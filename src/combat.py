import random

from src.rules import ENGAGED_DISTANCE, range_modifier

MAX_ROUNDS = 1000
DEFAULT_DISTANCE = 12  # yards between the two sides at the start


class Combat:
    def __init__(self, faction1, faction2, rng=None, distance=DEFAULT_DISTANCE):
        self.faction1 = faction1
        self.faction2 = faction2
        self.rng = rng or random.Random()
        self.action_log = []
        for member in faction1.get_members():
            member.position = 0
        for member in faction2.get_members():
            member.position = distance

    def determine_initiative_order(self):
        all_characters = self.faction1.get_members() + self.faction2.get_members()
        return sorted(all_characters, key=lambda char: char.I, reverse=True)

    def initiate_combat(self):
        self.action_log.append({"action": "initiate_combat", "details": "Combat initiated between factions."})
        self.initiative_order = self.determine_initiative_order()

    # --- turn --------------------------------------------------------------

    def resolve_turn(self, character):
        if not character.is_alive():
            return
        self.apply_bleeding(character)
        if not character.is_alive():
            return
        enemies = self.living_enemies(character)
        if not enemies:
            return
        move_used = self.stand_up(character)
        engaged = [e for e in enemies if self.distance(character, e) <= ENGAGED_DISTANCE]
        if engaged:
            self.engaged_action(character, engaged)
        else:
            self.free_action(character, self.pick_target(character, enemies), move_used)
        if character.is_alive() and character.stunned and character.endurance_test(self.rng):
            character.stunned = False

    def apply_bleeding(self, character):
        if character.bleeding:
            character.health -= character.bleeding
            self.action_log.append({
                "action": "bleed",
                "attacker": character.name,
                "target": character.name,
                "details": {"damage": character.bleeding},
                "enemy_health": character.health,
            })

    def stand_up(self, character):
        if not character.prone:
            return False
        character.prone = False
        self.action_log.append({"action": "stand_up", "attacker": character.name, "target": character.name})
        return True

    def engaged_action(self, character, engaged):
        enemy = self.rng.choice(engaged)
        if character.combat_mode() == "ranged":
            pistol = character.ready_ranged_weapon(pistol_only=True)
            if pistol:
                return self.ranged_attack(character, enemy, pistol)
            if not character.melee_weapons() and character.weapon_to_reload():
                return self.reload(character)
        self.melee_attack(character, enemy)

    def free_action(self, character, target, move_used):
        if character.combat_mode() == "ranged":
            self.ranged_turn(character, target, move_used)
        else:
            self.charge(character, target, move_used)

    def ranged_turn(self, character, target, move_used):
        weapon = character.ready_ranged_weapon()
        if weapon is None:
            if character.weapon_to_reload():
                self.reload(character)
            return
        reach = weapon.effective_range(character.BF())
        if self.distance(character, target) > reach and not move_used:
            self.move_towards(character, target, self.walk_distance(character))
        if range_modifier(self.distance(character, target), reach) is not None:
            self.ranged_attack(character, target, weapon)

    def charge(self, character, target, move_used):
        """Walk to the target and attack if that brings us into melee, otherwise run."""
        if move_used:
            return
        gap = self.distance(character, target) - ENGAGED_DISTANCE
        if gap > self.walk_distance(character):
            self.move_towards(character, target, 2 * self.walk_distance(character), "run")
            return
        self.move_towards(character, target, self.walk_distance(character))
        self.action_log.append({
            "action": "engage",
            "attacker": character.name,
            "target": target.name,
            "details": f"{character.name} engages {target.name}.",
        })
        self.melee_attack(character, target)

    # --- actions -----------------------------------------------------------

    def melee_attack(self, character, enemy):
        result = character.melee_attack(enemy, self.rng)
        self.action_log.append({
            "action": "attack",
            "attacker": character.name,
            "target": enemy.name,
            "details": result,
            "enemy_health": enemy.health,
        })

    def ranged_attack(self, character, enemy, weapon):
        result = character.ranged_attack(enemy, weapon, self.distance(character, enemy), self.rng)
        self.action_log.append({
            "action": "ranged_attack",
            "attacker": character.name,
            "target": enemy.name,
            "details": result,
            "enemy_health": enemy.health,
        })

    def reload(self, character):
        weapon = character.weapon_to_reload()
        ready = weapon.reload_step()
        self.action_log.append({
            "action": "reload",
            "attacker": character.name,
            "target": character.name,
            "details": {"weapon": weapon.name, "ready": ready},
        })

    def move_towards(self, character, target, steps, action="move"):
        distance = self.distance(character, target)
        travelled = min(steps, max(distance - 1, 0))
        if travelled <= 0:
            return
        character.position += travelled if target.position > character.position else -travelled
        self.action_log.append({
            "action": action,
            "attacker": character.name,
            "target": target.name,
            "details": {"distance": distance - travelled},
        })

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def distance(a, b):
        return abs(a.position - b.position)

    @staticmethod
    def walk_distance(character):
        return 2 * character.M  # yards per Move

    def enemy_faction(self, character):
        return self.faction2 if character in self.faction1.get_members() else self.faction1

    def living_enemies(self, character):
        return [e for e in self.enemy_faction(character).get_members() if e.is_alive()]

    def pick_target(self, character, enemies):
        if character.target not in enemies:
            character.target = self.rng.choice(enemies)
        return character.target

    # --- outcome -----------------------------------------------------------

    def determine_winner(self):
        faction1_alive = any(char.is_alive() for char in self.faction1.get_members())
        faction2_alive = any(char.is_alive() for char in self.faction2.get_members())
        if faction1_alive and not faction2_alive:
            return self.faction1
        elif faction2_alive and not faction1_alive:
            return self.faction2
        return None

    def determine_survivors(self, faction):
        if faction is None:
            return []
        return [character.name for character in faction.get_members() if character.is_alive()]

    def determine_remaining_health(self, faction):
        """Health of each surviving member of `faction`, keyed by character name."""
        if faction is None:
            return {}
        return {character.name: character.health for character in faction.get_members() if character.is_alive()}

    def run_combat(self):
        self.initiate_combat()
        rounds = 0
        while rounds < MAX_ROUNDS and any(char.is_alive() for char in self.faction1.get_members()) and any(char.is_alive() for char in self.faction2.get_members()):
            for character in self.initiative_order:
                self.resolve_turn(character)
            rounds += 1
        winner = self.determine_winner()
        survivors = self.determine_survivors(winner)
        remaining_health = self.determine_remaining_health(winner)
        return (winner.name if winner else None), survivors, remaining_health, self.action_log
