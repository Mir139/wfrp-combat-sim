import random

import pytest

from src.combat import Combat
from src.loader import create_characters
from src.simulation import Simulation
from tests.helpers import ScriptedRng, make_character, make_faction, make_ranged


def _combat(*factions, rng=None, distance=12):
    return Combat(list(factions), rng or random.Random(0), distance)


# --- targeting strategies ----------------------------------------------------

def _crowd():
    weak = make_character("Weak", faction="F2", health=3, CC=20)
    strong = make_character("Strong", faction="F2", health=30, CC=70, weapon_damage=9)
    return weak, strong


def test_weakest_targets_lowest_health():
    weak, strong = _crowd()
    hero = make_character("Hero", targeting="weakest")
    combat = _combat(make_faction("F1", hero), make_faction("F2", weak, strong))
    assert combat.select_target(hero, [strong, weak]) is weak


def test_dangerous_targets_highest_threat():
    weak, strong = _crowd()
    hero = make_character("Hero", targeting="dangerous")
    combat = _combat(make_faction("F1", hero), make_faction("F2", weak, strong))
    assert combat.select_target(hero, [weak, strong]) is strong


def test_threat_takes_the_best_of_melee_and_ranged():
    shooter = make_character("S", CC=20, CT=60, unarmed=True)
    shooter.inventory.add_item(make_ranged(damage=8))
    assert shooter.threat() == 60 * 8
    brute = make_character("B", CC=60, F=50, weapon_damage=4)
    assert brute.threat() == 60 * (5 + 4)


def test_nearest_targets_the_closest_enemy():
    near = make_character("Near", faction="F2")
    far = make_character("Far", faction="F3")
    hero = make_character("Hero")
    combat = _combat(make_faction("F1", hero), make_faction("F2", near), make_faction("F3", far))
    near.position = (3.0, 0.0)
    far.position = (30.0, 0.0)
    assert combat.select_target(hero, [far, near]) is near


def test_random_targeting_sticks_to_its_target_until_it_dies():
    a, b = make_character("A", faction="F2"), make_character("B", faction="F2")
    hero = make_character("Hero", targeting="random")
    combat = _combat(make_faction("F1", hero), make_faction("F2", a, b), rng=random.Random(5))
    first = combat.select_target(hero, [a, b])
    assert all(combat.select_target(hero, [a, b]) is first for _ in range(10))
    other = b if first is a else a
    assert combat.select_target(hero, [other]) is other


def test_ties_are_broken_with_the_rng():
    a, b = make_character("A", faction="F2"), make_character("B", faction="F2")
    hero = make_character("Hero")
    picks = {_combat(make_faction("F1", hero), make_faction("F2", a, b), rng=random.Random(s)).select_target(hero, [a, b]).name for s in range(20)}
    assert picks == {"A", "B"}


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError):
        make_character(targeting="bravest")
    with pytest.raises(ValueError):
        make_character(on_rout="hide")


def test_loader_applies_faction_defaults_and_member_overrides():
    member = {"name": "M", "health": 10, "M": 4, "CC": 30, "CT": 30, "F": 30, "E": 30, "I": 30, "Ag": 30,
              "Dex": 30, "Int": 30, "FM": 30, "Soc": 30, "inventory": []}
    data = [{"name": "F", "targeting": "weakest", "on_rout": "flee",
             "members": [dict(member, name="A"), dict(member, name="B", targeting="dangerous", on_rout="surrender")]}]
    a, b = create_characters(data, {})[0].members
    assert (a.targeting, a.on_rout) == ("weakest", "flee")
    assert (b.targeting, b.on_rout) == ("dangerous", "surrender")


# --- several factions ----------------------------------------------------------

def test_polygon_placement_has_equal_sides():
    points = Combat.starting_positions(3, 12)
    assert points[0] == (0.0, 0.0)
    import math
    sides = [math.dist(points[i], points[(i + 1) % 3]) for i in range(3)]
    assert all(abs(s - 12) < 1e-6 for s in sides)


def test_two_factions_face_each_other_along_x():
    assert Combat.starting_positions(2, 12) == [(0.0, 0.0), (12.0, 0.0)]


def test_three_way_fight_ends_with_a_single_faction():
    fighters = [make_faction(f"F{i}", make_character(f"C{i}", faction=f"F{i}", health=12, CC=40 + 15 * i)) for i in range(3)]
    winner, survivors, remaining, _ = _combat(*fighters).run_combat()
    assert winner is not None
    assert survivors == [winner.replace("F", "C")]
    assert list(remaining) == survivors


def test_third_faction_is_not_ignored():
    a = make_faction("F1", make_character("A", faction="F1", health=1, CC=1))
    b = make_faction("F2", make_character("B", faction="F2", health=1, CC=1))
    c = make_faction("F3", make_character("C", faction="F3", health=40, CC=90, I=90))
    winner, survivors, _, _ = _combat(a, b, c).run_combat()
    assert (winner, survivors) == ("F3", ["C"])


def test_simulation_metrics_cover_every_faction():
    factions = [make_faction(f"F{i}", make_character(f"C{i}", faction=f"F{i}", health=12)) for i in range(3)]
    sim = Simulation(factions, seed=3)
    metrics = sim.gather_metrics(sim.run_simulation(60))
    assert set(metrics["survival_probabilities"]) == {"F0", "F1", "F2"}
    assert sum(metrics["survival_probabilities"].values()) + metrics["draws"] / 60 == pytest.approx(1)


# --- morale --------------------------------------------------------------------

def test_no_morale_check_without_on_rout():
    c = make_character("C", health=10)
    c.health = 1
    combat = _combat(make_faction("F1", c), make_faction("F2", make_character("D", faction="F2")))
    combat.resolve_turn(c)
    assert "rout" not in [e["action"] for e in combat.action_log]


def test_wounded_character_flees_on_a_failed_cool_test():
    c = make_character("C", health=10, FM=30, on_rout="flee")
    c.health = 2
    combat = _combat(make_faction("F1", c), make_faction("F2", make_character("D", faction="F2")), rng=ScriptedRng([80]))
    combat.resolve_turn(c)
    assert c.status == "fled" and not c.is_active() and c.is_alive()
    assert combat.action_log[-1]["details"]["trigger"] == "wounded"
    assert combat.determine_routed() == {"C": "fled"}


def test_wounded_character_holds_on_a_passed_cool_test_and_is_not_retested():
    c = make_character("C", health=10, FM=60, on_rout="flee")
    c.health = 2
    combat = _combat(make_faction("F1", c), make_faction("F2", make_character("D", faction="F2")), distance=30)
    combat.rng = ScriptedRng([20])
    combat.resolve_turn(c)
    assert c.status is None and "wounded" in c.morale_checked
    combat.rng = ScriptedRng([])  # a second test would pop from an empty list
    combat.resolve_turn(c)


def test_surrender_is_a_distinct_outcome():
    c = make_character("C", health=10, FM=10, on_rout="surrender")
    c.health = 1
    combat = _combat(make_faction("F1", c), make_faction("F2", make_character("D", faction="F2")), rng=ScriptedRng([90]))
    combat.resolve_turn(c)
    assert c.status == "surrendered"


def test_healthy_character_is_not_tested():
    c = make_character("C", health=10, on_rout="flee")
    combat = _combat(make_faction("F1", c), make_faction("F2", make_character("D", faction="F2")), distance=30)
    combat.resolve_turn(c)
    assert c.morale_checked == set()


def test_losing_half_the_faction_triggers_a_test():
    a = make_character("A", on_rout="flee", FM=10)
    b = make_character("B", faction="F1")
    b.health = 0
    combat = _combat(make_faction("F1", a, b), make_faction("F2", make_character("D", faction="F2")), rng=ScriptedRng([99]))
    combat.resolve_turn(a)
    assert a.status == "fled"
    assert combat.action_log[-1]["details"]["trigger"] == "outnumbered"


def test_a_routed_side_loses_and_its_members_still_count_as_survivors():
    coward = make_character("Coward", health=10, FM=1, on_rout="flee", I=50)
    coward.health = 1
    brute = make_character("Brute", faction="F2", health=30, CC=60, I=10)
    combat = _combat(make_faction("F1", coward), make_faction("F2", brute), rng=ScriptedRng([99]))
    winner, survivors, remaining, _ = combat.run_combat()
    assert winner == "F2"
    assert set(survivors) == {"Coward", "Brute"}
    assert remaining["Coward"] == 1


def test_routed_characters_are_not_targeted():
    coward = make_character("Coward", faction="F1")
    coward.status = "fled"
    hero = make_character("Hero", faction="F2")
    combat = _combat(make_faction("F1", coward), make_faction("F2", hero))
    assert combat.living_enemies(hero) == []


def test_metrics_report_survival_and_rout_of_the_losing_side():
    coward = make_character("Coward", health=10, FM=1, on_rout="flee", I=50)
    coward.health = 1
    brute = make_character("Brute", faction="F2", health=30, CC=60, I=10)
    sim = Simulation([make_faction("F1", coward), make_faction("F2", brute)], seed=1)
    results = [{"winner": "F2", "survivors": ["Coward", "Brute"], "remaining_health": {"Coward": 1, "Brute": 20},
                "routed": {"Coward": "fled"}, "action_log": []}]
    metrics = sim.gather_metrics(results)
    assert metrics["individual_survival_probabilities"] == {"Coward": 1, "Brute": 1}
    assert metrics["individual_rout_probabilities"] == {"Coward": 1, "Brute": 0}
    assert metrics["average_remaining_health"] == {"F1": 0, "F2": 20}
