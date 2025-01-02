import unittest
from src.inventory import Inventory, MeleeWeapon, RangedWeapon, Armor

class TestInventory(unittest.TestCase):
    def setUp(self):
        self.inventory = Inventory()
        self.sword = MeleeWeapon("Sword", 1, 10, ["Sharp"])
        self.bow = RangedWeapon("Bow", 5, 8, ["Long Range"])
        self.armor = Armor("Plate Armor", -1, "Body", 5, ["Heavy"])

    def test_add_item(self):
        self.inventory.add_item(self.sword)
        self.assertIn(self.sword, self.inventory.get_items())

    def test_remove_item(self):
        self.inventory.add_item(self.sword)
        self.inventory.remove_item(self.sword)
        self.assertNotIn(self.sword, self.inventory.get_items())

    def test_get_items(self):
        self.inventory.add_item(self.sword)
        self.inventory.add_item(self.bow)
        items = self.inventory.get_items()
        self.assertEqual(len(items), 2)
        self.assertIn(self.sword, items)
        self.assertIn(self.bow, items)

    def test_remove_nonexistent_item(self):
        initial_items_count = len(self.inventory.get_items())
        self.inventory.remove_item("Nonexistent Item")
        self.assertEqual(len(self.inventory.get_items()), initial_items_count)

if __name__ == '__main__':
    unittest.main()