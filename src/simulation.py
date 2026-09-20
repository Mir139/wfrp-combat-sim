from src.loader import load_inventory, load_simulation_config, create_characters
from src.combat import Combat, DEFAULT_DISTANCE
import copy
import random

class Simulation:
    def __init__(self, factions, seed=None, initial_distance=DEFAULT_DISTANCE):
        self.factions = factions
        self.rng = random.Random(seed)
        self.initial_distance = initial_distance

    def run_simulation(self, num_simulations):
        results = []
        for _ in range(num_simulations):
            result = self._simulate_battle()
            results.append(result)
        return results

    def _simulate_battle(self):
        factions = copy.deepcopy(self.factions)
        combat = Combat(factions, self.rng, self.initial_distance)
        winner, survivors, remaining_health, action_log = combat.run_combat()
        return {"winner": winner, "survivors": survivors, "remaining_health": remaining_health,
                "routed": combat.determine_routed(), "action_log": action_log}

    def calculate_survival_probabilities(self, results):
        probabilities = {}
        for faction in self.factions:
            probabilities[faction.name] = sum(1 for result in results if result['winner'] == faction.name) / len(results)
        return probabilities

    def gather_metrics(self, results):
        metrics = {
            "total_battles": len(results),
            "draws": sum(1 for result in results if result['winner'] is None),
            "survival_probabilities": self.calculate_survival_probabilities(results),
            "average_remaining_health": {},
            "individual_survival_probabilities": {},
            "individual_average_remaining_health": {},
            "individual_rout_probabilities": {}
        }

        for faction in self.factions:
            names = [member.name for member in faction.members]
            wins = [r for r in results if r['winner'] == faction.name]
            total_health = sum(r['remaining_health'].get(name, 0) for r in wins for name in names)
            metrics["average_remaining_health"][faction.name] = total_health / len(wins) if wins else 0

            for name in names:
                alive = [r['remaining_health'][name] for r in results if name in r['remaining_health']]
                metrics["individual_survival_probabilities"][name] = len(alive) / len(results)
                metrics["individual_average_remaining_health"][name] = sum(alive) / len(alive) if alive else 0
                metrics["individual_rout_probabilities"][name] = sum(1 for r in results if name in r.get('routed', {})) / len(results)

        return metrics

# Example usage
if __name__ == "__main__":
    inventory_data = load_inventory('./db/db.json')
    config_data = load_simulation_config('./sim/job1.json')
    factions = create_characters(config_data['factions'], inventory_data)
    num_simulations = config_data['simulation']['num_simulations']

    sim = Simulation(factions, initial_distance=config_data['simulation'].get('initial_distance', DEFAULT_DISTANCE))
    results = sim.run_simulation(num_simulations)
    metrics = sim.gather_metrics(results)
    print(metrics)