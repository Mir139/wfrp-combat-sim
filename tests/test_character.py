import unittest
from src.character import Character

class TestCharacter(unittest.TestCase):
    def setUp(self):
        self.character = Character("Hero", 100, 4, 50, 30, 40, 30, 20, 30, 20, 30, 20, 10, "Faction1")
        self.enemy = Character("Enemy", 100, 4, 40, 20, 30, 20, 10, 20, 10, 20, 10, 5, "Faction2")

    def test_take_damage(self):
        self.character.take_damage(10)
        self.assertEqual(self.character.health, 90)

    def test_attack_enemy_melee(self):
        self.character.engaged = True
        self.character.attack_enemy(self.enemy)
        self.assertTrue(self.enemy.health < 100)

    def test_attack_enemy_ranged(self):
        self.character.engaged = False
        self.character.attack_enemy(self.enemy)
        self.assertTrue(self.enemy.health < 100)

if __name__ == '__main__':
    unittest.main()