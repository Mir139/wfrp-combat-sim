import random
from utils import calculate_dr, roll_d100
from math import floor
from inventory import Inventory  # Import the Inventory class

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
        self.PA = [0,0,0,0,0,0]

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
    
    def take_damage(self, damage, location):
        if location == "Head":
            PA = self.PA[0]
        elif location == "Left Arm":
            PA = self.PA[1]
        elif location == "Right Arm":
            PA = self.PA[2]
        elif location == "Body":
            PA = self.PA[3]
        elif location == "Left Leg":
            PA = self.PA[4]
        elif location == "Right Leg":
            PA = self.PA[5]
            
        damage_taken = max(1, damage - (self.E // 10) - PA)
        self.health -= damage_taken

    def attack_enemy(self, enemy):
        if self.engaged:
            attacker_roll = roll_d100()
            enemy_roll = roll_d100()
            attacker_dr = calculate_dr(attacker_roll, self.CC)
            enemy_dr = calculate_dr(enemy_roll, enemy.CC)
            if attacker_dr > enemy_dr:
                self.apply_damage(enemy, attacker_roll, attacker_dr)
        else:
            attacker_roll = roll_d100()
            if attacker_roll <= self.CT:
                self.apply_damage(enemy, attacker_roll, 0)

    def calculate_damage(self, weapon, dr):
        weapon_type = self.inventory.get_item_type(weapon)
        if weapon_type == 'melee_weapons':
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
        enemy.take_damage(damage, location)

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