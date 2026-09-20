"""Editing helpers for job files: validation, blank characters and import of character sheets."""
import copy
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


def characters_from_data(data):
    """Characters found in parsed JSON: a single character, a list, a faction, or a whole job file.

    Returns the list of character dicts (as found: use `character_problems` to check them).
    """
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


def import_characters(path):
    """Read characters from a JSON file (see `characters_from_data`)."""
    with open(path, "r", encoding="utf-8") as file:
        return characters_from_data(json.load(file))


# --- editing ------------------------------------------------------------------------------------------

OPTIONAL_CHOICES = {"behavior": BEHAVIORS, "targeting": list(TARGETING_STRATEGIES), "on_rout": list(ROUT_BEHAVIORS)}


def unique_name(base, taken):
    if base not in taken:
        return base
    k = 2
    while f"{base} {k}" in taken:
        k += 1
    return f"{base} {k}"


def member_names(job):
    return {m["name"] for f in job["factions"] for m in f["members"]}


def add_faction(job):
    """Append an empty faction; returns its index."""
    job["factions"].append({"name": unique_name(f"Faction {len(job['factions']) + 1}", {f["name"] for f in job["factions"]}),
                            "members": []})
    return len(job["factions"]) - 1


def add_member(job, faction_index):
    """Append a blank character to a faction; returns its index."""
    members = job["factions"][faction_index]["members"]
    members.append(new_character(unique_name("New character", member_names(job))))
    return len(members) - 1


def duplicate_member(job, faction_index, member_index):
    members = job["factions"][faction_index]["members"]
    clone = copy.deepcopy(members[member_index])
    clone["name"] = unique_name(clone["name"], member_names(job))
    members.append(clone)
    return len(members) - 1


def add_characters(job, faction_index, characters):
    """Add imported characters to a faction, renaming those whose name is already taken."""
    taken = member_names(job)
    for character in characters:
        character["name"] = unique_name(character["name"], taken)
        taken.add(character["name"])
        job["factions"][faction_index]["members"].append(character)


def set_field(job, target, key, value):
    """Set a field of a character or faction dict after validating it; raises ValueError when invalid.

    Optional fields (fighting style, targeting, rout) are removed when `value` is None or blank.
    """
    is_faction = "members" in target
    if key == "name":
        value = (value or "").strip()
        if not value:
            raise ValueError("The name cannot be empty")
        others = {f["name"] for f in job["factions"] if f is not target} if is_faction else member_names(job) - {target["name"]}
        if value in others:
            raise ValueError(f"There is already a {'faction' if is_faction else 'character'} named '{value}'")
    elif key in OPTIONAL_CHOICES:
        if value in (None, ""):
            target.pop(key, None)
            return
        if value not in OPTIONAL_CHOICES[key]:
            raise ValueError(f"Unknown {key} '{value}'")
    elif key == "rout_threshold":
        if value in (None, ""):
            target.pop(key, None)
            return
        if not 0 < float(value) <= 1:
            raise ValueError("The rout threshold must be between 0 and 1")
        value = float(value)
    elif key == "health" or key in CHARACTERISTICS:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"'{key}' must be a number")
        if value != int(value) or value < 0 or (key == "health" and value <= 0):
            raise ValueError(f"'{key}' must be a whole number, positive" if key == "health" else f"'{key}' must be a whole number, 0 or more")
        value = int(value)
    else:
        raise ValueError(f"Unknown field '{key}'")
    target[key] = value
