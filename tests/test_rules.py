import random

from src.combat import Combat
from src.loader import create_characters, load_inventory, load_simulation_config
from src.rules import make_test, range_modifier, resolve_opposed
from src.simulation import Simulation
from tests.helpers import ScriptedRng, make_armor, make_character, make_faction, make_ranged


# --- armor -----------------------------------------------------------------

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


def test_location_is_always_a_known_zone():
    c = make_character()
    for roll in range(1, 101):
        assert c.determine_location(roll) is not None


def test_hit_location_reverses_the_two_digits_of_the_roll():
    c = make_character()
    assert c.determine_location(21) == "Left Arm"   # 12
    assert c.determine_location(10) == "Head"       # 01
    assert c.determine_location(5) == "Body"        # 05 -> 50
    assert c.determine_location(1) == "Left Arm"    # 01 -> 10
    assert c.determine_location(100) == "Right Leg"


def test_hit_location_frequencies_match_the_table():
    c = make_character()
    counts = {}
    for roll in range(1, 101):
        location = c.determine_location(roll)
        counts[location] = counts.get(location, 0) + 1
    assert counts == {"Head": 9, "Left Arm": 15, "Right Arm": 20, "Body": 35, "Left Leg": 10, "Right Leg": 11}


# --- tests and opposed tests -----------------------------------------------

def test_success_and_sl():
    t = make_test(45, ScriptedRng([21]))
    assert (t["success"], t["sl"]) == (True, 2)


def test_rolls_up_to_5_always_succeed_and_from_96_always_fail():
    assert make_test(1, ScriptedRng([4]))["success"]
    assert not make_test(100, ScriptedRng([96]))["success"]


def test_success_sl_never_negative_and_failure_sl_never_positive():
    assert make_test(1, ScriptedRng([3]))["sl"] == 0
    assert make_test(100, ScriptedRng([97]))["sl"] == 0


def test_doubles_are_criticals_on_success_and_fumbles_on_failure():
    assert make_test(50, ScriptedRng([22]))["critical"]
    assert make_test(50, ScriptedRng([88]))["fumble"]
    assert make_test(50, ScriptedRng([100]))["fumble"]
    assert not make_test(50, ScriptedRng([23]))["critical"]


def test_modifier_shifts_the_target():
    assert make_test(40, ScriptedRng([45]), modifier=10)["success"]
    assert not make_test(40, ScriptedRng([45]), modifier=-10)["success"]


def _test(success, sl, target):
    return {"success": success, "sl": sl, "target": target}


def test_opposed_tie_goes_to_higher_target_then_defender():
    assert resolve_opposed(_test(True, 2, 60), _test(True, 2, 50)) == (True, 0)
    assert resolve_opposed(_test(True, 2, 50), _test(True, 2, 60)) == (False, 0)
    assert resolve_opposed(_test(True, 2, 50), _test(True, 2, 50)) == (False, 0)


def test_opposed_failed_attack_never_wins():
    assert resolve_opposed(_test(False, -1, 50), _test(False, -5, 50))[0] is False


def test_opposed_failed_defense_adds_to_the_difference():
    assert resolve_opposed(_test(True, 2, 50), _test(False, -3, 50)) == (True, 5)


# --- melee ------------------------------------------------------------------

def test_melee_damage_is_bf_weapon_and_sl_difference_minus_soak():
    attacker = make_character("A", CC=50, F=40, weapon_damage=4)
    defender = make_character("D", faction="F2", CC=30, E=30, health=30)
    # attacker rolls 21 (SL 3); defender rolls 91 and fails (SL -6): difference 9
    result = attacker.melee_attack(defender, ScriptedRng([21, 91]))
    assert result["damage"] == 4 + 4 + 9 - 3
    assert defender.health == 30 - result["damage"]


def test_defender_winning_the_opposed_test_takes_no_damage():
    attacker = make_character("A", CC=50)
    defender = make_character("D", faction="F2", CC=90, health=20)
    result = attacker.melee_attack(defender, ScriptedRng([91, 1]))
    assert result["damage"] == 0
    assert defender.health == 20


def test_defender_dodges_when_agility_beats_weapon_skill():
    defender = make_character("D", CC=30, Ag=60)
    assert defender.defense() == (60, "dodge", 0)


def test_defensive_weapon_gives_a_parry_sl_bonus():
    assert make_character(weapon_attributes=["Defensive"]).defense() == (50, "parry", 1)
    assert make_character().defense() == (50, "parry", 0)


def test_precise_weapon_adds_sl_to_a_successful_attack():
    def damage(attributes):
        attacker = make_character("A", CC=50, weapon_attributes=attributes)
        defender = make_character("D", faction="F2", CC=30, health=50)
        return attacker.melee_attack(defender, ScriptedRng([41, 91]))["damage"]

    assert damage(["Précise"]) - damage([]) == 1


def test_critical_ignores_armor_and_causes_bleeding_and_stun():
    attacker = make_character("A", CC=60, weapon_damage=4)
    defender = make_character("D", faction="F2", CC=30, health=50)
    defender.inventory.add_item(make_armor(3))
    result = attacker.melee_attack(defender, ScriptedRng([22, 91]))
    assert result["critical"]
    assert result["damage"] == 4 + 4 + (6 - 2 + 6) - 3  # BF + weapon + SL diff - BE, no armor
    assert defender.bleeding == 1 and defender.stunned


def test_melee_fumble_knocks_the_attacker_prone():
    attacker = make_character("A", CC=40)
    defender = make_character("D", faction="F2")
    result = attacker.melee_attack(defender, ScriptedRng([88, 50]))
    assert result["fumble"] and attacker.prone and result["damage"] == 0


def test_stunned_and_prone_penalties_apply():
    attacker = make_character("A", CC=50)
    attacker.stunned = True
    assert attacker.state_modifier() == -10
    attacker.prone = True
    assert attacker.state_modifier() == -30
    assert attacker.state_modifier(melee=False) == -10


def test_pummelling_weapon_stuns_on_a_hit():
    attacker = make_character("A", CC=50, weapon_attributes=["Assommante"])
    defender = make_character("D", faction="F2", CC=30, health=50)
    attacker.melee_attack(defender, ScriptedRng([41, 91]))
    assert defender.stunned


def test_unarmed_uses_strength_bonus_only():
    attacker = make_character("A", CC=50, F=40, unarmed=True)
    defender = make_character("D", faction="F2", CC=30, E=30, health=50)
    result = attacker.melee_attack(defender, ScriptedRng([41, 91]))
    assert result["damage"] == 4 + 7 - 3  # BF + SL difference (1 - -6) - BE


# --- ranged -----------------------------------------------------------------

def test_range_bands():
    assert range_modifier(1, 20) == 40
    assert range_modifier(8, 20) == 20
    assert range_modifier(20, 20) == 0
    assert range_modifier(35, 20) == -10
    assert range_modifier(60, 20) == -20
    assert range_modifier(61, 20) is None


def test_ranged_damage_scales_with_sl():
    def damage(roll):
        shooter = make_character("S", CT=50)
        target = make_character("T", faction="F2", E=30, health=50)
        return shooter.ranged_attack(target, make_ranged(range=20), 20, ScriptedRng([roll]))["damage"]

    assert damage(41) == 8 - 3 + 1
    assert damage(11) == 8 - 3 + 4


def test_ranged_miss_does_no_damage():
    shooter = make_character("S", CT=30)
    target = make_character("T", faction="F2", health=50)
    result = shooter.ranged_attack(target, make_ranged(), 20, ScriptedRng([80]))
    assert result["damage"] == 0 and target.health == 50


def test_ranged_weapon_with_bf_damage_adds_strength_bonus():
    shooter = make_character("S", CT=50, F=40)
    target = make_character("T", faction="F2", E=30, health=50)
    bow = make_ranged("Arc", range=50, damage=3, attributes=(), damage_BF=True)
    assert shooter.ranged_attack(target, bow, 50, ScriptedRng([41]))["damage"] == 3 + 4 + 1 - 3


def test_thrown_weapon_range_is_a_multiple_of_bf():
    knife = make_ranged("Couteau", range=2, damage=2, attributes=(), range_BF=True)
    assert knife.effective_range(4) == 8


def test_shield_absorbs_ranged_damage_only():
    shooter = make_character("S", CT=50)
    target = make_character("T", faction="F2", E=30, health=50, weapon_attributes=["Protectrice 2"])
    assert shooter.ranged_attack(target, make_ranged(), 20, ScriptedRng([41]))["damage"] == 8 + 1 - 3 - 2


def test_firing_empties_the_weapon_until_reloaded():
    pistol = make_ranged(attributes=("Pistolet", "Recharge 2"))
    assert pistol.is_ready()
    pistol.fire()
    assert not pistol.is_ready()
    assert not pistol.reload_step()
    assert pistol.reload_step()
    assert pistol.is_ready()


def test_bow_without_reload_never_runs_dry():
    bow = make_ranged("Arc", attributes=())
    for _ in range(5):
        bow.fire()
    assert bow.is_ready()


def test_repeating_weapon_fires_its_magazine_before_reloading():
    gun = make_ranged(attributes=("Recharge 4", "Répétition 4"))
    for _ in range(3):
        gun.fire()
        assert gun.is_ready()
    gun.fire()
    assert not gun.is_ready()


def test_ranged_fumble_jams_the_weapon():
    shooter = make_character("S", CT=30)
    pistol = make_ranged(attributes=("Recharge 1",))
    shooter.ranged_attack(make_character("T", faction="F2"), pistol, 20, ScriptedRng([88]))
    assert not pistol.is_ready()


def test_two_pistols_can_both_be_used_before_reloading():
    c = make_character("Else", unarmed=True)
    c.inventory.add_item(make_ranged())
    c.inventory.add_item(make_ranged())
    first = c.ready_ranged_weapon()
    first.fire()
    second = c.ready_ranged_weapon()
    assert second is not None and second is not first
    second.fire()
    assert c.ready_ranged_weapon() is None and c.weapon_to_reload() is not None


# --- weapon choice ----------------------------------------------------------

def test_combat_mode_follows_skills_and_equipment():
    assert make_character().combat_mode() == "melee"
    archer = make_character(unarmed=True)
    archer.inventory.add_item(make_ranged())
    assert archer.combat_mode() == "ranged"
    both = make_character(CC=30, CT=60)
    both.inventory.add_item(make_ranged())
    assert both.combat_mode() == "ranged"
    both.behavior = "melee"
    assert both.combat_mode() == "melee"


def test_forced_ranged_behavior_without_ranged_weapon_falls_back_to_melee():
    assert make_character(behavior="ranged").combat_mode() == "melee"


def test_best_melee_weapon_is_the_harmful_one_with_most_damage():
    c = make_character(weapon_damage=4)
    c.inventory.add_item(make_character(weapon_damage=9).melee_weapon())
    assert c.melee_weapon().base_damage() == 9


# --- combat: movement, range, states ----------------------------------------

def _duel(attacker, defender, distance=12, rng=None):
    return Combat([make_faction("F1", attacker), make_faction("F2", defender)], rng or random.Random(0), distance)


def test_melee_fighter_far_away_runs_without_attacking():
    a, d = make_character("A", M=4), make_character("D", faction="F2")
    combat = _duel(a, d, distance=30)
    combat.resolve_turn(a)
    assert [e["action"] for e in combat.action_log] == ["run"]
    assert combat.distance(a, d) == 30 - 16


def test_melee_fighter_within_walking_distance_engages_and_attacks():
    a, d = make_character("A", M=4), make_character("D", faction="F2")
    combat = _duel(a, d, distance=8)
    combat.resolve_turn(a)
    assert [e["action"] for e in combat.action_log] == ["move", "engage", "attack"]
    assert combat.distance(a, d) == 1


def test_archer_shoots_from_where_they_stand_when_in_range():
    archer = make_character("A", unarmed=True)
    archer.inventory.add_item(make_ranged(range=20))
    d = make_character("D", faction="F2")
    combat = _duel(archer, d, distance=12)
    combat.resolve_turn(archer)
    assert [e["action"] for e in combat.action_log] == ["ranged_attack"]
    assert archer.position == (0.0, 0.0)


def test_archer_out_of_range_walks_closer_then_shoots():
    archer = make_character("A", unarmed=True, M=4)
    archer.inventory.add_item(make_ranged(range=10))
    d = make_character("D", faction="F2")
    combat = _duel(archer, d, distance=30)
    combat.resolve_turn(archer)
    assert [e["action"] for e in combat.action_log] == ["move", "ranged_attack"]
    assert combat.distance(archer, d) == 22
    assert combat.action_log[-1]["details"]["range_modifier"] == -20


def test_archer_cannot_shoot_beyond_triple_range():
    archer = make_character("A", unarmed=True, M=4)
    archer.inventory.add_item(make_ranged(range=10))
    d = make_character("D", faction="F2")
    combat = _duel(archer, d, distance=50)
    combat.resolve_turn(archer)
    assert [e["action"] for e in combat.action_log] == ["move"]


def test_shooter_with_empty_weapons_reloads():
    archer = make_character("A", unarmed=True)
    archer.inventory.add_item(make_ranged())
    archer.ranged_weapons()[0].fire()
    combat = _duel(archer, make_character("D", faction="F2"))
    combat.resolve_turn(archer)
    assert combat.action_log[-1]["action"] == "reload"
    assert archer.ranged_weapons()[0].is_ready()


def test_shooter_fires_pistol_point_blank_when_engaged():
    a = make_character("A", CT=60, CC=20)
    a.inventory.add_item(make_ranged())
    combat = _duel(a, make_character("D", faction="F2"), distance=1)
    combat.resolve_turn(a)
    assert combat.action_log[-1]["action"] == "ranged_attack"
    assert combat.action_log[-1]["details"]["range_modifier"] == 40


def test_prone_character_spends_their_move_standing_up():
    a, d = make_character("A", M=4), make_character("D", faction="F2")
    a.prone = True
    combat = _duel(a, d, distance=8)
    combat.resolve_turn(a)
    assert [e["action"] for e in combat.action_log] == ["stand_up"]
    assert not a.prone


def test_bleeding_costs_health_each_turn_and_can_kill():
    a, d = make_character("A", health=2), make_character("D", faction="F2")
    a.bleeding = 1
    combat = _duel(a, d, distance=1)
    combat.resolve_turn(a)
    assert a.health <= 1
    a.health = 1
    combat.resolve_turn(a)
    assert not a.is_alive()
    assert combat.action_log[-1]["action"] == "bleed"


def test_stun_ends_after_a_successful_endurance_test():
    a, d = make_character("A", E=50), make_character("D", faction="F2")
    a.stunned = True
    combat = _duel(a, d, distance=1, rng=ScriptedRng([50, 91, 10]))  # attack, defense, endurance test
    combat.resolve_turn(a)
    assert not a.stunned


# --- full combats and simulation ---------------------------------------------

def test_combat_is_deterministic_with_a_seed():
    def run(seed):
        a = make_faction("F1", make_character("A", health=15))
        b = make_faction("F2", make_character("B", faction="F2", health=15))
        return Combat([a, b], random.Random(seed)).run_combat()

    assert run(42) == run(42)


def test_remaining_health_is_keyed_by_name_not_position():
    tank = make_character("Tank", health=1, CC=1)
    hero = make_character("Hero", health=50, CC=99, I=40)
    foe = make_character("Foe", faction="F2", health=50, CC=1, I=10)
    tank.health = 0
    combat = Combat([make_faction("F1", tank, hero), make_faction("F2", foe)], random.Random(0))
    winner, survivors, remaining, _ = combat.run_combat()
    assert winner == "F1"
    assert survivors == ["Hero"]
    assert remaining == {"Hero": hero.health}


def test_draw_does_not_crash():
    a = make_character("A", health=10)
    b = make_character("B", faction="F2", health=10)
    a.health = 0
    b.health = 0
    combat = Combat([make_faction("F1", a), make_faction("F2", b)])
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
    assert len(else_.ranged_weapons()) == 2


def test_simulation_with_seed_is_reproducible():
    inventory = load_inventory("db/db.json")
    config = load_simulation_config("sim/job1.json")
    factions = create_characters(config["factions"], inventory)
    r1 = [r["winner"] for r in Simulation(factions, seed=7).run_simulation(30)]
    r2 = [r["winner"] for r in Simulation(factions, seed=7).run_simulation(30)]
    assert r1 == r2
