import unittest
from src.character import Character
from src.combat import Combat
from src.simulation import Simulation

class TestSimulation(unittest.TestCase):
    def setUp(self):
        self.faction1 = [Character("Hero1", 100, 4, 50, 30, 40, 30, 20, 30, 20, 30, 20, 10, "Faction1")]
        self.faction2 = [Character("Enemy1", 100, 4, 40, 20, 30, 20, 10, 20, 10, 20, 10, 5, "Faction2")]
        self.combat = Combat(self.faction1, self.faction2)

    def test_simulation_run(self):
        self.combat.run_combat()
        winner = self.combat.determine_winner()
        self.assertIsNotNone(winner)

def test_run_simulation():
    simulation = Simulation()
    results = simulation.run_simulation(num_simulations=100)
    assert len(results) == 100

def test_calculate_survival_probabilities():
    simulation = Simulation()
    simulation.run_simulation(num_simulations=100)
    probabilities = simulation.calculate_survival_probabilities()
    assert isinstance(probabilities, dict)

def test_gather_metrics():
    simulation = Simulation()
    simulation.run_simulation(num_simulations=100)
    metrics = simulation.gather_metrics()
    assert 'average_survival' in metrics
    assert 'faction_wins' in metrics

if __name__ == '__main__':
    unittest.main()