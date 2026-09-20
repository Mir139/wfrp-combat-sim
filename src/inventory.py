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

    def _find_attribute(self, names):
        for attribute in self.attributes:
            for name in names:
                if attribute == name or attribute.startswith(name + " "):
                    return attribute
        return None

    def has_attribute(self, *names):
        """True if the item has one of the attributes (spelling variants allowed)."""
        return self._find_attribute(names) is not None

    def attribute_rating(self, *names):
        """Numeric rating of an attribute such as 'Recharge 3' (0 if absent or unrated)."""
        attribute = self._find_attribute(names)
        if attribute is None:
            return 0
        try:
            return int(attribute.split()[-1])
        except ValueError:
            return 0

    def base_damage(self):
        return int(str(self.damage).replace('+BF', '').strip())

class MeleeWeapon(Item):
    def __init__(self, name, reach, damage, attributes, encumbrance):
        super().__init__(name, attributes)
        self.reach = reach
        self.damage = damage
        self.encumbrance = encumbrance

class RangedWeapon(Item):
    def __init__(self, name, range, damage, attributes, encumbrance, damage_BF=False, range_BF=False):
        super().__init__(name, attributes)
        self.range = range
        self.damage = damage
        self.encumbrance = encumbrance
        self.damage_BF = damage_BF
        self.range_BF = range_BF
        self.reload_time = self.attribute_rating("Recharge")
        self.magazine = self.attribute_rating("Répétition", "Repétition") or 1
        self.shots_left = self.magazine
        self.reload_progress = 0

    def effective_range(self, strength_bonus):
        """Range in yards (the db range is a multiplier of BF for thrown weapons)."""
        return int(self.range) * (strength_bonus if self.range_BF else 1)

    def is_ready(self):
        return self.reload_time == 0 or self.shots_left > 0

    def fire(self):
        if self.reload_time > 0:
            self.shots_left -= 1

    def reload_step(self):
        """Spend one action reloading; returns True once the weapon is ready again."""
        self.reload_progress += 1
        if self.reload_progress >= self.reload_time:
            self.shots_left = self.magazine
            self.reload_progress = 0
        return self.is_ready()

    def reset(self):
        self.shots_left = self.magazine
        self.reload_progress = 0

    def jam(self):
        """Misfire: the weapon has to be reloaded from scratch."""
        self.shots_left = 0
        self.reload_progress = 0

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