import random

from src.combat import Combat
from src.loader import create_characters, load_inventory, load_simulation_config
from src.simulation import Simulation
from tests.helpers import ScriptedRng, make_armor, make_character, make_faction


def test_armor_points_default_to_zero():
    assert make_character().PA == [0] * 6


def test_armor_reduces_damage_by_its_points():
    target = make_character(E=30)  # BE 3
    unarmored = target.take_damage(10, "Body")
    target.inventory.add_item(make_armor(3))
    armored = target.take_damage(10, "Body")
    assert unarmored - armored == 3


def test_armor_applies_to_every_location_when_tous():
    c = make_character()
    c.inventory.add_item(make_armor(2))
    assert c.PA == [2] * 6


def test_armor_on_one_location_only():
    c = make_character()
    c.inventory.add_item(make_armor(2, ["Tête"]))
    assert c.PA == [2, 0, 0, 0, 0, 0]


def test_damage_is_at_least_one():
    c = make_character(E=90)
    c.inventory.add_item(make_armor(3))
    assert c.take_damage(1, "Head") == 1


def test_melee_attack_deals_bf_weapon_and_dr_minus_soak():
    attacker = make_character("A", CC=50, F=40, weapon_damage=4)
    defender = make_character("D", faction="F2", CC=30, E=30, health=20)
    # attacker rolls 21 -> DR 5-2=3 ; defender rolls 91 -> DR 3-9=-6
    attacker.engaged = True
    result = attacker.attack_enemy(defender, ScriptedRng([21, 91]))
    # damage = BF 4 + weapon 4 + DR 3 = 11 ; minus BE 3 = 8
    assert result["damage"] == 8
    assert defender.health == 12


def test_defender_winning_the_opposed_test_takes_no_damage():
    attacker = make_character("A", CC=50)
    defender = make_character("D", faction="F2", CC=90, health=20)
    attacker.engaged = True
    result = attacker.attack_enemy(defender, ScriptedRng([91, 1]))
    assert result["damage"] == 0
    assert defender.health == 20


def test_location_is_always_a_known_zone():
    c = make_character()
    for roll in range(1, 101):
        assert c.determine_location(roll) is not None


def test_combat_is_deterministic_with_a_seed():
    def run(seed):
        a = make_faction("F1", make_character("A", health=15))
        b = make_faction("F2", make_character("B", faction="F2", health=15))
        return Combat(a, b, random.Random(seed)).run_combat()

    assert run(42) == run(42)


def test_remaining_health_is_keyed_by_name_not_position():
    tank = make_character("Tank", health=1, CC=1)       # dies at once
    hero = make_character("Hero", health=50, CC=99, I=40)
    foe = make_character("Foe", faction="F2", health=50, CC=1, I=10)
    combat = Combat(make_faction("F1", tank, hero), make_faction("F2", foe), random.Random(0))
    tank.health = 0
    winner, survivors, remaining, _ = combat.run_combat()
    assert winner == "F1"
    assert survivors == ["Hero"]
    assert remaining == {"Hero": hero.health}


def test_draw_does_not_crash():
    a = make_character("A", health=10)
    b = make_character("B", faction="F2", health=10)
    a.health = 0
    b.health = 0
    combat = Combat(make_faction("F1", a), make_faction("F2", b))
    assert combat.run_combat()[:3] == (None, [], {})


def test_gather_metrics_attributes_health_to_the_right_survivor():
    tank = make_character("Tank", health=1, CC=1)
    hero = make_character("Hero", health=50, CC=99, I=40)
    foe = make_character("Foe", faction="F2", health=50, CC=1, I=10)
    sim = Simulation([make_faction("F1", tank, hero), make_faction("F2", foe)], seed=1)
    results = [{"winner": "F1", "survivors": ["Hero"], "remaining_health": {"Hero": 7}, "action_log": []}]
    metrics = sim.gather_metrics(results)
    assert metrics["individual_average_remaining_health"]["Hero"] == 7
    assert metrics["individual_average_remaining_health"]["Tank"] == 0
    assert metrics["individual_survival_probabilities"] == {"Tank": 0, "Hero": 1, "Foe": 0}


def test_loader_applies_armor_from_db():
    inventory = load_inventory("db/db.json")
    config = load_simulation_config("sim/job1.json")
    factions = create_characters(config["factions"], inventory)
    else_ = next(m for f in factions for m in f.members if m.name == "Else Sigloben")
    assert else_.PA == [1] * 6


def test_simulation_with_seed_is_reproducible():
    inventory = load_inventory("db/db.json")
    config = load_simulation_config("sim/job1.json")
    factions = create_characters(config["factions"], inventory)
    r1 = [r["winner"] for r in Simulation(factions, seed=7).run_simulation(30)]
    r2 = [r["winner"] for r in Simulation(factions, seed=7).run_simulation(30)]
    assert r1 == r2
