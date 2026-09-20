from src.character import Character
from src.faction import Faction
from src.inventory import Armor, MeleeWeapon, RangedWeapon


class ScriptedRng:
    """Fake RNG: randint returns the queued values in order; choice picks the first item."""

    def __init__(self, values):
        self.values = list(values)

    def randint(self, a, b):
        return self.values.pop(0)

    def choice(self, seq):
        return seq[0]


def make_character(name="Hero", faction="F1", health=10, CC=50, CT=30, F=40, E=30, I=30, Ag=30, M=4,
                   weapon_damage=4, weapon_attributes=(), behavior=None, unarmed=False):
    c = Character(name, health, M, CC, CT, F, E, I, Ag, 30, 30, 30, 30, faction, behavior=behavior)
    if not unarmed:
        c.inventory.add_item(MeleeWeapon("Epee", "Moyenne", str(weapon_damage), list(weapon_attributes), "1"))
    return c


def make_ranged(name="Pistolet", range=20, damage=8, attributes=("Pistolet", "Recharge 1"), damage_BF=False, range_BF=False):
    return RangedWeapon(name, str(range), str(damage), list(attributes), "0", damage_BF=damage_BF, range_BF=range_BF)


def make_faction(name, *members):
    faction = Faction(name)
    for m in members:
        faction.add_member(m)
    return faction


def make_armor(points, location="Tous"):
    return Armor("Armure", [], location, str(points), [])
