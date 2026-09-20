"""Interactive charts as Apache ECharts option dictionaries (rendered by NiceGUI, testable without a browser).

Same design rules as the PNG charts in plots.py: one colour per faction kept for its whole roster, sequential blue
for the heatmap, thin marks with a rounded data end, hairline grid, text in ink colours, a value on every bar.
Hovering a row shows a tooltip with the exact figures. Keys starting with ':' hold JavaScript for ECharts.
"""
import json

from src.character import LOCATIONS
from src.palette import LIGHT, THEMES
from src.report import health_histogram

LOCATION_LABELS = {"Head": "Head", "Left Arm": "Left arm", "Right Arm": "Right arm", "Body": "Body",
                   "Left Leg": "Left leg", "Right Leg": "Right leg"}
ROW_HEIGHT = 46
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def faction_colors(metrics, theme=LIGHT):
    """Colour of each faction, by its position in the job (stable whatever is displayed)."""
    return {faction: theme.series[i % len(theme.series)] for i, faction in enumerate(metrics["survival_probabilities"])}


def _pct(value):
    return f"{100 * value:.1f}%"


def _subtitle(metrics):
    level = int(round(100 * metrics["confidence_level"]))
    return f"{metrics['total_battles']:,} combats, whiskers show the {level}% confidence interval"


def _base(theme, title, subtitle):
    return {
        "backgroundColor": theme.surface,
        "animation": False,
        "textStyle": {"color": theme.ink_secondary, "fontFamily": FONT},
        "title": {"text": title, "subtext": subtitle, "left": 12, "top": 8,
                  "textStyle": {"color": theme.ink, "fontSize": 15, "fontWeight": 600, "fontFamily": FONT},
                  "subtextStyle": {"color": theme.ink_secondary, "fontSize": 12, "fontFamily": FONT}},
        "tooltip": {"confine": True, "backgroundColor": theme.surface, "borderColor": theme.axis,
                    "textStyle": {"color": theme.ink, "fontFamily": FONT, "fontSize": 12}},
    }


def _axis_text(theme, size=12):
    return {"color": theme.ink_muted, "fontSize": size, "fontFamily": FONT}


def _hairline(theme):
    return {"lineStyle": {"color": theme.grid, "width": 1, "type": "solid"}}


def _legend(theme, names):
    return {"data": names, "right": 12, "top": 10, "icon": "roundRect", "itemWidth": 10, "itemHeight": 10,
            "textStyle": {"color": theme.ink_secondary, "fontFamily": FONT, "fontSize": 12}}


def _row_renderer(theme):
    """JavaScript drawing, for each row of a horizontal bar chart, the confidence whisker, the value at its tip
    and a transparent full-width target for the tooltip."""
    return f"""(params, api) => {{
  const index = api.value(0);
  const low = api.coord([api.value(1), index]);
  const high = api.coord([api.value(2), index]);
  const band = api.size([0, 1])[1];
  const cap = 5;
  const line = (x1, y1, x2, y2) => ({{type: 'line', shape: {{x1, y1, x2, y2}}, silent: true,
    style: {{stroke: {json.dumps(theme.ink_secondary)}, lineWidth: 1, fill: null}}}});
  return {{type: 'group', children: [
    {{type: 'rect', shape: {{x: params.coordSys.x, y: low[1] - band / 2, width: params.coordSys.width, height: band}},
      style: {{fill: 'rgba(0,0,0,0)'}}}},
    line(low[0], low[1], high[0], high[1]),
    line(low[0], low[1] - cap, low[0], low[1] + cap),
    line(high[0], high[1] - cap, high[0], high[1] + cap),
    {{type: 'text', silent: true, style: {{text: api.value(4), x: high[0] + 8, y: high[1], textVerticalAlign: 'middle',
      fill: {json.dumps(theme.ink)}, font: '12px system-ui, sans-serif'}}}}
  ]}};
}}"""


def interval_bars(theme, title, subtitle, rows, colors, legend=False):
    """Horizontal bars (values 0..1) with confidence whiskers.

    `rows` are dicts with label, group (selects the colour and the legend entry), value, low, high, tip (HTML for the
    tooltip) and text (the value written at the tip of the whisker).
    """
    groups = list(dict.fromkeys(row["group"] for row in rows))
    series = []
    for group in groups:
        data = [{"value": 100 * row["value"], "itemStyle": {"color": colors[row["group"]], "borderRadius": [0, 4, 4, 0]}}
                if row["group"] == group else None for row in rows]
        series.append({"type": "bar", "name": group, "stack": "rows", "barWidth": 18, "data": data, "z": 2, "silent": True,
                       "itemStyle": {"color": colors[group], "borderRadius": [0, 4, 4, 0]}})
    series.append({
        "type": "custom", "name": "hover", "z": 3, "coordinateSystem": "cartesian2d",
        "encode": {"x": [1, 2], "y": 0},
        ":renderItem": _row_renderer(theme),
        "tooltip": {"trigger": "item", ":formatter": "(p) => p.value[3]"},
        "data": [[i, 100 * row["low"], 100 * row["high"], row["tip"], row["text"]] for i, row in enumerate(rows)],
    })
    option = _base(theme, title, subtitle)
    option.update({
        "grid": {"left": 12, "right": 90, "top": 78, "bottom": 12, "containLabel": True},
        "xAxis": {"type": "value", "min": 0, "max": 100, "axisLabel": {**_axis_text(theme), "formatter": "{value}%"},
                  "splitLine": _hairline(theme), "axisLine": {"show": False}, "axisTick": {"show": False}},
        "yAxis": {"type": "category", "inverse": True, "data": [row["label"] for row in rows],
                  "axisLabel": {**_axis_text(theme), "color": theme.ink_secondary},
                  "axisLine": {"lineStyle": {"color": theme.axis}}, "axisTick": {"show": False}},
        "series": series,
    })
    if legend and len(groups) > 1:
        option["legend"] = _legend(theme, groups)
        option["grid"]["top"] = 96
    return option


def chart_height(rows, extra=110):
    return ROW_HEIGHT * rows + extra


def win_probabilities(metrics, theme=LIGHT):
    colors = faction_colors(metrics, theme)
    intervals = metrics["confidence_intervals"]["survival_probabilities"]
    rows = []
    for faction, value in metrics["survival_probabilities"].items():
        low, high = intervals[faction]
        rows.append({"label": faction, "group": faction, "value": value, "low": low, "high": high, "text": _pct(value),
                     "tip": f"<b>{faction}</b><br/>Wins {_pct(value)} of the combats<br/>{_pct(low)} to {_pct(high)} "
                            f"({int(round(100 * metrics['confidence_level']))}% interval)<br/>"
                            f"Wounds left when winning: {metrics['average_remaining_health'][faction]:.1f}"})
    subtitle = _subtitle(metrics) + (f", {metrics['draws']} draws" if metrics["draws"] else "")
    return interval_bars(theme, "Chance of winning", subtitle, rows, colors)


def survival(metrics, theme=LIGHT):
    colors = faction_colors(metrics, theme)
    intervals = metrics["confidence_intervals"]
    rows = []
    for name, member in metrics["members"].items():
        value = metrics["individual_survival_probabilities"][name]
        low, high = intervals["individual_survival_probabilities"][name]
        rows.append({
            "label": name, "group": member["faction"], "value": value, "low": low, "high": high, "text": _pct(value),
            "tip": (f"<b>{name}</b> ({member['faction']})<br/>Survives {_pct(value)} [{_pct(low)} to {_pct(high)}]<br/>"
                    f"Dies {_pct(metrics['individual_death_probabilities'][name])}, falls first "
                    f"{_pct(metrics['first_death_probabilities'][name])}<br/>"
                    f"Routs {_pct(metrics['individual_rout_probabilities'][name])}<br/>"
                    f"Wounds left when alive: {metrics['individual_average_remaining_health'][name]:.1f} of {member['max_health']}")})
    return interval_bars(theme, "Chance of surviving",
                         _subtitle(metrics) + " (fleeing or surrendering counts as surviving)", rows, colors, legend=True)


def comparison(outcomes, faction=None, theme=LIGHT):
    """Win chance of one faction across the scenarios of a comparison, with the change against the base."""
    base = outcomes[0]["metrics"]
    faction = faction or next(iter(base["survival_probabilities"]))
    color = faction_colors(base, theme).get(faction, theme.series[0])
    reference = base["survival_probabilities"].get(faction, 0)
    rows = []
    for outcome in outcomes:
        metrics = outcome["metrics"]
        value = metrics["survival_probabilities"].get(faction, 0)
        low, high = metrics["confidence_intervals"]["survival_probabilities"].get(faction, (0, 0))
        delta = "" if outcome is outcomes[0] else f" ({100 * (value - reference):+.1f})"
        rows.append({"label": outcome["name"], "group": faction, "value": value, "low": low, "high": high,
                     "text": _pct(value) + delta,
                     "tip": f"<b>{outcome['name']}</b><br/>{faction} wins {_pct(value)} [{_pct(low)} to {_pct(high)}]{delta}"})
    return interval_bars(theme, f"Chance of winning for {faction}",
                         _subtitle(base) + " each, same seed, change in points against the base scenario", rows,
                         {faction: color})


def health_distribution(metrics, name, theme=LIGHT):
    """Share of combats ending with each amount of remaining Wounds, for one character."""
    member = metrics["members"][name]
    total = metrics["total_battles"]
    color = faction_colors(metrics, theme)[member["faction"]]
    buckets = health_histogram(metrics["remaining_health_distribution"][name], member["max_health"])
    shares = [100 * count / total for count in buckets.values()]
    tallest = shares.index(max(shares))
    data = []
    for i, (label, count) in enumerate(buckets.items()):
        item = {"value": shares[i], "count": count, "itemStyle": {"color": color, "borderRadius": [4, 4, 0, 0]}}
        if i in (0, tallest) and shares[i] >= 0.5:
            text = f"{shares[i]:.0f}%" if shares[i] >= 10 else f"{shares[i]:.1f}%"
            item["label"] = {"show": True, "position": "top", "formatter": text, "color": theme.ink, "fontSize": 11}
        data.append(item)
    option = _base(theme, name, f"max {member['max_health']} Wounds")
    option["title"].update({"textStyle": {"color": theme.ink, "fontSize": 13, "fontWeight": 600, "fontFamily": FONT},
                            "subtextStyle": {"color": theme.ink_muted, "fontSize": 11, "fontFamily": FONT}})
    option.update({
        "grid": {"left": 8, "right": 12, "top": 62, "bottom": 8, "containLabel": True},
        "xAxis": {"type": "category", "data": list(buckets), "axisLabel": {**_axis_text(theme, 11), "rotate": 45},
                  "axisLine": {"lineStyle": {"color": theme.axis}}, "axisTick": {"show": False}},
        "yAxis": {"type": "value", "min": 0, "max": 112, "interval": 50, "splitLine": _hairline(theme),
                  "axisLabel": {**_axis_text(theme, 11), ":formatter": "(v) => v <= 100 ? v + '%' : ''"},
                  "axisLine": {"show": False}},
        "series": [{"type": "bar", "barWidth": "62%", "data": data,
                    "tooltip": {"trigger": "item",
                                ":formatter": "(p) => '<b>' + p.name + '</b> Wounds left<br/>' + p.value.toFixed(1) + "
                                              "'% of the combats (' + p.data.count + ')'"}}],
    })
    return option


def hit_locations(metrics, measure="hits", theme=LIGHT):
    """Heatmap: where each character gets hit (share of the hits taken, or of the damage taken)."""
    key = "damage" if measure == "damage" else "hits"
    names = list(metrics["members"])
    shares = []
    for name in names:
        by_location = metrics["hit_locations"].get(name, {})
        total = sum(entry[key] for entry in by_location.values())
        shares.append([100 * by_location.get(loc, {}).get(key, 0) / total if total else None for loc in LOCATIONS])
    peak = max((v for row in shares for v in row if v is not None), default=1) or 1
    dark = theme.name == "dark"
    data = []
    for y, (name, row) in enumerate(zip(names, shares)):
        for x, value in enumerate(row):
            if value is None:
                continue
            fraction = value / peak
            light_text = fraction < 0.5 if dark else fraction > 0.45
            entry = metrics["hit_locations"][name].get(LOCATIONS[x], {"hits": 0, "damage": 0})
            data.append({"value": [x, y, round(value, 2)], "hits": entry["hits"], "damage": entry["damage"],
                         "label": {"show": True, "formatter": f"{value:.0f}%", "fontSize": 12,
                                   "color": "#ffffff" if light_text else "#0b0b0b"}})
    what = "damage" if key == "damage" else "hits"
    tooltip = (f"(p) => '<b>' + {json.dumps(names)}[p.value[1]] + ', ' + "
               f"{json.dumps([LOCATION_LABELS[loc] for loc in LOCATIONS])}[p.value[0]] + '</b><br/>' + "
               f"p.value[2].toFixed(1) + '% of the {what}<br/>' + p.data.hits + ' hits, ' + p.data.damage + ' damage'")
    option = _base(theme, f"Where the {what} {'lands' if key == 'damage' else 'land'}", f"Share of the {what} taken by each character, by body location")
    option["tooltip"]["trigger"] = "item"
    option.update({
        "grid": {"left": 12, "right": 84, "top": 96, "bottom": 12, "containLabel": True},
        "xAxis": {"type": "category", "position": "top", "data": [LOCATION_LABELS[loc] for loc in LOCATIONS],
                  "axisLabel": {**_axis_text(theme), "color": theme.ink_secondary}, "axisLine": {"show": False},
                  "axisTick": {"show": False}, "splitArea": {"show": False}},
        "yAxis": {"type": "category", "inverse": True, "data": names, "axisLabel": {**_axis_text(theme), "color": theme.ink_secondary},
                  "axisLine": {"show": False}, "axisTick": {"show": False}},
        "visualMap": {"min": 0, "max": round(peak, 1), "calculable": False, "orient": "vertical", "right": 12, "top": 96,
                      "itemHeight": 140, "inRange": {"color": list(theme.sequential)},
                      "text": [f"{peak:.0f}%", "0%"], "textStyle": {"color": theme.ink_muted, "fontFamily": FONT, "fontSize": 11}},
        "series": [{"type": "heatmap", "data": data, "itemStyle": {"borderColor": theme.surface, "borderWidth": 2},
                    "emphasis": {"itemStyle": {"borderColor": theme.ink, "borderWidth": 1}},
                    "tooltip": {":formatter": tooltip}}],
    })
    return option


CHARTS = {
    "Chance of winning": win_probabilities,
    "Chance of surviving": survival,
    "Where the hits land": hit_locations,
    "Where the damage lands": lambda metrics, theme=LIGHT: hit_locations(metrics, "damage", theme),
}
