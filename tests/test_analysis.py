import copy
import csv
import json
import random

import pytest

from src.cli import main
from src.combat import Combat
from src.compare import apply_variant, expand_sweeps, load_variants, run_comparison
from src.loader import create_characters, load_inventory, load_simulation_config
from src.report import (comparison_rows, format_comparison, format_report, health_histogram, metrics_rows)
from src.simulation import Simulation, simulate_battle
from src.stats import wilson_interval
from tests.helpers import make_character, make_faction, make_ranged


def _job():
    return load_simulation_config("sim/job1.json"), load_inventory("db/db.json")


def _duel_factions(hero_health=15, foe_health=15):
    return [make_faction("F1", make_character("Hero", health=hero_health)),
            make_faction("F2", make_character("Foe", faction="F2", health=foe_health))]


# --- confidence intervals -------------------------------------------------------

def test_wilson_interval_known_values():
    low, high = wilson_interval(50, 100)
    assert low == pytest.approx(0.4038, abs=1e-3) and high == pytest.approx(0.5962, abs=1e-3)


def test_wilson_interval_stays_within_bounds_at_the_extremes():
    low, high = wilson_interval(0, 100)
    assert low == 0.0 and 0 < high < 0.05
    low, high = wilson_interval(100, 100)
    assert high == 1.0 and 0.95 < low < 1


def test_wilson_interval_without_data_is_uninformative():
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_wilson_interval_narrows_with_more_samples_and_widens_with_confidence():
    narrow = wilson_interval(500, 1000)
    wide = wilson_interval(50, 100)
    assert narrow[1] - narrow[0] < wide[1] - wide[0]
    assert wilson_interval(50, 100, 0.99)[1] - wilson_interval(50, 100, 0.99)[0] > wide[1] - wide[0]


# --- reset and reproducibility ----------------------------------------------------

def test_reset_restores_a_fresh_character():
    fresh = make_character("A")
    fresh.inventory.add_item(make_ranged())
    used = copy.deepcopy(fresh)
    used.health, used.bleeding, used.stunned, used.prone = 1, 2, True, True
    used.status, used.target, used.position = "fled", fresh, (5.0, 5.0)
    used.morale_checked.add("wounded")
    used.ranged_weapons()[0].jam()
    used.reset()
    state = lambda c: {k: v for k, v in vars(c).items() if k not in ("inventory", "target")}
    assert state(used) == state(fresh)
    assert used.target is None
    assert [vars(w) for w in used.ranged_weapons()] == [vars(w) for w in fresh.ranged_weapons()]


def test_a_battle_does_not_depend_on_the_battles_run_before_it():
    config, inventory = _job()
    fresh = create_characters(config["factions"], inventory)
    reused = create_characters(config["factions"], inventory)
    for seed in range(5):
        simulate_battle(reused, seed, 12, False)
    for seed in (100, 101, 102):
        a = simulate_battle(reused, seed, 12, True)
        b = simulate_battle(copy.deepcopy(fresh), seed, 12, True)
        assert a == b


def test_results_do_not_depend_on_the_number_of_workers():
    config, inventory = _job()
    factions = create_characters(config["factions"], inventory)
    sequential = Simulation(factions, seed=5).run_simulation(24, keep_logs=3, workers=1)
    parallel = Simulation(factions, seed=5).run_simulation(24, keep_logs=3, workers=2)
    assert sequential == parallel


def test_logs_are_kept_only_for_the_first_battles():
    results = Simulation(_duel_factions(), seed=1).run_simulation(10, keep_logs=3)
    assert [r["action_log"] is not None for r in results] == [True] * 3 + [False] * 7
    everything = Simulation(_duel_factions(), seed=1).run_simulation(5, keep_logs=None)
    assert all(r["action_log"] for r in everything)


def test_simulation_leaves_the_template_characters_untouched_in_the_next_run():
    factions = _duel_factions()
    sim = Simulation(factions, seed=2)
    first = [r["winner"] for r in sim.run_simulation(20)]
    again = [r["winner"] for r in Simulation(factions, seed=2).run_simulation(20)]
    assert first == again


# --- new metrics ----------------------------------------------------------------------

def test_combat_records_rounds_and_order_of_deaths():
    strong = make_character("Strong", health=50, CC=90, I=40)
    weak = make_character("Weak", faction="F2", health=3, CC=10)
    combat = Combat([make_faction("F1", strong), make_faction("F2", weak)], random.Random(0))
    winner, _, _, _ = combat.run_combat()
    assert winner == "F1"
    assert combat.deaths == ["Weak"]
    assert combat.rounds >= 1


def _fake_results():
    return [
        {"winner": "F1", "remaining_health": {"Hero": 4}, "routed": {}, "rounds": 3, "deaths": ["Foe"], "survivors": ["Hero"]},
        {"winner": "F1", "remaining_health": {"Hero": 10, "Foe": 2}, "routed": {"Foe": "fled"}, "rounds": 5, "deaths": [], "survivors": ["Hero", "Foe"]},
        {"winner": "F2", "remaining_health": {"Foe": 7}, "routed": {}, "rounds": 7, "deaths": ["Hero"], "survivors": ["Foe"]},
        {"winner": None, "remaining_health": {}, "routed": {}, "rounds": 9, "deaths": ["Hero", "Foe"], "survivors": []},
    ]


def test_metrics_from_known_results():
    sim = Simulation(_duel_factions(hero_health=10, foe_health=10))
    m = sim.gather_metrics(_fake_results())
    assert m["rounds"] == {"mean": 6, "median": 6, "min": 3, "max": 9}
    assert m["draws"] == 1
    assert m["survival_probabilities"] == {"F1": 0.5, "F2": 0.25}
    assert m["individual_death_probabilities"] == {"Hero": 0.5, "Foe": 0.5}
    assert m["individual_survival_probabilities"] == {"Hero": 0.5, "Foe": 0.5}
    assert m["first_death_probabilities"] == {"Hero": 0.5, "Foe": 0.25}
    assert m["individual_rout_probabilities"] == {"Hero": 0, "Foe": 0.25}
    assert m["remaining_health_distribution"]["Hero"] == {0: 2, 4: 1, 10: 1}
    assert m["members"]["Hero"] == {"faction": "F1", "max_health": 10}


def test_metrics_include_confidence_intervals_around_each_probability():
    m = Simulation(_duel_factions()).gather_metrics(_fake_results())
    intervals = dict(m["confidence_intervals"])
    low, high = intervals.pop("draw_probability")
    assert 0 <= low <= m["draws"] / 4 <= high <= 1
    for group, values in intervals.items():
        for key, (low, high) in values.items():
            assert 0 <= low <= m[group][key] <= high <= 1


def test_metrics_tolerate_results_without_the_new_fields():
    results = [{"winner": "F1", "survivors": ["Hero"], "remaining_health": {"Hero": 7}, "action_log": []}]
    m = Simulation(_duel_factions()).gather_metrics(results)
    assert m["rounds"] == {} and m["individual_survival_probabilities"]["Hero"] == 1


def test_wider_intervals_with_fewer_battles():
    sim = Simulation(_duel_factions())
    few = sim.gather_metrics(_fake_results())["confidence_intervals"]["survival_probabilities"]["F1"]
    many = sim.gather_metrics(_fake_results() * 50)["confidence_intervals"]["survival_probabilities"]["F1"]
    assert many[1] - many[0] < few[1] - few[0]


# --- what-if scenarios --------------------------------------------------------------------

def test_copy_members_clones_with_numbered_names():
    config, _ = _job()
    out = apply_variant(config, {"copy_members": [{"member": "Terreur de la Teufel", "count": 2}]})
    names = [m["name"] for m in out["factions"][1]["members"]]
    assert names == ["Terreur de la Teufel", "Terreur de la Teufel 2", "Terreur de la Teufel 3"]
    assert len(config["factions"][1]["members"]) == 1  # the original config is not modified


def test_variant_operations():
    config, _ = _job()
    out = apply_variant(config, {
        "remove_members": ["Else Sigloben"],
        "set": {"Amris Pluiedebraise": {"CC": 99}},
        "add_items": [{"member": "Molrella Tuilecaramel", "type": "armors", "name": "Armure lourde"}],
        "remove_items": [{"member": "Molrella Tuilecaramel", "name": "Fronde"}],
        "faction_set": {"Faction2": {"targeting": "weakest"}},
        "simulation": {"initial_distance": 3},
    })
    players = {m["name"]: m for m in out["factions"][0]["members"]}
    assert "Else Sigloben" not in players
    assert players["Amris Pluiedebraise"]["CC"] == 99
    molrella_items = [i["name"] for i in players["Molrella Tuilecaramel"]["inventory"]]
    assert "Armure lourde" in molrella_items and "Fronde" not in molrella_items
    assert out["factions"][1]["targeting"] == "weakest"
    assert out["simulation"]["initial_distance"] == 3


def test_add_member_to_a_faction():
    config, _ = _job()
    newcomer = dict(config["factions"][1]["members"][0], name="Renfort")
    out = apply_variant(config, {"add_members": [{"faction": "Faction2", "member": newcomer}]})
    assert out["factions"][1]["members"][-1]["name"] == "Renfort"


@pytest.mark.parametrize("variant", [
    {"set": {"Nobody": {"CC": 1}}},
    {"remove_members": ["Nobody"]},
    {"faction_set": {"Nobody": {}}},
    {"remove_items": [{"member": "Molrella Tuilecaramel", "name": "Not an item"}]},
])
def test_unknown_targets_are_reported(variant):
    config, _ = _job()
    with pytest.raises(ValueError):
        apply_variant(config, variant)


def test_sweeps_expand_into_named_variants():
    variants = expand_sweeps([{"member": "A", "field": "CC", "values": [30, 40]},
                              {"copy_member": "B", "counts": [1, 2]}])
    assert [v["name"] for v in variants] == ["A.CC=30", "A.CC=40", "B x2", "B x3"]
    assert variants[0]["set"] == {"A": {"CC": 30}}
    assert variants[3]["copy_members"] == [{"member": "B", "count": 2}]
    with pytest.raises(ValueError):
        expand_sweeps([{"oops": 1}])


def test_load_variants_names_the_anonymous_ones():
    assert load_variants({"variants": [{"set": {}}], "sweeps": []})[0]["name"] == "variant 1"


def test_comparison_uses_the_same_seed_so_the_base_matches_a_plain_run():
    config, inventory = _job()
    outcomes = run_comparison(config, inventory, [{"name": "no Else", "remove_members": ["Else Sigloben"]}], 200, seed=4)
    assert [o["name"] for o in outcomes] == ["base", "no Else"]
    sim = Simulation(create_characters(config["factions"], inventory), seed=4)
    plain = sim.gather_metrics(sim.run_simulation(200, keep_logs=0))
    assert outcomes[0]["metrics"]["survival_probabilities"] == plain["survival_probabilities"]
    assert "Else Sigloben" not in outcomes[1]["metrics"]["members"]


def test_adding_enemies_lowers_the_players_chances():
    config, inventory = _job()
    variants = expand_sweeps([{"copy_member": "Terreur de la Teufel", "counts": [2]}])
    outcomes = run_comparison(config, inventory, variants, 300, seed=1)
    assert outcomes[1]["metrics"]["survival_probabilities"]["Joueurs"] < outcomes[0]["metrics"]["survival_probabilities"]["Joueurs"]


# --- reports ------------------------------------------------------------------------------

def test_health_histogram_buckets():
    buckets = health_histogram({0: 5, 1: 2, 10: 3, 12: 1}, 10)
    assert buckets["dead"] == 5
    assert buckets["1-1"] == 2
    assert buckets["10-10"] == 4  # 12 (above max) lands in the last bucket
    assert sum(buckets.values()) == 11


def test_health_histogram_with_a_small_max_health():
    buckets = health_histogram({0: 1, 1: 1, 2: 1}, 2)
    assert list(buckets) == ["dead", "1-1", "2-2"] and list(buckets.values()) == [1, 1, 1]


def test_text_report_lists_every_character_with_intervals():
    m = Simulation(_duel_factions()).gather_metrics(_fake_results())
    text = format_report(m, title="job", histogram=True)
    for expected in ("Hero", "Foe", "F1", "95% confidence", "Rounds per combat", "Falls first", "Remaining health", "["):
        assert expected in text


def test_comparison_report_shows_deltas_against_the_base():
    sim = Simulation(_duel_factions())
    base = sim.gather_metrics(_fake_results())
    worse = sim.gather_metrics(_fake_results()[2:])
    text = format_comparison([{"name": "base", "metrics": base}, {"name": "worse", "metrics": worse}])
    assert "worse" in text and "-50.0" in text  # F1 wins 50% in the base and 0% in the variant


def test_csv_rows():
    m = Simulation(_duel_factions()).gather_metrics(_fake_results())
    rows = metrics_rows(m)
    assert [r["name"] for r in rows] == ["Hero", "Foe"]
    assert rows[0]["survival"] == 0.5 and rows[0]["survival_ci_low"] < 0.5 < rows[0]["survival_ci_high"]
    scenarios = comparison_rows([{"name": "base", "metrics": m}])
    assert scenarios[0]["scenario"] == "base" and scenarios[0]["delta_vs_base"] == 0


# --- command line ---------------------------------------------------------------------------

def test_cli_prints_a_report_and_exports(tmp_path, capsys):
    out_json, out_csv = tmp_path / "out.json", tmp_path / "out.csv"
    main(["sim/job1.json", "-n", "40", "--seed", "1", "--json", str(out_json), "--csv", str(out_csv)])
    assert "40 combats" in capsys.readouterr().out
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["seed"] == 1 and data["metrics"]["total_battles"] == 40
    with open(out_csv, encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 6 and rows[0]["name"] == "Gunnar Hrolfsson"


def test_cli_is_reproducible_with_a_seed(capsys):
    main(["sim/job1.json", "-n", "60", "--seed", "3"])
    first = capsys.readouterr().out
    main(["sim/job1.json", "-n", "60", "--seed", "3"])
    assert capsys.readouterr().out == first


def test_cli_number_of_simulations_defaults_to_the_job_setting(capsys):
    main(["sim/job1.json", "--seed", "1", "-n", "5"])
    assert "5 combats" in capsys.readouterr().out
    assert load_simulation_config("sim/job1.json")["simulation"]["num_simulations"] == 10000


def test_cli_comparison(tmp_path, capsys):
    compare = tmp_path / "compare.json"
    compare.write_text(json.dumps({"sweeps": [{"copy_member": "Terreur de la Teufel", "counts": [1]}]}), encoding="utf-8")
    out_csv = tmp_path / "cmp.csv"
    main(["sim/job1.json", "-n", "30", "--seed", "1", "--compare", str(compare), "--csv", str(out_csv)])
    text = capsys.readouterr().out
    assert "Terreur de la Teufel x2" in text and "base" in text
    assert "scenario" in out_csv.read_text(encoding="utf-8")


def test_cli_reports_errors_without_a_traceback():
    with pytest.raises(SystemExit) as error:
        main(["sim/missing.json"])
    assert "Error" in str(error.value)
    with pytest.raises(SystemExit):
        main(["sim/job1.json", "--confidence", "1.5"])
    with pytest.raises(SystemExit):
        main(["sim/job1.json", "-n", "-3", "--seed", "1"])
