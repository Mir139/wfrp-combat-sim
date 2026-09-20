from math import floor

from src.inventory import Inventory, MeleeWeapon, RangedWeapon
from src.rules import make_test, resolve_opposed, range_modifier

LOCATIONS = ["Head", "Left Arm", "Right Arm", "Body", "Left Leg", "Right Leg"]

STUNNED_PENALTY = -10
PRONE_PENALTY = -20
PRONE_TARGET_BONUS = 20


class Character:
    def __init__(self, name, health, M, CC, CT, F, E, I, Ag, Dex, Int, FM, Soc, faction, behavior=None):
        self.name = name
        self.health = health
        self.M = M
        self.CC = CC
        self.CT = CT
        self.F = F
        self.E = E
        self.I = I
        self.Ag = Ag
        self.Dex = Dex
        self.Int = Int
        self.FM = FM
        self.Soc = Soc
        self.inventory = Inventory()
        self.faction = faction
        self.behavior = behavior  # "melee", "ranged" or None (decided from the inventory)
        self.position = 0  # yards along the line between the two sides
        self.target = None
        self.bleeding = 0
        self.stunned = False
        self.prone = False

    @property
    def PA(self):
        """Armor points per location, ordered as LOCATIONS, summed over worn armors."""
        return self.inventory.armor_points()

    def is_alive(self):
        return self.health > 0

    def BF(self):
        return floor(self.F / 10)

    def BE(self):
        return floor(self.E / 10)

    # --- equipment choices -------------------------------------------------

    def melee_weapons(self):
        return [i for i in self.inventory.get_items() if isinstance(i, MeleeWeapon)]

    def ranged_weapons(self):
        return [i for i in self.inventory.get_items() if isinstance(i, RangedWeapon)]

    def melee_weapon(self):
        """Best melee weapon: harmful ones first, then highest damage. None means unarmed."""
        weapons = self.melee_weapons()
        if not weapons:
            return None
        return max(weapons, key=lambda w: (not w.has_attribute("Inoffensive"), w.base_damage()))

    def ready_ranged_weapon(self, pistol_only=False):
        ready = [w for w in self.ranged_weapons() if w.is_ready() and (not pistol_only or w.has_attribute("Pistolet"))]
        if not ready:
            return None
        return max(ready, key=lambda w: w.base_damage())

    def weapon_to_reload(self):
        pending = [w for w in self.ranged_weapons() if not w.is_ready()]
        if not pending:
            return None
        return max(pending, key=lambda w: w.reload_progress)

    def combat_mode(self):
        """'ranged' or 'melee': explicit behavior, else ranged when the ranged skill is the better one."""
        if self.behavior == "melee":
            return "melee"
        if self.behavior == "ranged" and self.ranged_weapons():
            return "ranged"
        if not self.ranged_weapons():
            return "melee"
        if self.behavior == "ranged" or not self.melee_weapons():
            return "ranged"
        return "ranged" if self.CT > self.CC else "melee"

    def shield_rating(self):
        return max([w.attribute_rating("Protectrice") for w in self.melee_weapons()], default=0)

    # --- tests -------------------------------------------------------------

    def state_modifier(self, melee=True):
        modifier = STUNNED_PENALTY if self.stunned else 0
        if melee and self.prone:
            modifier += PRONE_PENALTY
        return modifier

    def defense(self):
        """Best defensive option: (target number, kind, bonus SL). Parry uses CC, dodge uses Ag."""
        if self.CC >= self.Ag:
            defensive = any(w.has_attribute("Defensive", "Défensive") for w in self.melee_weapons())
            return self.CC, "parry", 1 if defensive else 0
        return self.Ag, "dodge", 0

    def endurance_test(self, rng=None):
        return make_test(self.E, rng)["success"]

    # --- attacks -----------------------------------------------------------

    def melee_attack(self, enemy, rng=None):
        weapon = self.melee_weapon()
        modifier = self.state_modifier()
        if enemy.prone:
            modifier += PRONE_TARGET_BONUS
        attack = make_test(self.CC, rng, modifier)
        target, defense_kind, defense_bonus = enemy.defense()
        defense = make_test(target, rng, enemy.state_modifier())
        if attack["success"] and weapon:
            attack["sl"] = max(attack["sl"] + self._accuracy(weapon), 0)
        if defense["success"]:
            defense["sl"] += defense_bonus

        wins, sl_diff = resolve_opposed(attack, defense)
        result = {
            "type": "melee",
            "attack_roll": attack["roll"],
            "enemy_roll": defense["roll"],
            "attack_dr": attack["sl"],
            "enemy_dr": defense["sl"],
            "defense": defense_kind,
            "damage": 0,
            "critical": False,
            "fumble": attack["fumble"],
        }
        if attack["fumble"]:
            self.prone = True
        if wins:
            result["critical"] = attack["critical"]
            result["damage"], result["location"] = self._hit(enemy, weapon, attack["roll"], sl_diff, attack["critical"])
        return result

    def ranged_attack(self, enemy, weapon, distance, rng=None):
        range_mod = range_modifier(distance, weapon.effective_range(self.BF()))
        weapon.fire()
        attack = make_test(self.CT, rng, self.state_modifier(melee=False) + range_mod)
        if attack["success"]:
            attack["sl"] = max(attack["sl"] + self._accuracy(weapon), 0)
        result = {
            "type": "ranged",
            "weapon": weapon.name,
            "attack_roll": attack["roll"],
            "attack_dr": attack["sl"],
            "distance": distance,
            "range_modifier": range_mod,
            "damage": 0,
            "critical": False,
            "fumble": attack["fumble"],
        }
        if attack["fumble"]:
            weapon.jam()
        if attack["success"]:
            result["critical"] = attack["critical"]
            result["damage"], result["location"] = self._hit(enemy, weapon, attack["roll"], attack["sl"], attack["critical"], ranged=True)
        return result

    @staticmethod
    def _accuracy(weapon):
        return (1 if weapon.has_attribute("Précise") else 0) - (1 if weapon.has_attribute("Imprécise") else 0)

    def _hit(self, enemy, weapon, roll, sl, critical, ranged=False):
        """Resolve a landed attack. A critical ignores armor, and makes the target bleed and stunned."""
        location = self.determine_location(roll)
        damage = self.calculate_damage(weapon, sl)
        shield = enemy.shield_rating() if ranged else 0
        dealt = enemy.take_damage(damage, location, ignore_armor=critical, extra_pa=shield)
        if critical:
            enemy.bleeding += 1
            enemy.stunned = True
        if weapon and weapon.has_attribute("Assommante"):
            enemy.stunned = True
        return dealt, location

    def calculate_damage(self, weapon, sl):
        if weapon is None:
            return self.BF() + sl
        adds_bf = isinstance(weapon, MeleeWeapon) or weapon.damage_BF
        return weapon.base_damage() + (self.BF() if adds_bf else 0) + sl

    def take_damage(self, damage, location, ignore_armor=False, extra_pa=0):
        armor = 0 if ignore_armor else self.PA[LOCATIONS.index(location)] + extra_pa
        damage_taken = max(1, damage - self.BE() - armor)
        self.health -= damage_taken
        return damage_taken

    def determine_location(self, roll):
        if roll == 100:
            return "Right Leg"
        inverted_roll = int(str(roll)[::-1])
        if inverted_roll <= 9:
            return "Head"
        elif inverted_roll <= 24:
            return "Left Arm"
        elif inverted_roll <= 44:
            return "Right Arm"
        elif inverted_roll <= 79:
            return "Body"
        elif inverted_roll <= 89:
            return "Left Leg"
        return "Right Leg"
