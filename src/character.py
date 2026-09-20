from src.utils import calculate_dr, roll_d100
from math import floor
from src.inventory import Inventory  # Import the Inventory class

LOCATIONS = ["Head", "Left Arm", "Right Arm", "Body", "Left Leg", "Right Leg"]

class Character:
    def __init__(self, name, health, M, CC, CT, F, E, I, Ag, Dex, Int, FM, Soc, faction):
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
        self.inventory = Inventory()  # Initialize inventory as an Inventory object
        self.faction = faction
        self.engaged = False

        if self.CC > self.CT:
            self.prefers_melee = True
        else:
            self.prefers_melee = False

    def equip_weapon(self, weapon_name):
        weapon_type = self.inventory.equip_weapon(weapon_name)
        if weapon_type == 'melee_weapons':
            self.prefers_melee = True
        elif weapon_type == 'ranged_weapons':
            self.prefers_melee = False
    
    @property
    def PA(self):
        """Armor points per location, ordered as LOCATIONS, summed over worn armors."""
        return self.inventory.armor_points()

    def take_damage(self, damage, location):
        PA = self.PA[LOCATIONS.index(location)]
        damage_taken = max(1, damage - (self.E // 10) - PA)
        self.health -= damage_taken
        return damage_taken

    def attack_enemy(self, enemy, rng=None):
        if self.engaged:
            attacker_roll = roll_d100(rng)
            enemy_roll = roll_d100(rng)
            attacker_dr = calculate_dr(attacker_roll, self.CC)
            enemy_dr = calculate_dr(enemy_roll, enemy.CC)
            if attacker_dr > enemy_dr:
                damage, location = self.apply_damage(enemy, attacker_roll, attacker_dr)
                return {"attack_roll": attacker_roll, "damage": damage, "enemy_roll": enemy_roll, "enemy_dr": enemy_dr, "attack_dr": attacker_dr, "location": location, "type": "melee"}
            else:
                return {"attack_roll": attacker_roll, "damage": 0, "enemy_roll": enemy_roll, "enemy_dr": enemy_dr, "attack_dr": attacker_dr, "type": "melee"}
        else:
            attacker_roll = roll_d100(rng)
            if attacker_roll <= self.CT:
                damage, location = self.apply_damage(enemy, attacker_roll, 0)
                return {"attack_roll": attacker_roll, "damage": damage, "location": location, "type": "ranged"}
            else:
                return {"attack_roll": attacker_roll, "damage": 0, "type": "ranged"}

    def calculate_damage(self, weapon, dr):
        weapon_type = self.inventory.get_item_type(weapon)
        if weapon is None:
            damage = self.BF() + dr
        elif weapon_type == 'melee_weapons':
            damage = self.BF() + int(weapon.damage) + dr
        elif weapon_type == 'ranged_weapons':
            if weapon.damage_BF:
                damage = self.BF() + int(weapon.damage.replace('+BF', '').strip()) + dr
            else:
                damage = int(weapon.damage) + dr
        return damage

    def apply_damage(self, enemy, roll, dr):
        location = self.determine_location(roll)
        weapon = self.inventory.get_equipped_weapon()
        damage = self.calculate_damage(weapon, dr)
        return enemy.take_damage(damage, location), location

    def determine_location(self, roll):
        if roll == 100:
            return "Right Leg"
        else:
            inverted_roll = int(str(roll)[::-1])
            if 1 <= inverted_roll <= 9:
                return "Head"
            elif 10 <= inverted_roll <= 24:
                return "Left Arm"
            elif 25 <= inverted_roll <= 44:
                return "Right Arm"
            elif 45 <= inverted_roll <= 79:
                return "Body"
            elif 80 <= inverted_roll <= 89:
                return "Left Leg"
            elif 90 <= inverted_roll <= 99:
                return "Right Leg"

    def is_alive(self):
        return self.health > 0
    
    def BF(self):
        return floor(self.F/10)
    
    def BE(self):
        return floor(self.E/10)