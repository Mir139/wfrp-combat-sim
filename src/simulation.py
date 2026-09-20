import os
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from statistics import mean, median

from src.combat import Combat, DEFAULT_DISTANCE
from src.stats import DEFAULT_CONFIDENCE, wilson_interval

DEFAULT_NUM_SIMULATIONS = 10000
PROGRESS_STEPS = 50  # progress reports of a single-process run
DEFAULT_KEEP_LOGS = 100  # detailed logs are only kept for the first battles, to bound memory


def simulate_battle(factions, seed, distance, keep_log):
    """Run one fight on `factions` (reset first, mutated in place) with its own RNG."""
    for faction in factions:
        for member in faction.get_members():
            member.reset()
    combat = Combat(factions, random.Random(seed), distance)
    winner, survivors, remaining_health, action_log = combat.run_combat()
    return {
        "winner": winner,
        "survivors": survivors,
        "remaining_health": remaining_health,
        "routed": combat.determine_routed(),
        "rounds": combat.rounds,
        "deaths": combat.deaths,
        "hits": combat.hits,
        "action_log": action_log if keep_log else None,
    }


def _run_chunk(args):
    factions, distance, jobs = args
    return [simulate_battle(factions, seed, distance, keep_log) for seed, keep_log in jobs]


class Simulation:
    def __init__(self, factions, seed=None, initial_distance=DEFAULT_DISTANCE):
        self.factions = factions
        self.rng = random.Random(seed)
        self.initial_distance = initial_distance

    def run_simulation(self, num_simulations, keep_logs=DEFAULT_KEEP_LOGS, workers=1, progress=None):
        """Run `num_simulations` fights.

        Every fight gets its own seed drawn from the simulation seed, so the results do not depend on
        `workers`. Only the first `keep_logs` fights keep their action log (None: keep all of them);
        the others have `action_log` set to None. `progress(done, total)` is called as fights complete.
        """
        seeds = [self.rng.getrandbits(64) for _ in range(num_simulations)]
        jobs = [(seed, keep_logs is None or i < keep_logs) for i, seed in enumerate(seeds)]
        if workers is None or workers <= 0:
            workers = os.cpu_count() or 1
        workers = min(workers, max(num_simulations, 1))
        pieces = workers * 4 if workers > 1 else PROGRESS_STEPS
        size = max(1, -(-len(jobs) // pieces))
        chunks = [(self.factions, self.initial_distance, jobs[i:i + size]) for i in range(0, len(jobs), size)]
        results = []

        def collect(chunk_results):
            results.extend(chunk_results)
            if progress:
                progress(len(results), num_simulations)

        if workers == 1:
            for chunk in chunks:
                collect(_run_chunk(chunk))
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for chunk_results in pool.map(_run_chunk, chunks):
                    collect(chunk_results)
        return results

    def calculate_survival_probabilities(self, results):
        probabilities = {}
        for faction in self.factions:
            probabilities[faction.name] = sum(1 for result in results if result['winner'] == faction.name) / len(results)
        return probabilities

    def gather_metrics(self, results, confidence=DEFAULT_CONFIDENCE):
        """Aggregate the results of many fights.

        Probabilities come with a Wilson confidence interval in `confidence_intervals`.
        `remaining_health_distribution` counts, per character, the final health over all fights (dead = 0).
        `hit_locations` gives, per character and body location, the total hits taken and damage suffered.
        """
        total = len(results)
        interval = lambda count: wilson_interval(count, total, confidence)
        metrics = {
            "total_battles": total,
            "confidence_level": confidence,
            "draws": sum(1 for result in results if result['winner'] is None),
            "survival_probabilities": self.calculate_survival_probabilities(results),
            "average_remaining_health": {},
            "individual_survival_probabilities": {},
            "individual_death_probabilities": {},
            "individual_average_remaining_health": {},
            "individual_rout_probabilities": {},
            "first_death_probabilities": {},
            "remaining_health_distribution": {},
            "members": {},
            "hit_locations": {},
            "rounds": {},
            "confidence_intervals": {"survival_probabilities": {}, "individual_survival_probabilities": {},
                                     "individual_death_probabilities": {}, "first_death_probabilities": {}},
        }
        intervals = metrics["confidence_intervals"]
        intervals["draw_probability"] = interval(metrics["draws"])

        rounds = [r["rounds"] for r in results if "rounds" in r]
        if rounds:
            metrics["rounds"] = {"mean": mean(rounds), "median": median(rounds), "min": min(rounds), "max": max(rounds)}
        hit_totals = {}
        for result in results:
            for name, locations in result.get("hits", {}).items():
                totals = hit_totals.setdefault(name, {})
                for location, (count, damage) in locations.items():
                    entry = totals.setdefault(location, {"hits": 0, "damage": 0})
                    entry["hits"] += count
                    entry["damage"] += damage
        first_deaths = Counter(r["deaths"][0] for r in results if r.get("deaths"))

        for faction in self.factions:
            names = [member.name for member in faction.members]
            wins = [r for r in results if r['winner'] == faction.name]
            total_health = sum(r['remaining_health'].get(name, 0) for r in wins for name in names)
            metrics["average_remaining_health"][faction.name] = total_health / len(wins) if wins else 0
            intervals["survival_probabilities"][faction.name] = interval(len(wins))

            for member in faction.members:
                name = member.name
                metrics["members"][name] = {"faction": faction.name, "max_health": member.max_health}
                alive = [r['remaining_health'][name] for r in results if name in r['remaining_health']]
                deaths = sum(1 for r in results if name in r.get("deaths", ()))
                metrics["individual_survival_probabilities"][name] = len(alive) / total
                metrics["individual_death_probabilities"][name] = deaths / total
                metrics["individual_average_remaining_health"][name] = sum(alive) / len(alive) if alive else 0
                metrics["individual_rout_probabilities"][name] = sum(1 for r in results if name in r.get('routed', {})) / total
                metrics["first_death_probabilities"][name] = first_deaths[name] / total
                metrics["hit_locations"][name] = hit_totals.get(name, {})
                metrics["remaining_health_distribution"][name] = dict(sorted(Counter(max(r['remaining_health'].get(name, 0), 0) for r in results).items()))
                intervals["individual_survival_probabilities"][name] = interval(len(alive))
                intervals["individual_death_probabilities"][name] = interval(deaths)
                intervals["first_death_probabilities"][name] = interval(first_deaths[name])

        return metrics


if __name__ == "__main__":
    from src.cli import main
    main()
