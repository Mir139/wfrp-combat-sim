"""The item database: field schema and validation of edited items."""
from src.jobs import ITEM_TYPES

TYPE_LABELS = {"melee_weapons": "Melee weapons", "ranged_weapons": "Ranged weapons", "armors": "Armors"}
# (key, kind): kinds are text, int (stored as a string, like the database does), list (comma separated) and bool
FIELDS = {
    "melee_weapons": [("name", "text"), ("reach", "text"), ("damage", "int"), ("attributes", "list"),
                      ("encumbrance", "text"), ("2M", "bool")],
    "ranged_weapons": [("name", "text"), ("range", "int"), ("damage", "int"), ("attributes", "list"),
                       ("encumbrance", "text"), ("2M", "bool"), ("range_BF", "bool"), ("damage_BF", "bool")],
    "armors": [("name", "text"), ("penalty", "list"), ("location", "text"), ("armor_points", "int"), ("attributes", "list")],
}
DEFAULTS = {"melee_weapons": {"name": "", "reach": "Moyenne", "damage": "4", "attributes": [], "encumbrance": "1", "2M": False},
            "ranged_weapons": {"name": "", "range": "20", "damage": "4", "attributes": [], "encumbrance": "1", "2M": False,
                               "range_BF": False, "damage_BF": False},
            "armors": {"name": "", "penalty": [], "location": "Tous", "armor_points": "1", "attributes": []}}
assert set(FIELDS) == set(DEFAULTS) == set(ITEM_TYPES)


def display(value):
    """How a value of an item is shown in a table."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, bool):
        return "yes" if value else ""
    return str(value)


def form_values(item_type, item):
    """The item as strings and booleans, ready to fill a form."""
    return {key: bool(item.get(key)) if kind == "bool" else display(item.get(key, "")) for key, kind in FIELDS[item_type]}


def item_from_values(item_type, values, other_names):
    """Build a database item from form values (strings and booleans); raises ValueError when invalid."""
    item = {}
    for key, kind in FIELDS[item_type]:
        value = values.get(key, False if kind == "bool" else "")
        if kind == "bool":
            item[key] = bool(value)
        elif kind == "list":
            item[key] = [part.strip() for part in str(value).split(",") if part.strip()]
        elif kind == "int":
            try:
                item[key] = str(int(str(value).strip()))
            except ValueError:
                raise ValueError(f"'{key}' must be a whole number, not '{value}'") from None
        else:
            item[key] = str(value).strip()
    if not item["name"]:
        raise ValueError("The name cannot be empty")
    if item["name"] in other_names:
        raise ValueError(f"There is already an item named '{item['name']}'")
    if item_type == "armors" and "," in item["location"]:
        item["location"] = [part.strip() for part in item["location"].split(",")]
    return item


def items_using(job, item_type, name):
    """Names of the characters carrying an item."""
    return [m["name"] for f in job["factions"] for m in f["members"]
            if any(i["type"] == item_type and i["name"] == name for i in m.get("inventory", []))]
