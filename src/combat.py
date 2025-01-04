from faction import Faction
import random

class Combat:
    def __init__(self, faction1, faction2):
        self.faction1 = faction1
        self.faction2 = faction2
        self.action_log = []
        self.engagements = {}  # Dictionnaire pour suivre les engagements

    def clean_character_engagement(self, character):
        engagements = self.engagements.get(character.name, [])
        if engagements and not character.engaged:
            character.engaged = True
        elif not engagements and character.engaged:
            character.engaged = False
    
    def determine_initiative_order(self):
        all_characters = self.faction1.get_members() + self.faction2.get_members()
        return sorted(all_characters, key=lambda char: char.I, reverse=True)

    def initiate_combat(self):
        self.action_log.append({"action": "initiate_combat", "details": "Combat initiated between factions."})
        self.initiative_order = self.determine_initiative_order()

    def resolve_turn(self, character):
        if not character.is_alive():
            return
        if not character.engaged:
            self.movement_phase(character)
        self.action_phase(character)

    def movement_phase(self, character):
        if not character.engaged:
            if character.prefers_melee:
                enemy, details = self.find_enemy(character)
                if enemy:
                    character.engaged = True
                    enemy.engaged = True
                    if character.name not in self.engagements:
                        self.engagements[character.name] = []
                    if enemy.name not in self.engagements:
                        self.engagements[enemy.name] = []
                    self.engagements[character.name].append(enemy.name)
                    self.engagements[enemy.name].append(character.name)
                    self.action_log.append({
                        "action": "engage",
                        "attacker": character.name,
                        "target": enemy.name,
                        "details": details
                    })

    def action_phase(self, character):
        if character.engaged:
            enemy = self.select_target(character, [self.find_character_by_name(enemy) for enemy in self.engagements.get(character.name)])
            if enemy and enemy.is_alive():
                attack_result = character.attack_enemy(enemy)
                self.action_log.append({
                    "action": "attack",
                    "attacker": character.name,
                    "target": enemy.name,
                    "details": attack_result,
                    "enemy_health": enemy.health
                })
                self.handle_target_death(character, enemy)
        else:
            enemy, details = self.find_enemy(character)
            if enemy:
                attack_result = character.attack_enemy(enemy)
                self.action_log.append({
                    "action": "ranged_attack",
                    "attacker": character.name,
                    "target": enemy.name,
                    "details": attack_result,
                    "enemy_health": enemy.health
                })
                self.handle_target_death(character, enemy)
    
    def handle_target_death(self, attacker, target):
        if not target.is_alive():
            if target.engaged:
                self.engagements.pop(target.name, None)
                for enemy_name in self.engagements:
                    try:
                        self.engagements[enemy_name].remove(target.name)
                    except ValueError:
                        pass
                    self.clean_character_engagement(self.find_character_by_name(enemy_name))
            
            self.action_log.append({
                "action": "death",
                "attacker": attacker.name,
                "target": target.name,
                "details": f"{target.name} has been killed by {attacker.name}.",
                "enemy_health": target.health
            })

    def select_target(self, character, potential_targets):
        if character.target_selection_priority == "default":
            return self.get_higher_attack_target(potential_targets)
        elif character.target_selection_priority == "random":
            return random.choice(potential_targets)
        
    def select_target_unengaged(self, character, potential_targets):
        if character.target_selection_priority == "default":
            if not character.prefers_melee:
                return self.get_higher_attack_target(potential_targets), {"target_selection_priority": character.target_selection_priority}
            else:
                same_rank_target, character_rank, target_rank = self.get_same_rank_target(character, potential_targets)
                if same_rank_target:
                    return same_rank_target, {"target_selection_priority": character.target_selection_priority, "character_rank": character_rank, "target_rank": target_rank}
                else:
                    return self.get_higher_attack_target(potential_targets), {"target_selection_priority": character.target_selection_priority, "character_rank": character_rank, "target_rank": 1}
        elif character.target_selection_priority == "random":
            return random.choice(potential_targets), {"target_selection_priority": character.target_selection_priority}

    def get_same_rank_target(self, character, potential_targets):
        character_rank = self.get_rank(character, "CC")
        same_rank_target = None
        target_rank = None
        for target in potential_targets:
            if self.get_rank(target, "CC") == character_rank:
                same_rank_target = target
                target_rank = character_rank
                break
        return same_rank_target, character_rank, target_rank
    
    def get_rank(self, character, attribute):
        sorted_characters = sorted(character.faction.get_members(), key=lambda char: getattr(char, attribute), reverse=True)
        return sorted_characters.index(character)

    def get_higher_attack_target(self, potential_targets):
        target = None
        highest_attack = 0
        for enemy in potential_targets:
            if enemy.prefers_melee and enemy.CC > highest_attack:
                highest_attack = enemy.CC
                target = enemy
            else:
                if not enemy.engaged and enemy.CT > highest_attack:
                    highest_attack = enemy.CT
                    target = enemy
                elif not enemy.engaged and enemy.CC > highest_attack:
                    highest_attack = enemy.CC
                    target = enemy
        return target
    
    def find_enemy(self, character):
        enemies = self.faction2.get_members() if character in self.faction1.get_members() else self.faction1.get_members()
        alive_enemies = [enemy for enemy in enemies if enemy.is_alive()]
        if alive_enemies:
            return self.select_target_unengaged(character, alive_enemies)
        return None, None

    def find_character_by_name(self, name):
        all_characters = self.faction1.get_members() + self.faction2.get_members()
        for character in all_characters:
            if character.name == name:
                return character
        return None

    def determine_winner(self):
        faction1_alive = any(char.is_alive() for char in self.faction1.get_members())
        faction2_alive = any(char.is_alive() for char in self.faction2.get_members())
        if faction1_alive and not faction2_alive:
            return self.faction1
        elif faction2_alive and not faction1_alive:
            return self.faction2
        return None
    
    def determine_survivors(self, faction):
        survivors = []
        for character in faction.get_members():
            if character.is_alive():
                survivors.append(character.name)
        return survivors
    
    def determine_remaining_health(self, faction):
        remaining_health = []
        for character in faction.get_members():
            if character.is_alive():
                remaining_health.append(character.health)
        return remaining_health

    def run_combat(self):
        self.initiate_combat()
        while any(char.is_alive() for char in self.faction1.get_members()) and any(char.is_alive() for char in self.faction2.get_members()):
            for character in self.initiative_order:
                self.resolve_turn(character)
        winner = self.determine_winner()
        survivors = self.determine_survivors(winner)
        remaining_health = self.determine_remaining_health(winner)
        if winner:
            return winner.name, survivors, remaining_health, self.action_log
        else:
            return None, survivors, remaining_health, self.action_log