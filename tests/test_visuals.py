import json
import os
import random

import pytest

matplotlib = pytest.importorskip("matplotlib")

from src.cli import main
from src.combat import Combat
from src.jobs import (CHARACTERISTICS, character_problems, import_characters, new_character, new_job, validate_job)
from src.loader import create_characters, load_inventory, load_simulation_config
from src.plots import (SERIES, all_figures, faction_colors, plot_comparison, plot_hit_locations, plot_survival,
                       plot_win_probabilities, save_plots)
from src.compare import run_comparison
from src.simulation import Simulation
from tests.helpers import make_character, make_faction


@pytest.fixture(scope="module")
def job_metrics():
    config = load_simulation_config("sim/job1.json")
    factions = create_characters(config["factions"], load_inventory("db/db.json"))
    sim = Simulation(factions, seed=1)
    return sim.gather_metrics(sim.run_simulation(300, keep_logs=0))


# --- hit locations -----------------------------------------------------------------

def test_combat_records_hits_and_damage_per_target_and_location():
    a = make_faction("F1", make_character("A", health=30, CC=90, I=50))
    b = make_faction("F2", make_character("B", faction="F2", health=30, CC=10))
    combat = Combat([a, b], random.Random(2))
    combat.run_combat()
    assert set(combat.hits) == {"B"}
    total_hits = sum(count for count, _ in combat.hits["B"].values())
    total_damage = sum(damage for _, damage in combat.hits["B"].values())
    assert total_hits >= 1 and total_damage >= total_hits  # every hit does at least 1 damage
    assert set(combat.hits["B"]) <= {"Head", "Left Arm", "Right Arm", "Body", "Left Leg", "Right Leg"}


def test_metrics_aggregate_hit_locations(job_metrics):
    locations = job_metrics["hit_locations"]
    assert set(locations) == set(job_metrics["members"])
    monster = locations["Terreur de la Teufel"]
    total = sum(v["hits"] for v in monster.values())
    assert total > 100
    assert monster["Body"]["hits"] / total == pytest.approx(0.35, abs=0.06)  # 35% of the table
    assert monster["Head"]["hits"] / total == pytest.approx(0.09, abs=0.04)


def test_hit_locations_are_summed_over_fights():
    sim = Simulation([make_faction("F1", make_character("A")), make_faction("F2", make_character("B", faction="F2"))])
    results = [{"winner": None, "remaining_health": {}, "hits": {"A": {"Head": [1, 4]}}},
               {"winner": None, "remaining_health": {}, "hits": {"A": {"Head": [2, 5], "Body": [1, 3]}}}]
    assert sim.gather_metrics(results)["hit_locations"] == {
        "A": {"Head": {"hits": 3, "damage": 9}, "Body": {"hits": 1, "damage": 3}}, "B": {}}


# --- charts ------------------------------------------------------------------------------

def test_every_chart_builds(job_metrics):
    figures = all_figures(job_metrics)
    assert set(figures) == {"win_probabilities", "survival", "health_distribution", "hit_locations"}
    assert all(f.axes for f in figures.values())


def test_faction_colors_follow_the_job_order_and_are_distinct(job_metrics):
    colors = faction_colors(job_metrics)
    assert list(colors.values()) == SERIES[:2]


def test_survival_chart_labels_every_character_with_its_value(job_metrics):
    ax = plot_survival(job_metrics).axes[0]
    assert [t.get_text() for t in ax.get_yticklabels()] == list(job_metrics["members"])
    labels = [t.get_text() for t in ax.texts]
    assert len(labels) == len(job_metrics["members"]) and all(label.endswith("%") for label in labels)


def test_win_chart_has_one_bar_per_faction(job_metrics):
    ax = plot_win_probabilities(job_metrics).axes[0]
    assert len(ax.patches) == 2


def test_faction_legend_only_with_several_factions(job_metrics):
    assert plot_survival(job_metrics).legends
    alone = Simulation([make_faction("F1", make_character("A"))], seed=1)
    single = alone.gather_metrics(alone.run_simulation(5, keep_logs=0))
    assert not plot_survival(single).legends


def test_hit_heatmap_handles_a_character_who_was_never_hit(job_metrics):
    metrics = dict(job_metrics, hit_locations=dict(job_metrics["hit_locations"], **{"Else Sigloben": {}}))
    fig = plot_hit_locations(metrics)
    assert "-" in [t.get_text() for t in fig.axes[0].texts]
    assert plot_hit_locations(metrics, "damage").axes


def test_save_plots_writes_png_files(tmp_path, job_metrics):
    paths = save_plots(job_metrics, str(tmp_path / "charts"))
    assert len(paths) == 4
    for path in paths:
        with open(path, "rb") as file:
            assert file.read(8) == b"\x89PNG\r\n\x1a\n"


def test_comparison_chart_shows_the_deltas():
    config = load_simulation_config("sim/job1.json")
    outcomes = run_comparison(config, load_inventory("db/db.json"),
                              [{"name": "no Else", "remove_members": ["Else Sigloben"]}], 100, seed=1)
    ax = plot_comparison(outcomes).axes[0]
    assert len(ax.patches) == 2
    assert any("(" in t.get_text() for t in ax.texts)  # the delta of the variant


def test_cli_writes_the_charts(tmp_path, capsys):
    main(["sim/job1.json", "-n", "30", "--seed", "1", "--plots", str(tmp_path)])
    assert sorted(os.listdir(tmp_path)) == ["health_distribution.png", "hit_locations.png", "survival.png", "win_probabilities.png"]
    main(["sim/job1.json", "-n", "30", "--seed", "1", "--compare", "sim/compare_example.json", "--plots", str(tmp_path / "cmp")])
    assert sorted(os.listdir(tmp_path / "cmp")) == ["comparison_Faction2.png", "comparison_Joueurs.png"]


# --- job editing helpers -------------------------------------------------------------------

def _valid_job():
    job = new_job()
    for faction in job["factions"]:
        faction["members"].append(new_character(f"{faction['name']} member"))
    return job


def test_a_new_job_with_new_characters_is_valid():
    assert validate_job(_valid_job()) == []


def test_new_character_has_every_required_field():
    character = new_character("X")
    assert character["name"] == "X" and all(f in character for f in CHARACTERISTICS)


def test_validation_reports_missing_and_wrong_fields():
    job = _valid_job()
    member = job["factions"][0]["members"][0]
    del member["CC"]
    member["FM"] = "high"
    member["health"] = 0
    member["targeting"] = "bravest"
    problems = validate_job(job)
    assert any("missing 'CC'" in p for p in problems)
    assert any("'FM' must be a number" in p for p in problems)
    assert any("'health' must be positive" in p for p in problems)
    assert any("unknown targeting" in p for p in problems)


def test_validation_reports_structure_problems():
    job = _valid_job()
    job["factions"][1]["members"].append(new_character(job["factions"][0]["members"][0]["name"]))
    assert any("Two characters are named" in p for p in validate_job(job))
    assert any("at least two factions" in p for p in validate_job({"factions": job["factions"][:1]}))
    job["factions"][1]["members"] = []
    assert any("has no character" in p for p in validate_job(job))


def test_validation_checks_items_against_the_database():
    inventory = load_inventory("db/db.json")
    job = _valid_job()
    job["factions"][0]["members"][0]["inventory"] = [{"type": "armors", "name": "Armure lourde"},
                                                    {"type": "armors", "name": "Nope"},
                                                    {"type": "gadgets", "name": "x"}]
    problems = validate_job(job, inventory)
    assert any("'Nope'" in p for p in problems) and any("unknown item type" in p for p in problems)
    assert not any("Armure lourde" in p for p in problems)


def test_the_example_jobs_are_valid():
    inventory = load_inventory("db/db.json")
    assert validate_job(load_simulation_config("sim/job1.json"), inventory) == []


def test_import_accepts_a_job_a_list_or_a_single_character(tmp_path):
    job = _valid_job()
    member = job["factions"][0]["members"][0]
    files = {"job": job, "list": [member, job["factions"][1]["members"][0]], "single": member,
             "faction": job["factions"][0]}
    counts = {}
    for name, content in files.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(content), encoding="utf-8")
        counts[name] = len(import_characters(str(path)))
    assert counts == {"job": 2, "list": 2, "single": 1, "faction": 1}


def test_import_rejects_files_without_characters(tmp_path):
    for content in ({"foo": 1}, [], [1, 2], "text"):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(content), encoding="utf-8")
        with pytest.raises(ValueError):
            import_characters(str(path))


def test_imported_characters_get_an_inventory(tmp_path):
    member = new_character("Solo")
    del member["inventory"]
    path = tmp_path / "solo.json"
    path.write_text(json.dumps(member), encoding="utf-8")
    assert import_characters(str(path))[0]["inventory"] == []


def test_character_problems_is_reusable_on_a_single_character():
    assert character_problems(new_character("X"), "X", None) == []
    assert character_problems({"name": "X"}, "X", None)
