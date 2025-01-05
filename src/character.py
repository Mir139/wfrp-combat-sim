import random
from utils import calculate_dr, roll_d100
from math import floor
from inventory import Inventory  # Import the Inventory class

class Character:
    def __init__(self, name, health, M, CC, CT, F, E, I, Ag, Dex, Int, FM, Soc, faction):
        self.name = name
        self.health = health
        self.characteristics = {
            "M": M,
            "CC": CC,
            "CT": CT,
            "F": F,
            "E": E,
            "I": I,
            "Ag": Ag,
            "Dex": Dex,
            "Int": Int,
            "FM": FM,
            "Soc": Soc
        }
        self.skills = {}
        self.spells = []
        self.inventory = Inventory()  # Initialize inventory as an Inventory object
        self.faction = faction
        self.engaged = False
        self.PA = [0,0,0,0,0,0]
        self.target_selection_priority = "random"
        self.focused_spell = None

        if self.characteristics["CC"] > self.characteristics["CT"]:
            self.prefers_melee = True
        else:
            self.prefers_melee = False

    def set_skills(self, skills):
        if skills:
            self.skills = skills

    def get_skill(self, skill_name):
        return self.skills.get(skill_name, 0)
    
    def add_spell(self, spell):
        if spell:
            self.spells.append(spell)
            if self.prefers_melee and spell["damage"] != "none":
                self.prefers_melee = False

    def get_spell(self, spell_name):
        return self.spells.get(spell_name, 0)

    def set_target_selection_priority(self, method):
        if method:
            self.target_selection_priority = method
    
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
            
        damage_taken = max(1, damage - self.BE() - PA)
        self.health -= damage_taken
        return damage_taken

    def get_melee_attack(self):
        return self.characteristics["CC"]+self.get_skill("Corps à corps")
    
    def get_ranged_attack(self):
        return self.characteristics["CT"]+self.get_skill("Projectile")
    
    def attack_enemy(self, enemy, advantage_bonus_character, advantage_bonus_enemy):
        if self.engaged:
            attacker_roll = roll_d100()
            enemy_roll = roll_d100()
            attacker_dr = calculate_dr(attacker_roll, self.get_melee_attack() + advantage_bonus_character)
            enemy_dr = calculate_dr(enemy_roll, enemy.get_melee_attack() + advantage_bonus_enemy)
            if attacker_dr > enemy_dr:
                damage, location = self.apply_damage(enemy, attacker_roll, attacker_dr)
                return {"attack_roll": attacker_roll, "damage": damage, "enemy_roll": enemy_roll, "enemy_dr": enemy_dr, "attack_dr": attacker_dr, "location": location, "type": "melee"}
            else:
                return {"attack_roll": attacker_roll, "damage": 0, "enemy_roll": enemy_roll, "enemy_dr": enemy_dr, "attack_dr": attacker_dr, "type": "melee"}
        else:
            attacker_roll = roll_d100()
            if attacker_roll <= (self.get_ranged_attack() + advantage_bonus_character):
                damage, location = self.apply_damage(enemy, attacker_roll, 0)
                return {"attack_roll": attacker_roll, "damage": damage, "location": location, "type": "ranged"}
            else:
                return {"attack_roll": attacker_roll, "damage": 0, "type": "ranged"}

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
        return enemy.take_damage(damage, location), location

    def apply_damage_spell(self, enemy, roll, dr, spell):
        location = self.determine_location(roll)
        damage = int(spell["damage"]) + dr + self.BFM()
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
        return floor(self.characteristics["F"]/10)
    
    def BE(self):
        return floor(self.characteristics["E"]/10)
    
    def BFM(self):
        return floor(self.characteristics["FM"]/10)
    
    def get_cast_skill(self):
        return self.characteristics["I"] + self.get_skill("Langue (Magick)")

    def cast_spell(self, spell, enemy, focused):
        cast_roll = roll_d100()
        dr = calculate_dr(cast_roll, self.get_cast_skill())
        if cast_roll <= self.get_cast_skill():
            if dr >= int(spell["cast"]) or focused:
                damage, location = self.apply_damage_spell(enemy, cast_roll, dr, spell)
                self.focused_spell = None
                return {"spell_name": spell["name"], "attack_roll": cast_roll, "damage": damage, "attack_dr": dr, "location": location, "type": "spell_cast"}
        self.focused_spell = None
        return {"spell_name": spell["name"], "attack_roll": cast_roll, "damage": 0, "attack_dr": dr, "type": "spell_cast"}
    
    def focus_spell(self, spell):
        if not self.focused_spell:
            self.focused_spell = {"name": spell["name"], "focus_bonus": 0, "ready": False}
        elif self.focused_spell["name"] != spell["name"]:    
            self.focused_spell = {"name": spell["name"], "focus_bonus": 0, "ready": False}
        focus_roll = roll_d100()
        dr = calculate_dr(focus_roll, self.get_cast_skill())
        self.focused_spell["focus_bonus"] += dr
        if self.focused_spell["focus_bonus"] >= int(spell["cast"]):
            self.focused_spell["ready"] = True
        return {"spell_name": spell["name"], "focus_roll": focus_roll, "focus_bonus": dr, "ready": self.focused_spell["ready"], "type": "spell_focus"}

    def select_spell_cast_or_focus(self, spell, enemy):
        if int(spell["cast"]) > 0:
            if not self.focused_spell:
                return self.focus_spell(spell)
            elif self.focused_spell["name"] != spell["name"]:
                return self.focus_spell(spell)
            elif not self.focused_spell["ready"]:
                return self.focus_spell(spell)
            else:
                return self.cast_spell(spell, enemy, True)
        else:
            return self.cast_spell(spell, enemy, True)