import unittest
from src.faction import Faction
from src.character import Character

class TestFaction(unittest.TestCase):

    def setUp(self):
        self.character1 = Character("Hero1", 100, 4, 50, 30, 40, 30, 20, 30, 20, 30, 20, 10, "Faction1")
        self.character2 = Character("Hero2", 100, 4, 50, 30, 40, 30, 20, 30, 20, 30, 20, 10, "Faction1")
        self.faction = [self.character1, self.character2]

    def test_add_member(self):
        character = "Character1"  # Replace with actual character instance when implemented
        self.faction.add_member(character)
        self.assertIn(character, self.faction.get_members())

    def test_get_members(self):
        self.assertEqual(self.faction.get_members(), [])
        character1 = "Character1"  # Replace with actual character instance when implemented
        character2 = "Character2"  # Replace with actual character instance when implemented
        self.faction.add_member(character1)
        self.faction.add_member(character2)
        self.assertEqual(self.faction.get_members(), [character1, character2])

    def test_faction_name(self):
        self.assertEqual(self.faction.name, "Warriors")

    def test_faction_members(self):
        self.assertEqual(len(self.faction), 2)
        self.assertEqual(self.faction[0].name, "Hero1")
        self.assertEqual(self.faction[1].name, "Hero2")

if __name__ == '__main__':
    unittest.main()