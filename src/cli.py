"""Command line interface: python -m src.simulation job.json -n 10000"""
import argparse

from src.combat import DEFAULT_DISTANCE
from src.compare import load_variants, run_comparison
from src.loader import create_characters, load_inventory, load_simulation_config
from src.report import (comparison_rows, format_comparison, format_report, metrics_rows, write_csv, write_json)
from src.simulation import DEFAULT_NUM_SIMULATIONS, Simulation
from src.stats import DEFAULT_CONFIDENCE


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m src.simulation",
                                     description="Estimate the outcome of a WFRP combat by running many simulated fights.")
    parser.add_argument("job", nargs="?", default="sim/job1.json", help="job file (default: %(default)s)")
    parser.add_argument("--db", default="db/db.json", help="item database (default: %(default)s)")
    parser.add_argument("-n", "--num-simulations", type=int,
                        help=f"number of fights (default: the job's num_simulations, else {DEFAULT_NUM_SIMULATIONS})")
    parser.add_argument("--seed", type=int, help="seed for reproducible results")
    parser.add_argument("-j", "--workers", type=int, default=1,
                        help="worker processes, 0 for one per CPU (default: %(default)s)")
    parser.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE,
                        help="confidence level of the intervals (default: %(default)s)")
    parser.add_argument("--histogram", action="store_true", help="also print the remaining health histograms")
    parser.add_argument("--compare", metavar="FILE",
                        help="comparison file listing variants and sweeps of the job (what-if analysis)")
    parser.add_argument("--json", metavar="FILE", help="write the full metrics as JSON")
    parser.add_argument("--csv", metavar="FILE", help="write a CSV summary (per character, or per scenario with --compare)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (OSError, ValueError, KeyError) as error:  # bad path, invalid JSON, unknown character/item...
        raise SystemExit(f"Error: {error!r}" if isinstance(error, KeyError) else f"Error: {error}")


def run(args):
    if not 0 < args.confidence < 1:
        raise SystemExit("--confidence must be strictly between 0 and 1")
    config = load_simulation_config(args.job)
    inventory = load_inventory(args.db)
    settings = config.get("simulation", {})
    num_simulations = args.num_simulations or settings.get("num_simulations", DEFAULT_NUM_SIMULATIONS)
    if num_simulations <= 0:
        raise SystemExit("The number of simulations must be positive")

    if args.compare:
        variants = load_variants(load_simulation_config(args.compare))
        outcomes = run_comparison(config, inventory, variants, num_simulations, seed=args.seed, workers=args.workers)
        print(format_comparison(outcomes))
        if args.json:
            write_json(args.json, {"job": args.job, "seed": args.seed, "scenarios": outcomes})
        if args.csv:
            write_csv(args.csv, comparison_rows(outcomes))
        return

    factions = create_characters(config["factions"], inventory)
    sim = Simulation(factions, seed=args.seed, initial_distance=settings.get("initial_distance", DEFAULT_DISTANCE))
    results = sim.run_simulation(num_simulations, keep_logs=0, workers=args.workers)
    metrics = sim.gather_metrics(results, args.confidence)
    print(format_report(metrics, title=f"{args.job}" + (f" (seed {args.seed})" if args.seed is not None else ""),
                        histogram=args.histogram))
    if args.json:
        write_json(args.json, {"job": args.job, "seed": args.seed, "metrics": metrics})
    if args.csv:
        write_csv(args.csv, metrics_rows(metrics))


if __name__ == "__main__":
    main()
