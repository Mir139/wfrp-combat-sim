import json
import os

import pytest

from src import echarts
from src.database import DEFAULTS, FIELDS, display, form_values, item_from_values, items_using
from src.gui.state import AppState, json_files, safe_json_name
from src.jobs import (add_characters, add_faction, add_member, characters_from_data, duplicate_member, member_names,
                      new_character, new_job, set_field, unique_name, validate_job)
from src.loader import create_characters, load_inventory, load_simulation_config
from src.palette import DARK, LIGHT, THEMES
from src.report import csv_text, json_text, log_rows
from src.simulation import Simulation
from tests.helpers import make_character, make_faction


def _job():
    job = new_job()
    for faction in job["factions"]:
        faction["members"].append(new_character(f"{faction['name']} member"))
    return job


# --- job editing -------------------------------------------------------------------------------

def test_unique_name():
    assert unique_name("Goblin", {"Orc"}) == "Goblin"
    assert unique_name("Goblin", {"Goblin"}) == "Goblin 2"
    assert unique_name("Goblin", {"Goblin", "Goblin 2"}) == "Goblin 3"


def test_add_faction_and_members_get_unique_names():
    job = new_job()
    assert add_faction(job) == 2 and job["factions"][2]["name"] == "Faction 3"
    assert add_member(job, 0) == 0 and add_member(job, 1) == 0
    assert sorted(member_names(job)) == ["New character", "New character 2"]
    assert validate_job(job) != []  # the third faction has no character
    assert duplicate_member(job, 0, 0) == 1 and job["factions"][0]["members"][1]["name"] == "New character 3"


def test_duplicate_is_a_deep_copy():
    job = _job()
    member = job["factions"][0]["members"][0]
    member["inventory"].append({"type": "armors", "name": "Armure légère"})
    duplicate_member(job, 0, 0)
    job["factions"][0]["members"][1]["inventory"].clear()
    assert member["inventory"]


def test_set_field_updates_characteristics_as_whole_numbers():
    job = _job()
    member = job["factions"][0]["members"][0]
    set_field(job, member, "CC", 55.0)
    set_field(job, member, "health", 20)
    assert member["CC"] == 55 and isinstance(member["CC"], int) and member["health"] == 20


@pytest.mark.parametrize("key, value", [("CC", "abc"), ("CC", None), ("CC", 12.5), ("CC", -3), ("health", 0),
                                        ("health", True), ("name", "  "), ("targeting", "bravest"),
                                        ("behavior", "flying"), ("rout_threshold", 1.5), ("rout_threshold", 0),
                                        ("nonsense", 1)])
def test_set_field_rejects_invalid_values_and_keeps_the_old_one(key, value):
    job = _job()
    member = job["factions"][0]["members"][0]
    before = dict(member)
    with pytest.raises((ValueError, TypeError)):
        set_field(job, member, key, value)
    assert member == before


def test_set_field_name_must_stay_unique():
    job = _job()
    first, second = job["factions"][0]["members"][0], job["factions"][1]["members"][0]
    with pytest.raises(ValueError):
        set_field(job, first, "name", second["name"])
    set_field(job, first, "name", first["name"])  # keeping its own name is fine
    set_field(job, first, "name", "  Renamed ")
    assert first["name"] == "Renamed"
    with pytest.raises(ValueError):
        set_field(job, job["factions"][0], "name", job["factions"][1]["name"])


def test_optional_fields_are_removed_when_blank():
    job = _job()
    member = job["factions"][0]["members"][0]
    set_field(job, member, "targeting", "weakest")
    set_field(job, member, "rout_threshold", 0.5)
    set_field(job, member, "on_rout", "flee")
    assert (member["targeting"], member["rout_threshold"], member["on_rout"]) == ("weakest", 0.5, "flee")
    for key in ("targeting", "rout_threshold", "on_rout"):
        set_field(job, member, key, "" if key != "rout_threshold" else None)
        assert key not in member


def test_faction_fields_can_be_edited_too():
    job = _job()
    set_field(job, job["factions"][0], "targeting", "dangerous")
    assert job["factions"][0]["targeting"] == "dangerous"
    assert validate_job(job) == []


def test_add_characters_renames_duplicates():
    job = _job()
    incoming = [new_character("Faction 1 member"), new_character("Faction 1 member"), new_character("Fresh")]
    add_characters(job, 0, incoming)
    assert [m["name"] for m in job["factions"][0]["members"]] == [
        "Faction 1 member", "Faction 1 member 2", "Faction 1 member 3", "Fresh"]


def test_characters_from_data_accepts_the_usual_shapes():
    job = _job()
    member = job["factions"][0]["members"][0]
    assert len(characters_from_data(job)) == 2
    assert len(characters_from_data(job["factions"][0])) == 1
    assert len(characters_from_data([member, member])) == 2
    assert characters_from_data(member)[0]["name"] == member["name"]
    for bad in ({"foo": 1}, [], [1], "text", 3):
        with pytest.raises(ValueError):
            characters_from_data(bad)


# --- item database ------------------------------------------------------------------------------

def test_item_forms_round_trip():
    item = {"name": "Cotte", "penalty": ["-10% Perception"], "location": "Tous", "armor_points": "2", "attributes": []}
    values = form_values("armors", item)
    assert values["penalty"] == "-10% Perception" and values["attributes"] == ""
    assert item_from_values("armors", values, set()) == item


def test_item_from_values_validates():
    values = form_values("melee_weapons", dict(DEFAULTS["melee_weapons"], name="Épée"))
    assert item_from_values("melee_weapons", values, {"Hache"})["damage"] == "4"
    with pytest.raises(ValueError):
        item_from_values("melee_weapons", dict(values, damage="lots"), set())
    with pytest.raises(ValueError):
        item_from_values("melee_weapons", dict(values, name=" "), set())
    with pytest.raises(ValueError):
        item_from_values("melee_weapons", values, {"Épée"})


def test_armor_locations_and_lists_are_parsed():
    values = form_values("armors", dict(DEFAULTS["armors"], name="Casque"))
    item = item_from_values("armors", dict(values, location="Tête, Corps", attributes="Flexible, Lourde"), set())
    assert item["location"] == ["Tête", "Corps"] and item["attributes"] == ["Flexible", "Lourde"]


def test_every_item_type_has_a_complete_default_and_form():
    for item_type, fields in FIELDS.items():
        assert {key for key, _ in fields} == set(DEFAULTS[item_type])
        values = form_values(item_type, dict(DEFAULTS[item_type], name="X"))
        assert item_from_values(item_type, values, set())["name"] == "X"


def test_display_and_usage():
    assert display(["a", "b"]) == "a, b" and display(True) == "yes" and display(False) == "" and display("x") == "x"
    job = load_simulation_config("sim/job1.json")
    assert "Else Sigloben" in items_using(job, "ranged_weapons", "Pistolet")
    assert items_using(job, "ranged_weapons", "Arc") == []


def test_the_shipped_database_survives_a_form_round_trip():
    inventory = load_inventory("db/db.json")
    for item_type, items in inventory.items():
        for item in items:
            rebuilt = item_from_values(item_type, form_values(item_type, item), set())
            assert rebuilt["name"] == item["name"]


# --- state and files -------------------------------------------------------------------------------

def test_state_defaults_load_the_example_job_and_database():
    state = AppState()
    state.load_defaults()
    assert len(state.job["factions"]) == 2 and state.inventory["armors"]
    assert validate_job(state.job, state.inventory) == []


def test_state_runs_keep_the_number_of_logs():
    state = AppState()
    assert state.run is None
    factions = [make_faction("F1", make_character("A")), make_faction("F2", make_character("B", faction="F2"))]
    sim = Simulation(factions, seed=1)
    results = sim.run_simulation(12, keep_logs=5)
    run = state.add_run(results, sim.gather_metrics(results))
    assert run.logs == 5 and state.run is run and state.current_run == 0


def test_json_helpers(tmp_path):
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "b.txt").write_text("")
    assert json_files(str(tmp_path)) == ["a.json"] and json_files(str(tmp_path / "missing")) == []
    assert safe_json_name("../../etc/passwd", "x.json") == "passwd.json"
    assert safe_json_name("job", "x.json") == "job.json" and safe_json_name("", "x.json") == "x.json"
    assert safe_json_name("dir/job.json", "x.json") == "job.json"


# --- exports and progress -----------------------------------------------------------------------------

def test_csv_and_json_text():
    assert csv_text([{"a": 1, "b": "x,y"}]).splitlines() == ["a,b", '1,"x,y"']
    assert csv_text([]).strip() == ""
    assert json.loads(json_text({"é": 1})) == {"é": 1} and "é" in json_text({"é": 1})


def test_log_rows_cover_every_kind_of_action():
    factions = load_simulation_config("sim/job1.json")
    inventory = load_inventory("db/db.json")
    sim = Simulation(create_characters(factions["factions"], inventory), seed=3)
    log = sim.run_simulation(1, keep_logs=None)[0]["action_log"]
    rows = log_rows(log)
    assert len(rows) == len(log) and rows[0]["action"] == "Combat starts"
    assert {"Run", "Attack", "Ranged attack"} <= {r["action"].split(" (")[0] for r in rows}
    assert all(set(r) == {"action", "attacker", "target", "roll", "dr", "damage", "target_hp"} for r in rows)


def test_log_rows_flag_criticals_fumbles_and_routs():
    attack = {"attack_roll": 22, "enemy_roll": 50, "attack_dr": 5, "enemy_dr": 1, "damage": 9, "critical": True, "fumble": False}
    rows = log_rows([
        {"action": "attack", "attacker": "A", "target": "B", "details": attack, "enemy_health": 3},
        {"action": "attack", "attacker": "A", "target": "B", "details": dict(attack, critical=False, fumble=True), "enemy_health": 3},
        {"action": "rout", "attacker": "A", "target": "A", "details": {"outcome": "fled", "trigger": "wounded", "roll": 88, "target": 30}},
        {"action": "bleed", "attacker": "A", "target": "A", "details": {"damage": 2}, "enemy_health": 4},
        {"action": "reload", "attacker": "A", "target": "A", "details": {"weapon": "Pistolet", "ready": True}},
    ])
    assert [r["action"] for r in rows] == ["Attack (critical)", "Attack (fumble)", "Rout (fled)", "Bleed", "Reload"]
    assert rows[0]["roll"] == "22 | 50" and rows[3]["damage"] == 2 and rows[2]["target"] == ""


def test_progress_is_reported_and_reaches_the_total():
    factions = [make_faction("F1", make_character("A")), make_faction("F2", make_character("B", faction="F2"))]
    calls = []
    Simulation(factions, seed=1).run_simulation(120, keep_logs=0, progress=lambda done, total: calls.append((done, total)))
    assert len(calls) > 5 and calls[-1] == (120, 120)
    assert [c[0] for c in calls] == sorted(c[0] for c in calls)
    assert Simulation(factions, seed=1).run_simulation(30, keep_logs=0) == Simulation(factions, seed=1).run_simulation(30, keep_logs=0, progress=lambda *a: None)


# --- palette ----------------------------------------------------------------------------------------------

def test_palettes_have_the_same_shape_and_dark_is_dark():
    assert set(THEMES) == {"light", "dark"}
    assert len(LIGHT.series) == len(DARK.series) == 8 and len(LIGHT.sequential) == len(DARK.sequential) == 7
    assert LIGHT.surface > DARK.surface
    # the sequential ramps run from the lowest to the highest value: the high end is dark on the light theme
    # (against a light surface) and light on the dark theme
    assert LIGHT.sequential[0] > LIGHT.sequential[-1] and DARK.sequential[0] < DARK.sequential[-1]
