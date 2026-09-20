"""Editing helpers for job files: validation, blank characters and import of character sheets."""
import json

from src.character import ROUT_BEHAVIORS, TARGETING_STRATEGIES

CHARACTERISTICS = ["M", "CC", "CT", "F", "E", "I", "Ag", "Dex", "Int", "FM", "Soc"]
REQUIRED_FIELDS = ["name", "health"] + CHARACTERISTICS
ITEM_TYPES = ["melee_weapons", "ranged_weapons", "armors"]
BEHAVIORS = ["melee", "ranged"]


def new_character(name="New character"):
    """A blank average character."""
    character = {"name": name, "health": 10}
    character.update({field: 30 for field in CHARACTERISTICS})
    character["M"] = 4
    character["inventory"] = []
    return character


def new_job():
    return {"factions": [{"name": "Faction 1", "members": []}, {"name": "Faction 2", "members": []}],
            "simulation": {"num_simulations": 10000}}


def character_problems(member, where, inventory):
    problems = []
    for field in REQUIRED_FIELDS:
        if field not in member:
            problems.append(f"{where}: missing '{field}'")
        elif field != "name" and not isinstance(member[field], (int, float)):
            problems.append(f"{where}: '{field}' must be a number")
    if isinstance(member.get("health"), (int, float)) and member["health"] <= 0:
        problems.append(f"{where}: 'health' must be positive")
    if member.get("behavior") not in (None, *BEHAVIORS):
        problems.append(f"{where}: unknown behavior '{member['behavior']}'")
    if member.get("targeting") not in (None, *TARGETING_STRATEGIES):
        problems.append(f"{where}: unknown targeting '{member['targeting']}'")
    if member.get("on_rout") not in (None, *ROUT_BEHAVIORS):
        problems.append(f"{where}: unknown on_rout '{member['on_rout']}'")
    for item in member.get("inventory", []):
        if item.get("type") not in ITEM_TYPES:
            problems.append(f"{where}: unknown item type '{item.get('type')}'")
        elif inventory is not None and not any(i["name"] == item.get("name") for i in inventory.get(item["type"], [])):
            problems.append(f"{where}: item '{item.get('name')}' ({item['type']}) is not in the item database")
    return problems


def validate_job(config, inventory=None):
    """List of problems that would make the job fail or misbehave (empty when it is fine).

    Item names are checked against `inventory` (the database's 'inventory' section) when given.
    """
    problems = []
    factions = config.get("factions", [])
    if len(factions) < 2:
        problems.append("A job needs at least two factions")
    names, seen = [], set()
    for faction in factions:
        if not faction.get("name"):
            problems.append("A faction has no name")
        if not faction.get("members"):
            problems.append(f"Faction '{faction.get('name')}' has no character")
        for member in faction.get("members", []):
            where = f"{faction.get('name')}/{member.get('name')}"
            problems += character_problems(member, where, inventory)
            if member.get("name") in seen:
                problems.append(f"Two characters are named '{member.get('name')}'")
            seen.add(member.get("name"))
            names.append(member.get("name"))
    return problems


def import_characters(path):
    """Read characters from a JSON file: a single character, a list of characters, or a whole job file.

    Returns the list of character dicts (as found: use `validate_job` to check them).
    """
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    if isinstance(data, dict) and "factions" in data:
        characters = [m for f in data["factions"] for m in f.get("members", [])]
    elif isinstance(data, dict) and "members" in data:
        characters = list(data["members"])
    elif isinstance(data, dict):
        characters = [data]
    elif isinstance(data, list):
        characters = list(data)
    else:
        raise ValueError("Unrecognised character file")
    characters = [c for c in characters if isinstance(c, dict)]
    if not characters or any("name" not in c for c in characters):
        raise ValueError("No character with a name found in the file")
    for character in characters:
        character.setdefault("inventory", [])
    return characters
