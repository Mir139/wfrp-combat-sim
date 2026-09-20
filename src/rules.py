"""WFRP 4e test resolution (simplified where noted)."""
from src.utils import roll_d100

ENGAGED_DISTANCE = 2  # yards; enemies this close are in melee


def is_double(roll):
    return roll == 100 or (roll >= 11 and roll % 11 == 0)


def make_test(target, rng=None, modifier=0):
    """Roll d100 against `target` (+ modifier). Rolls <= 5 always succeed, >= 96 always fail.

    SL is the tens-digit difference, clamped so a success never has a negative SL
    and a failure never has a positive one. A success double is a critical, a failed double a fumble.
    """
    roll = roll_d100(rng)
    target = max(target + modifier, 0)
    if roll <= 5:
        success = True
    elif roll >= 96:
        success = False
    else:
        success = roll <= target
    sl = target // 10 - roll // 10
    sl = max(sl, 0) if success else min(sl, 0)
    double = is_double(roll)
    return {
        "roll": roll,
        "target": target,
        "success": success,
        "sl": sl,
        "critical": success and double,
        "fumble": not success and double,
    }


def resolve_opposed(attack, defense):
    """Return (attacker_wins, sl_difference).

    The attacker must succeed. Against a failed defense the difference includes the defender's
    negative SL. On equal SL the higher target number wins; if equal too, the defender wins.
    """
    if not attack["success"]:
        return False, 0
    if not defense["success"]:
        return True, attack["sl"] - defense["sl"]
    if attack["sl"] != defense["sl"]:
        return attack["sl"] > defense["sl"], max(attack["sl"] - defense["sl"], 0)
    return attack["target"] > defense["target"], 0


def range_modifier(distance, weapon_range):
    """To-hit modifier by range band, or None when the target is out of range."""
    if distance <= ENGAGED_DISTANCE:
        return 40
    if distance <= weapon_range / 2:
        return 20
    if distance <= weapon_range:
        return 0
    if distance <= weapon_range * 2:
        return -10
    if distance <= weapon_range * 3:
        return -20
    return None
