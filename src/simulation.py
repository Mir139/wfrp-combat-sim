from loader import load_inventory, load_simulation_config, create_characters
from combat import Combat
import copy

class Simulation:
    def __init__(self, factions):
        self.factions = factions

    def run_simulation(self, num_simulations):
        results = []
        for _ in range(num_simulations):
            result = self._simulate_battle()
            results.append(result)
        return results

    def _simulate_battle(self):
        # Select two factions for the battle
        faction1 = copy.deepcopy(self.factions[0])
        faction2 = copy.deepcopy(self.factions[1])
        combat = Combat(faction1, faction2)
        winner, survivors, remaining_health = combat.run_combat()
        print(f"Combat log: {combat.action_log}.")
        return {"winner": winner, "survivors": survivors, "remaining_health": remaining_health}

    def calculate_survival_probabilities(self, results):
        probabilities = {}
        for faction in self.factions:
            probabilities[faction.name] = sum(1 for result in results if result['winner'] == faction.name) / len(results)
        return probabilities

    def gather_metrics(self, results):
        metrics = {
            "total_battles": len(results),
            "survival_probabilities": self.calculate_survival_probabilities(results),
            "average_remaining_health": {},
            "individual_survival_probabilities": {},
            "individual_average_remaining_health": {}
        }

        for faction in self.factions:
            total_health = 0
            win_count = 0
            individual_health = {member.name: 0 for member in faction.members}
            individual_wins = {member.name: 0 for member in faction.members}
            for result in results:
                if result['winner'] == faction.name:
                    total_health += sum(result['remaining_health'])
                    win_count += 1
                    for member, health in zip(faction.members, result['remaining_health']):
                        individual_health[member.name] += health
                        individual_wins[member.name] += 1
            if win_count > 0:
                metrics["average_remaining_health"][faction.name] = total_health / win_count
            else:
                metrics["average_remaining_health"][faction.name] = 0

            for member in faction.members:
                if individual_wins[member.name] > 0:
                    metrics["individual_average_remaining_health"][member.name] = individual_health[member.name] / individual_wins[member.name]
                else:
                    metrics["individual_average_remaining_health"][member.name] = 0
                metrics["individual_survival_probabilities"][member.name] = individual_wins[member.name] / len(results)

        return metrics

# Example usage
if __name__ == "__main__":
    inventory_data = load_inventory('./db/db.json')
    config_data = load_simulation_config('./sim/job1.json')
    factions = create_characters(config_data['factions'], inventory_data)
    num_simulations = config_data['simulation']['num_simulations']

    sim = Simulation(factions)
    results = sim.run_simulation(num_simulations)
    metrics = sim.gather_metrics(results)
    print(metrics)