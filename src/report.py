"""Text, JSON and CSV output of simulation metrics."""
import csv
import json

BAR_WIDTH = 30
HISTOGRAM_BINS = 10


def pct(p):
    return f"{100 * p:.1f}%"


def pct_interval(interval):
    return f"[{100 * interval[0]:.1f}-{100 * interval[1]:.1f}]"


def _table(headers, rows):
    widths = [max(len(str(x)) for x in column) for column in zip(headers, *rows)]
    lines = ["  ".join(str(h).ljust(w) for h, w in zip(headers, widths)).rstrip()]
    lines += ["  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip() for row in rows]
    return "\n".join(lines)


def health_histogram(distribution, max_health):
    """Bucket a {health: count} distribution: 'dead', then up to HISTOGRAM_BINS slices of the max health."""
    bins = max(1, min(HISTOGRAM_BINS, max_health))
    buckets = {"dead": 0}
    for i in range(bins):
        buckets[f"{max_health * i // bins + 1}-{max_health * (i + 1) // bins}"] = 0
    labels = list(buckets)
    for health, count in distribution.items():
        if health <= 0:
            buckets["dead"] += count
        else:  # health above the max (healing) goes to the last bucket
            buckets[labels[min(-(-health * bins // max_health), bins)]] += count
    return buckets


def format_report(metrics, title=None, histogram=False):
    level = int(round(100 * metrics["confidence_level"]))
    intervals = metrics["confidence_intervals"]
    total = metrics["total_battles"]
    lines = []
    if title:
        lines.append(title)
    lines.append(f"{total} combats, {level}% confidence intervals in brackets")
    rounds = metrics.get("rounds")
    if rounds:
        lines.append(f"Rounds per combat: mean {rounds['mean']:.1f}, median {rounds['median']:g}, "
                     f"min {rounds['min']}, max {rounds['max']}")
    lines.append(f"Draws: {metrics['draws']}")
    lines += ["", "Chance of winning"]
    rows = [(name, pct(p), pct_interval(intervals["survival_probabilities"][name]),
             f"{metrics['average_remaining_health'][name]:.1f}")
            for name, p in metrics["survival_probabilities"].items()]
    lines.append(_table(["Faction", "Wins", "CI", "Avg HP left (when winning)"], rows))

    rows = []
    for name, member in metrics["members"].items():
        rows.append((name, member["faction"],
                     pct(metrics["individual_survival_probabilities"][name]),
                     pct_interval(intervals["individual_survival_probabilities"][name]),
                     pct(metrics["individual_death_probabilities"][name]),
                     pct_interval(intervals["individual_death_probabilities"][name]),
                     pct(metrics["first_death_probabilities"][name]),
                     f"{metrics['individual_average_remaining_health'][name]:.1f}",
                     pct(metrics["individual_rout_probabilities"][name])))
    lines += ["", "Characters"]
    lines.append(_table(["Name", "Faction", "Survives", "CI", "Dies", "CI", "Falls first", "Avg HP (alive)", "Routs"], rows))

    if histogram:
        lines += ["", "Remaining health (share of combats)"]
        for name, member in metrics["members"].items():
            buckets = health_histogram(metrics["remaining_health_distribution"][name], member["max_health"])
            top = max(buckets.values()) or 1
            lines.append(f"{name} (max {member['max_health']})")
            for label, count in buckets.items():
                bar = "#" * round(BAR_WIDTH * count / top)
                lines.append(f"  {label:>8} {bar:<{BAR_WIDTH}} {pct(count / total)}")
    return "\n".join(lines)


def _delta(value, base):
    return f"{100 * (value - base):+.1f}"


def format_comparison(outcomes):
    """Tables of win chance per faction and survival per character, with the change against the base."""
    base = outcomes[0]["metrics"]
    total = base["total_battles"]
    level = int(round(100 * base["confidence_level"]))
    lines = [f"Comparison of {len(outcomes)} scenarios, {total} combats each, same seed "
             f"(deltas in percentage points against '{outcomes[0]['name']}', {level}% CI in brackets)"]

    factions = list(base["survival_probabilities"])
    for outcome in outcomes[1:]:
        factions += [f for f in outcome["metrics"]["survival_probabilities"] if f not in factions]
    rows = []
    for outcome in outcomes:
        m = outcome["metrics"]
        row = [outcome["name"]]
        for faction in factions:
            p = m["survival_probabilities"].get(faction)
            if p is None:
                row.append("-")
                continue
            interval = pct_interval(m["confidence_intervals"]["survival_probabilities"][faction])
            row.append(f"{pct(p)} {interval}" + ("" if outcome is outcomes[0] else f" {_delta(p, base['survival_probabilities'].get(faction, 0))}"))
        rows.append(row)
    lines += ["", "Chance of winning", _table(["Scenario"] + factions, rows)]

    names = []
    for outcome in outcomes:
        names += [n for n in outcome["metrics"]["members"] if n not in names]
    rows = []
    for outcome in outcomes:
        m = outcome["metrics"]
        row = [outcome["name"]]
        for name in names:
            p = m["individual_survival_probabilities"].get(name)
            row.append("-" if p is None else pct(p) + ("" if outcome is outcomes[0] or name not in base["members"]
                                                         else f" {_delta(p, base['individual_survival_probabilities'][name])}"))
        rows.append(row)
    lines += ["", "Survival per character", _table(["Scenario"] + names, rows)]
    lines += ["", "Rounds per combat (mean): " + ", ".join(
        f"{o['name']} {o['metrics']['rounds']['mean']:.1f}" for o in outcomes if o["metrics"].get("rounds"))]
    return "\n".join(lines)


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def metrics_rows(metrics):
    """One CSV row per character."""
    intervals = metrics["confidence_intervals"]
    rows = []
    for name, member in metrics["members"].items():
        survival_low, survival_high = intervals["individual_survival_probabilities"][name]
        death_low, death_high = intervals["individual_death_probabilities"][name]
        rows.append({
            "faction": member["faction"],
            "name": name,
            "survival": metrics["individual_survival_probabilities"][name],
            "survival_ci_low": survival_low,
            "survival_ci_high": survival_high,
            "death": metrics["individual_death_probabilities"][name],
            "death_ci_low": death_low,
            "death_ci_high": death_high,
            "falls_first": metrics["first_death_probabilities"][name],
            "average_remaining_health": metrics["individual_average_remaining_health"][name],
            "rout": metrics["individual_rout_probabilities"][name],
        })
    return rows


def comparison_rows(outcomes):
    """One CSV row per scenario and faction."""
    base = outcomes[0]["metrics"]["survival_probabilities"]
    rows = []
    for outcome in outcomes:
        m = outcome["metrics"]
        for faction, p in m["survival_probabilities"].items():
            low, high = m["confidence_intervals"]["survival_probabilities"][faction]
            rows.append({"scenario": outcome["name"], "faction": faction, "win_probability": p,
                         "ci_low": low, "ci_high": high, "delta_vs_base": p - base.get(faction, 0),
                         "rounds_mean": m.get("rounds", {}).get("mean")})
    return rows


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
