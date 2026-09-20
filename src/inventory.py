ARMOR_LOCATIONS = {
    "Tête": 0, "Bras gauche": 1, "Bras droit": 2, "Corps": 3, "Jambe gauche": 4, "Jambe droite": 5,
}

class Inventory:
    def __init__(self):
        self.items = []
        self.equipped_weapon = None

    def add_item(self, item):
        self.items.append(item)

    def remove_item(self, item):
        if item in self.items:
            self.items.remove(item)

    def get_items(self):
        return self.items

    def equip_weapon(self, weapon_name):
        for item in self.items:
            if isinstance(item, (MeleeWeapon, RangedWeapon)) and item.name == weapon_name:
                self.equipped_weapon = item
                if isinstance(item, MeleeWeapon):
                    return "melee_weapons"
                elif isinstance(item, RangedWeapon):
                    return "ranged_weapons"
        return None
    
    def armor_points(self):
        """Armor points per location (Head, L/R Arm, Body, L/R Leg), summed over armors."""
        points = [0] * 6
        for item in self.items:
            if isinstance(item, Armor):
                for i in item.covered_indexes():
                    points[i] += int(item.armor_points)
        return points

    def get_item_type(self, item):
        if isinstance(item, MeleeWeapon):
            return "melee_weapons"
        elif isinstance(item, RangedWeapon):
            return "ranged_weapons"
        elif isinstance(item, Armor):
            return "armors"
        return None

    def get_equipped_weapon(self):
        return self.equipped_weapon

class Item:
    def __init__(self, name, attributes):
        self.name = name
        self.attributes = attributes

class MeleeWeapon(Item):
    def __init__(self, name, reach, damage, attributes, encumbrance):
        super().__init__(name, attributes)
        self.reach = reach
        self.damage = damage
        self.encumbrance = encumbrance

class RangedWeapon(Item):
    def __init__(self, name, range, damage, attributes, encumbrance, damage_BF=False):
        super().__init__(name, attributes)
        self.range = range
        self.damage = damage
        self.encumbrance = encumbrance
        self.damage_BF = damage_BF

class Armor(Item):
    def __init__(self, name, penalty, location, armor_points, attributes):
        super().__init__(name, attributes)
        self.penalty = penalty
        self.location = location
        self.armor_points = armor_points

    def covered_indexes(self):
        """Indexes (Head, L Arm, R Arm, Body, L Leg, R Leg) covered by this armor."""
        if self.location == "Tous":
            return range(6)
        names = self.location if isinstance(self.location, list) else [self.location]
        return [ARMOR_LOCATIONS[n] for n in names]