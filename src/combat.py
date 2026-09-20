import math
import random

from src.rules import ENGAGED_DISTANCE, range_modifier

MAX_ROUNDS = 1000
DEFAULT_DISTANCE = 12  # yards between the two sides at the start


class Combat:
    def __init__(self, factions, rng=None, distance=DEFAULT_DISTANCE):
        self.factions = list(factions)
        self.rng = rng or random.Random()
        self.action_log = []
        self.rounds = 0
        self.deaths = []  # names, in order of death
        self.faction_of = {id(m): f for f in self.factions for m in f.get_members()}
        self.initial_size = {id(f): len(f.get_members()) for f in self.factions}
        for faction, position in zip(self.factions, self.starting_positions(len(self.factions), distance)):
            for member in faction.get_members():
                member.position = position

    @staticmethod
    def starting_positions(count, distance):
        """Factions sit on the vertices of a regular polygon whose side is `distance`.

        The first faction is at the origin, so two factions face each other along the x axis.
        """
        if count == 1:
            return [(0.0, 0.0)]
        radius = distance / (2 * math.sin(math.pi / count))
        return [(round(radius * (1 - math.cos(2 * math.pi * i / count)), 9),
                 round(radius * math.sin(2 * math.pi * i / count), 9)) for i in range(count)]

    def all_characters(self):
        return [m for f in self.factions for m in f.get_members()]

    def determine_initiative_order(self):
        return sorted(self.all_characters(), key=lambda char: char.I, reverse=True)

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
        if not character.is_active():
            return
        enemies = self.living_enemies(character)
        if not enemies:
            return
        if character.on_rout and self.check_morale(character):
            return
        move_used = self.stand_up(character)
        engaged = [e for e in enemies if self.distance(character, e) <= ENGAGED_DISTANCE]
        if engaged:
            self.engaged_action(character, engaged)
        else:
            self.free_action(character, self.select_target(character, enemies), move_used)
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
        enemy = self.select_target(character, engaged)
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
        dx = (target.position[0] - character.position[0]) / distance
        dy = (target.position[1] - character.position[1]) / distance
        character.position = (character.position[0] + dx * travelled, character.position[1] + dy * travelled)
        self.action_log.append({
            "action": action,
            "attacker": character.name,
            "target": target.name,
            "details": {"distance": distance - travelled},
        })

    def check_morale(self, character):
        """Test Sang-froid (FM) once per new trigger; on failure the character flees or surrenders."""
        faction = self.faction_of[id(character)]
        active_allies = sum(1 for m in faction.get_members() if m.is_active())
        for trigger in character.morale_triggers(active_allies, self.initial_size[id(faction)]):
            character.morale_checked.add(trigger)
            test = character.cool_test(self.rng)
            if test["success"]:
                continue
            character.status = "fled" if character.on_rout == "flee" else "surrendered"
            self.action_log.append({
                "action": "rout",
                "attacker": character.name,
                "target": character.name,
                "details": {"outcome": character.status, "trigger": trigger, "roll": test["roll"], "target": test["target"]},
            })
            return True
        return False

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def distance(a, b):
        return math.dist(a.position, b.position)

    @staticmethod
    def walk_distance(character):
        return 2 * character.M  # yards per Move

    def living_enemies(self, character):
        own = self.faction_of[id(character)]
        return [m for f in self.factions if f is not own for m in f.get_members() if m.is_active()]

    def select_target(self, character, candidates):
        """Pick among `candidates` following the character's targeting strategy; ties are random."""
        strategy = character.targeting
        if strategy == "random":
            if character.target not in candidates:
                character.target = self.rng.choice(candidates)
            return character.target
        key = {
            "nearest": lambda e: self.distance(character, e),
            "weakest": lambda e: e.health,
            "dangerous": lambda e: -e.threat(),
        }[strategy]
        best = min(key(e) for e in candidates)
        return self.rng.choice([e for e in candidates if key(e) == best])

    # --- outcome -----------------------------------------------------------

    def record_deaths(self):
        for character in self.all_characters():
            if not character.is_alive() and character.name not in self.deaths:
                self.deaths.append(character.name)

    def determine_winner(self):
        """The only faction with fighters left, or None (draw)."""
        standing = [f for f in self.factions if any(m.is_active() for m in f.get_members())]
        return standing[0] if len(standing) == 1 else None

    def determine_survivors(self):
        """Names of everyone still alive, including those who fled or surrendered."""
        return [m.name for m in self.all_characters() if m.is_alive()]

    def determine_remaining_health(self):
        return {m.name: m.health for m in self.all_characters() if m.is_alive()}

    def determine_routed(self):
        return {m.name: m.status for m in self.all_characters() if m.status}

    def run_combat(self):
        self.initiate_combat()
        rounds = 0
        while rounds < MAX_ROUNDS and sum(any(m.is_active() for m in f.get_members()) for f in self.factions) > 1:
            for character in self.initiative_order:
                self.resolve_turn(character)
                self.record_deaths()
            rounds += 1
            self.rounds = rounds
        winner = self.determine_winner()
        return (winner.name if winner else None), self.determine_survivors(), self.determine_remaining_health(), self.action_log
