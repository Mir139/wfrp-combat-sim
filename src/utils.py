from math import floor

def random_number_generator(min_value, max_value):
    import random
    return random.randint(min_value, max_value)

def calculate_damage(attack, defense):
    damage = attack - defense
    return damage if damage > 0 else 0

def calculate_dr(roll, characteristic):
    return floor(characteristic/10) - floor(roll/10)

def roll_d100():
    return random_number_generator(1, 100)

def roll_d10():
    return random_number_generator(1, 10)