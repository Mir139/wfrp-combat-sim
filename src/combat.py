from faction import Faction
import random

class Combat:
    def __init__(self, faction1, faction2):
        self.faction1 = faction1
        self.faction2 = faction2

    def determine_initiative_order(self):
        all_characters = self.faction1.get_members() + self.faction2.get_members()
        return sorted(all_characters, key=lambda char: char.I, reverse=True)

    def initiate_combat(self):
        print("Combat initiated between factions.")
        self.initiative_order = self.determine_initiative_order()

    def resolve_turn(self, character):
        if not character.is_alive():
            return
        if not character.engaged:
            self.movement_phase(character)
        self.action_phase(character)

    def movement_phase(self, character):
        # Simplified movement phase
        if not character.engaged:
            if character.prefers_melee:
                enemy = self.find_enemy(character)
                if enemy:
                    character.engaged = True
                    enemy.engaged = True
                    print(f"{character.name} engages {enemy.name}.")

    def action_phase(self, character):
        if character.engaged:
            enemy = self.find_enemy(character)
            if enemy:
                character.attack_enemy(enemy)
                print(f"{character.name} attacks {enemy.name}.")
        else:
            # Logic for ranged attack
            enemy = self.find_enemy(character)
            if enemy:
                character.attack_enemy(enemy)
                print(f"{character.name} shoots at {enemy.name}.")

    def find_enemy(self, character):
        enemies = self.faction2.get_members() if character in self.faction1.get_members() else self.faction1.get_members()
        alive_enemies = [enemy for enemy in enemies if enemy.is_alive()]
        if alive_enemies:
            return random.choice(alive_enemies)
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
            print(f"The winner is {winner.name}.")
        else:
            print("It's a draw!")
        return winner.name, survivors, remaining_health