"""Charts of the simulation metrics (matplotlib, no pyplot: figures can be saved or embedded in Tk).

Design: one hue per faction, kept for its whole roster (a filter never repaints); sequential blue for the
heatmap; thin marks, hairline grid, text in ink colors and never in a series color. Three of the eight series
colors are below 3:1 contrast on the surface, so every bar carries a visible value label.
"""
import os

from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch, Rectangle

from src.character import LOCATIONS
from src.report import health_histogram

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQUENTIAL_MAP = LinearSegmentedColormap.from_list("blue", SEQUENTIAL)

FONT = 9
BAR = 0.42  # bar thickness as a share of its row
ROW_HEIGHT = 0.5  # inches per row
LOCATION_LABELS = {"Head": "Head", "Left Arm": "L. arm", "Right Arm": "R. arm", "Body": "Body",
                   "Left Leg": "L. leg", "Right Leg": "R. leg"}


def _figure(width, height):
    return Figure(figsize=(width, height), facecolor=SURFACE, dpi=100)


def _title(fig, title, subtitle):
    fig.text(0.02, 0.985, title, ha="left", va="top", fontsize=12, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.02, 0.985 - 0.4 / fig.get_figheight(), subtitle, ha="left", va="top", fontsize=FONT, color=INK_SECONDARY)


def _subtitle(metrics):
    level = int(round(100 * metrics["confidence_level"]))
    return f"{metrics['total_battles']:,} combats, whiskers show the {level}% confidence interval"


def _percent_axis(ax, upper=100):
    ax.set_facecolor(SURFACE)
    ax.set_xlim(0, upper)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.tick_params(axis="x", colors=INK_MUTED, labelsize=FONT, length=0, pad=6)
    ax.tick_params(axis="y", colors=INK_SECONDARY, labelsize=FONT, length=0, pad=6)
    ax.grid(axis="x", color=GRID, linewidth=1, linestyle="-")
    ax.set_axisbelow(True)
    for name, spine in ax.spines.items():
        spine.set_visible(name == "left")
        spine.set_color(AXIS)
        spine.set_linewidth(1)


def faction_colors(metrics):
    """Colour of each faction, by its position in the job (stable whatever is displayed)."""
    return {faction: SERIES[i % len(SERIES)] for i, faction in enumerate(metrics["survival_probabilities"])}


TOP_MARGIN = 0.95  # inches above the plot, for the title and the subtitle
BOTTOM_MARGIN = 0.45


def _rows_figure(rows, left=0.27, right=0.84, width=7.0):
    """A figure with one axes sized for `rows` bars, and the axes."""
    height = TOP_MARGIN + BOTTOM_MARGIN + ROW_HEIGHT * rows
    fig = _figure(width, height)
    ax = fig.add_axes([left, BOTTOM_MARGIN / height, right - left, ROW_HEIGHT * rows / height])
    return fig, ax


def _bars_with_intervals(ax, labels, values, intervals, colors, deltas=None):
    """Horizontal bars, one per row, with a confidence whisker and the value at the tip."""
    ys = list(range(len(labels)))
    ax.barh(ys, [100 * v for v in values], height=BAR, color=colors, linewidth=0, zorder=2)
    for y, value, (low, high) in zip(ys, values, intervals):
        ax.plot([100 * low, 100 * high], [y, y], color=INK_SECONDARY, linewidth=1, zorder=3, solid_capstyle="butt")
        for edge in (low, high):
            ax.plot([100 * edge] * 2, [y - 0.12, y + 0.12], color=INK_SECONDARY, linewidth=1, zorder=3)
    for i, (y, value, (low, high)) in enumerate(zip(ys, values, intervals)):
        text = f"{100 * value:.1f}%" + (f"  ({deltas[i]:+.1f})" if deltas and deltas[i] is not None else "")
        ax.text(100 * high + 1.5, y, text, va="center", ha="left", fontsize=FONT, color=INK, clip_on=False)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels)
    ax.set_ylim(len(labels) - 0.5, -0.5)  # first row on top


def plot_win_probabilities(metrics):
    factions = list(metrics["survival_probabilities"])
    colors = faction_colors(metrics)
    fig, ax = _rows_figure(len(factions), left=0.22)
    _bars_with_intervals(ax, factions, [metrics["survival_probabilities"][f] for f in factions],
                         [metrics["confidence_intervals"]["survival_probabilities"][f] for f in factions],
                         [colors[f] for f in factions])
    _percent_axis(ax)
    _title(fig, "Chance of winning", _subtitle(metrics) + (f", {metrics['draws']} draws" if metrics["draws"] else ""))
    return fig


def _character_rows(metrics):
    colors = faction_colors(metrics)
    names = list(metrics["members"])
    return names, [colors[metrics["members"][n]["faction"]] for n in names]


def _faction_legend(fig, metrics, anchor=(0.98, 0.985)):
    colors = faction_colors(metrics)
    if len(colors) < 2:
        return
    handles = [Patch(facecolor=c, label=f, linewidth=0) for f, c in colors.items()]
    legend = fig.legend(handles=handles, loc="upper right", bbox_to_anchor=anchor, ncol=len(handles), frameon=False,
                        fontsize=FONT, handlelength=1, handleheight=1)
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)


def plot_survival(metrics):
    names, colors = _character_rows(metrics)
    fig, ax = _rows_figure(len(names))
    _bars_with_intervals(ax, names, [metrics["individual_survival_probabilities"][n] for n in names],
                         [metrics["confidence_intervals"]["individual_survival_probabilities"][n] for n in names], colors)
    _percent_axis(ax)
    _title(fig, "Chance of surviving", _subtitle(metrics) + " (fleeing or surrendering counts as surviving)")
    _faction_legend(fig, metrics)
    return fig


def plot_health_distribution(metrics, columns=3):
    """One small chart per character: share of combats ending with each amount of remaining Wounds."""
    names, colors = _character_rows(metrics)
    total = metrics["total_battles"]
    rows = -(-len(names) // columns)
    fig = _figure(3.3 * min(columns, len(names)) + 0.6, 1.0 + 2.1 * rows)
    for i, (name, color) in enumerate(zip(names, colors)):
        ax = fig.add_subplot(rows, min(columns, len(names)), i + 1)
        buckets = health_histogram(metrics["remaining_health_distribution"][name], metrics["members"][name]["max_health"])
        shares = [100 * count / total for count in buckets.values()]
        xs = range(len(shares))
        ax.bar(xs, shares, width=0.6, color=color, linewidth=0, zorder=2)
        top = max(shares) or 1
        for x in {0, shares.index(max(shares))}:  # label the "dead" bar and the tallest one only
            if shares[x] >= 0.5:
                ax.text(x, shares[x] + 0.03 * 100, f"{shares[x]:.0f}%" if shares[x] >= 10 else f"{shares[x]:.1f}%",
                        ha="center", va="bottom", fontsize=FONT - 1, color=INK)
        ax.set_facecolor(SURFACE)
        ax.set_ylim(0, 112)
        ax.set_yticks([0, 50, 100])
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
        ax.set_xticks(list(xs))
        ax.set_xticklabels(list(buckets), rotation=60, ha="right", fontsize=FONT - 2)
        ax.set_title(f"{name} (max {metrics['members'][name]['max_health']})", loc="left", fontsize=FONT,
                     color=INK, pad=6)
        ax.tick_params(axis="x", colors=INK_MUTED, length=0, pad=3)
        ax.tick_params(axis="y", colors=INK_MUTED, labelsize=FONT - 1, length=0)
        ax.grid(axis="y", color=GRID, linewidth=1, linestyle="-")
        ax.set_axisbelow(True)
        for spine_name, spine in ax.spines.items():
            spine.set_visible(spine_name == "bottom")
            spine.set_color(AXIS)
    fig.subplots_adjust(left=0.08, right=0.98, top=1 - 0.95 / fig.get_figheight(), bottom=0.7 / fig.get_figheight() + 0.04,
                        hspace=1.05, wspace=0.3)
    _title(fig, "Remaining Wounds at the end of the combat", "Share of combats, dead characters are in the first column")
    _faction_legend(fig, metrics)
    return fig


def plot_hit_locations(metrics, measure="hits"):
    """Heatmap: where each character gets hit (share of the hits taken, or of the damage taken)."""
    names = list(metrics["members"])
    key = "damage" if measure == "damage" else "hits"
    shares = []
    for name in names:
        by_location = metrics["hit_locations"].get(name, {})
        total = sum(entry[key] for entry in by_location.values())
        shares.append([100 * by_location.get(loc, {}).get(key, 0) / total if total else None for loc in LOCATIONS])
    peak = max((v for row in shares for v in row if v is not None), default=1) or 1

    height = 1.5 + ROW_HEIGHT * len(names)
    fig = _figure(7, height)
    ax = fig.add_axes([0.27, 0.62 / height, 0.57, 1 - 1.5 / height])
    for r, row in enumerate(shares):
        for c, value in enumerate(row):
            if value is None:
                ax.text(c, r, "-", ha="center", va="center", fontsize=FONT, color=INK_MUTED)
                continue
            ax.add_patch(Rectangle((c - 0.5, r - 0.5), 1, 1, facecolor=SEQUENTIAL_MAP(value / peak),
                                   edgecolor=SURFACE, linewidth=2))
            dark = value / peak > 0.45
            ax.text(c, r, f"{value:.0f}%", ha="center", va="center", fontsize=FONT,
                    color="#ffffff" if dark else INK)
    ax.set_facecolor(SURFACE)
    ax.set_xlim(-0.5, len(LOCATIONS) - 0.5)
    ax.set_ylim(len(names) - 0.5, -0.5)
    ax.set_xticks(range(len(LOCATIONS)))
    ax.set_xticklabels([LOCATION_LABELS[loc] for loc in LOCATIONS])
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.xaxis.tick_top()
    ax.tick_params(axis="both", length=0, labelsize=FONT, colors=INK_SECONDARY, pad=6)
    for spine in ax.spines.values():
        spine.set_visible(False)

    bar = fig.add_axes([0.89, 0.62 / height, 0.02, 1 - 1.5 / height])
    bar.imshow([[v] for v in reversed([i / 99 for i in range(100)])], aspect="auto", cmap=SEQUENTIAL_MAP, extent=(0, 1, 0, peak))
    bar.set_xticks([])
    bar.yaxis.tick_right()
    bar.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    bar.tick_params(axis="y", length=0, labelsize=FONT - 1, colors=INK_MUTED)
    for spine in bar.spines.values():
        spine.set_visible(False)
    what = "damage" if key == "damage" else "hits"
    _title(fig, f"Where the {what} land", f"Share of the {what} taken by each character, by body location")
    return fig


def plot_comparison(outcomes, faction=None):
    """Win chance of one faction across the scenarios of a comparison, with the change against the base."""
    base = outcomes[0]["metrics"]
    faction = faction or next(iter(base["survival_probabilities"]))
    labels = [o["name"] for o in outcomes]
    values = [o["metrics"]["survival_probabilities"].get(faction, 0) for o in outcomes]
    intervals = [o["metrics"]["confidence_intervals"]["survival_probabilities"].get(faction, (0, 0)) for o in outcomes]
    deltas = [None] + [100 * (v - values[0]) for v in values[1:]]
    color = faction_colors(base).get(faction, SERIES[0])
    fig, ax = _rows_figure(len(outcomes), left=0.32, right=0.8, width=8)
    _bars_with_intervals(ax, labels, values, intervals, [color] * len(outcomes), deltas)
    _percent_axis(ax)
    _title(fig, f"Chance of winning for {faction}", _subtitle(base) + " each, same seed. Change in points against the base scenario")
    return fig


def all_figures(metrics):
    return {
        "win_probabilities": plot_win_probabilities(metrics),
        "survival": plot_survival(metrics),
        "health_distribution": plot_health_distribution(metrics),
        "hit_locations": plot_hit_locations(metrics),
    }


def save_plots(metrics, directory):
    """Write the standard charts as PNG files in `directory`; returns their paths."""
    os.makedirs(directory, exist_ok=True)
    paths = []
    for name, figure in all_figures(metrics).items():
        path = os.path.join(directory, f"{name}.png")
        figure.savefig(path, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
        paths.append(path)
    return paths
