"""What-if analysis: run a job and variants of it with the same seed, and compare the outcomes.

A variant is a dict with a `name` and any of these operations (applied in this order):

    "simulation":      {"initial_distance": 6}                      override simulation settings
    "faction_set":     {"Faction2": {"targeting": "weakest"}}       override faction fields
    "remove_members":  ["Amris"]
    "copy_members":    [{"member": "Goblin", "count": 2}]           clone a member (named "Goblin 2", ...)
    "add_members":     [{"faction": "Faction2", "member": {...}}]   add a full character
    "set":             {"Molrella": {"CC": 50, "health": 20}}       override character fields
    "add_items":       [{"member": "Molrella", "type": "armors", "name": "Armure lourde"}]
    "remove_items":    [{"member": "Molrella", "name": "Fronde"}]

A sweep expands into one variant per value:

    {"member": "Amris", "field": "CC", "values": [30, 40, 50]}
    {"copy_member": "Goblin", "counts": [1, 2, 3]}
"""
import copy

from src.loader import create_characters
from src.simulation import Simulation
from src.combat import DEFAULT_DISTANCE


def _find_member(config, name):
    for faction in config["factions"]:
        for member in faction["members"]:
            if member["name"] == name:
                return faction, member
    raise ValueError(f"Unknown character '{name}'")


def _find_faction(config, name):
    for faction in config["factions"]:
        if faction["name"] == name:
            return faction
    raise ValueError(f"Unknown faction '{name}'")


def apply_variant(config, variant):
    """Return a modified deep copy of a job config."""
    config = copy.deepcopy(config)
    config.setdefault("simulation", {}).update(variant.get("simulation", {}))
    for name, fields in variant.get("faction_set", {}).items():
        _find_faction(config, name).update(fields)
    for name in variant.get("remove_members", []):
        faction, member = _find_member(config, name)
        faction["members"].remove(member)
    for spec in variant.get("copy_members", []):
        faction, member = _find_member(config, spec["member"])
        for k in range(2, spec.get("count", 1) + 2):
            clone = copy.deepcopy(member)
            clone["name"] = f"{member['name']} {k}"
            faction["members"].append(clone)
    for spec in variant.get("add_members", []):
        _find_faction(config, spec["faction"])["members"].append(copy.deepcopy(spec["member"]))
    for name, fields in variant.get("set", {}).items():
        _find_member(config, name)[1].update(fields)
    for spec in variant.get("add_items", []):
        _find_member(config, spec["member"])[1]["inventory"].append({"type": spec["type"], "name": spec["name"]})
    for spec in variant.get("remove_items", []):
        inventory = _find_member(config, spec["member"])[1]["inventory"]
        matches = [i for i in inventory if i["name"] == spec["name"]]
        if not matches:
            raise ValueError(f"'{spec['member']}' has no item '{spec['name']}'")
        inventory.remove(matches[0])
    return config


def expand_sweeps(sweeps):
    variants = []
    for sweep in sweeps:
        if "copy_member" in sweep:
            for count in sweep["counts"]:
                variants.append({"name": f"{sweep['copy_member']} x{count + 1}",
                                 "copy_members": [{"member": sweep["copy_member"], "count": count}]})
        elif "field" in sweep:
            for value in sweep["values"]:
                variants.append({"name": f"{sweep['member']}.{sweep['field']}={value}",
                                 "set": {sweep["member"]: {sweep["field"]: value}}})
        else:
            raise ValueError(f"Unknown sweep: {sweep}")
    return variants


def load_variants(comparison):
    """Variants of a comparison file: explicit ones followed by the expanded sweeps."""
    variants = list(comparison.get("variants", [])) + expand_sweeps(comparison.get("sweeps", []))
    for i, variant in enumerate(variants):
        variant.setdefault("name", f"variant {i + 1}")
    return variants


def run_comparison(config, inventory_data, variants, num_simulations, seed=None, workers=1, keep_logs=0):
    """Run the base job and every variant with the same seed; returns a list of {name, metrics}."""
    outcomes = []
    for variant in [{"name": "base"}] + list(variants):
        varied = apply_variant(config, variant)
        factions = create_characters(varied["factions"], inventory_data)
        distance = varied["simulation"].get("initial_distance", DEFAULT_DISTANCE)
        sim = Simulation(factions, seed=seed, initial_distance=distance)
        results = sim.run_simulation(num_simulations, keep_logs=keep_logs, workers=workers)
        outcomes.append({"name": variant["name"], "metrics": sim.gather_metrics(results)})
    return outcomes
