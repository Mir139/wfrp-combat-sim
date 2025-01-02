import json
import warnings
from character import Character
from inventory import Inventory, MeleeWeapon, RangedWeapon, Armor
from faction import Faction  # Import the Faction class

def load_inventory(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data['inventory']

def load_simulation_config(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data

def create_item(item_data, item_type):
    if item_type == 'melee_weapons':
        return MeleeWeapon(
            name=item_data['name'],
            reach=item_data['reach'],
            damage=item_data['damage'],
            attributes=item_data['attributes'],
            encumbrance=item_data['encumbrance']
        )
    elif item_type == 'ranged_weapons':
        return RangedWeapon(
            name=item_data['name'],
            range=item_data['range'],
            damage=item_data['damage'],
            attributes=item_data['attributes'],
            encumbrance=item_data['encumbrance'],
            damage_BF=item_data.get('damage_BF', False)
        )
    elif item_type == 'armors':
        return Armor(
            name=item_data['name'],
            penalty=item_data['penalty'],
            location=item_data['location'],
            armor_points=item_data['armor_points'],
            attributes=item_data['attributes']
        )
    else:
        warnings.warn(f"Unknown item type: {item_type}")
        return None

def create_characters(factions_data, inventory_data):
    factions = []
    for faction_data in factions_data:
        faction = Faction(faction_data['name'])
        for member_data in faction_data['members']:
            character = Character(
                name=member_data['name'],
                health=member_data['health'],
                M=member_data['M'],
                CC=member_data['CC'],
                CT=member_data['CT'],
                F=member_data['F'],
                E=member_data['E'],
                I=member_data['I'],
                Ag=member_data['Ag'],
                Dex=member_data['Dex'],
                Int=member_data['Int'],
                FM=member_data['FM'],
                Soc=member_data['Soc'],
                faction=faction_data['name']
            )
            for item in member_data['inventory']:
                item_data = next((i for i in inventory_data[item['type']] if i['name'] == item['name']), None)
                if item_data:
                    item_instance = create_item(item_data, item['type'])
                    if item_instance:
                        character.inventory.add_item(item_instance)
                        if isinstance(item_instance, (MeleeWeapon, RangedWeapon)):
                            character.inventory.equip_weapon(item_instance.name)
                else:
                    warnings.warn(f"Item '{item['name']}' of type '{item['type']}' not found in inventory data.")
            faction.add_member(character)
        factions.append(faction)
    return factions