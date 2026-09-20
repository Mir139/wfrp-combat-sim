from src.character import Character
from src.faction import Faction
from src.inventory import Armor, MeleeWeapon


class ScriptedRng:
    """Fake RNG: randint returns the queued values in order; choice picks the first item."""

    def __init__(self, values):
        self.values = list(values)

    def randint(self, a, b):
        return self.values.pop(0)

    def choice(self, seq):
        return seq[0]


def make_character(name="Hero", faction="F1", health=10, CC=50, CT=30, F=40, E=30, I=30, weapon_damage=4):
    c = Character(name, health, 4, CC, CT, F, E, I, 30, 30, 30, 30, 30, faction)
    sword = MeleeWeapon("Epee", "Moyenne", str(weapon_damage), [], "1")
    c.inventory.add_item(sword)
    c.equip_weapon("Epee")
    return c


def make_faction(name, *members):
    faction = Faction(name)
    for m in members:
        faction.add_member(m)
    return faction


def make_armor(points, location="Tous"):
    return Armor("Armure", [], location, str(points), [])
