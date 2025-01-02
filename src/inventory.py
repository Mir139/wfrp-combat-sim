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