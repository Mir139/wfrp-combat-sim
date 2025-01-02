import unittest
from src.character import Character
from src.combat import Combat

class TestCombat(unittest.TestCase):

    def setUp(self):
        self.faction1 = [Character("Hero1", 100, 4, 50, 30, 40, 30, 20, 30, 20, 30, 20, 10, "Faction1")]
        self.faction2 = [Character("Enemy1", 100, 4, 40, 20, 30, 20, 10, 20, 10, 20, 10, 5, "Faction2")]
        self.combat = Combat(self.faction1, self.faction2)

    def test_determine_initiative_order(self):
        order = self.combat.determine_initiative_order()
        self.assertEqual(order[0].name, "Hero1")

    def test_run_combat(self):
        self.combat.run_combat()
        winner = self.combat.determine_winner()
        self.assertIsNotNone(winner)

if __name__ == '__main__':
    unittest.main()