import json

import pytest

from src import echarts
from src.compare import run_comparison
from src.loader import create_characters, load_inventory, load_simulation_config
from src.palette import DARK, LIGHT
from src.simulation import Simulation
from tests.helpers import make_character, make_faction


@pytest.fixture(scope="module")
def metrics():
    config = load_simulation_config("sim/job1.json")
    sim = Simulation(create_characters(config["factions"], load_inventory("db/db.json")), seed=1)
    return sim.gather_metrics(sim.run_simulation(400, keep_logs=0))


def _series(option, kind):
    return [s for s in option["series"] if s["type"] == kind]


@pytest.mark.parametrize("theme", [LIGHT, DARK])
def test_every_option_is_json_serialisable(metrics, theme):
    for build in echarts.CHARTS.values():
        json.dumps(build(metrics, theme))
    for name in metrics["members"]:
        json.dumps(echarts.health_distribution(metrics, name, theme))


def test_faction_colors_follow_the_job_order_in_both_themes(metrics):
    assert list(echarts.faction_colors(metrics, LIGHT).values()) == list(LIGHT.series[:2])
    assert list(echarts.faction_colors(metrics, DARK).values()) == list(DARK.series[:2])


def test_win_chart_has_a_bar_per_faction_and_a_whisker_row_each(metrics):
    option = echarts.win_probabilities(metrics)
    assert [s["name"] for s in _series(option, "bar")] == ["Joueurs", "Faction2"]
    hover = _series(option, "custom")[0]
    assert len(hover["data"]) == 2
    index, low, high, tip, text = hover["data"][0]
    assert low <= 100 * metrics["survival_probabilities"]["Joueurs"] <= high
    assert "Joueurs" in tip and text.endswith("%")
    assert ":renderItem" in hover and ":formatter" in hover["tooltip"]


def test_bars_have_a_thin_rounded_data_end_and_the_faction_colour(metrics):
    for bar in _series(echarts.survival(metrics), "bar"):
        assert bar["barWidth"] <= 24
        assert bar["itemStyle"]["borderRadius"] == [0, 4, 4, 0]
    colors = {s["name"]: s["itemStyle"]["color"] for s in _series(echarts.survival(metrics), "bar")}
    assert colors == dict(zip(["Joueurs", "Faction2"], LIGHT.series))


def test_survival_rows_line_up_with_the_characters_and_carry_a_tooltip(metrics):
    option = echarts.survival(metrics)
    assert option["yAxis"]["data"] == list(metrics["members"])
    for bar in _series(option, "bar"):
        assert len(bar["data"]) == len(metrics["members"])
    tips = [row[3] for row in _series(option, "custom")[0]["data"]]
    assert all("Survives" in tip and "Wounds left" in tip for tip in tips)
    assert option["legend"]["data"] == ["Joueurs", "Faction2"]


def test_survival_bars_only_carry_the_value_of_their_own_faction(metrics):
    option = echarts.survival(metrics)
    monster = list(metrics["members"]).index("Terreur de la Teufel")
    by_faction = {s["name"]: s["data"] for s in _series(option, "bar")}
    assert by_faction["Faction2"][monster] is not None and by_faction["Joueurs"][monster] is None


def test_no_legend_for_a_single_faction():
    alone = Simulation([make_faction("F1", make_character("A"))], seed=1)
    single = alone.gather_metrics(alone.run_simulation(5, keep_logs=0))
    assert "legend" not in echarts.survival(single)


def test_theme_changes_surface_and_text_colours(metrics):
    light, dark = echarts.win_probabilities(metrics, LIGHT), echarts.win_probabilities(metrics, DARK)
    assert light["backgroundColor"] == LIGHT.surface and dark["backgroundColor"] == DARK.surface
    assert light["title"]["textStyle"]["color"] == LIGHT.ink and dark["title"]["textStyle"]["color"] == DARK.ink
    js_light, js_dark = _series(light, "custom")[0][":renderItem"], _series(dark, "custom")[0][":renderItem"]
    assert LIGHT.ink_secondary in js_light and LIGHT.ink in js_light and DARK.ink_secondary not in js_light
    assert DARK.ink_secondary in js_dark and DARK.ink in js_dark and LIGHT.ink_secondary not in js_dark


def test_health_distribution_shares_add_up_to_all_the_combats(metrics):
    name = "Amris Pluiedebraise"
    option = echarts.health_distribution(metrics, name)
    data = option["series"][0]["data"]
    assert sum(item["count"] for item in data) == metrics["total_battles"]
    assert sum(item["value"] for item in data) == pytest.approx(100)
    assert option["xAxis"]["data"][0] == "dead" and data[0]["count"] > 0
    labelled = [item for item in data if "label" in item]
    assert 1 <= len(labelled) <= 2  # only the dead bar and the tallest one


def test_health_distribution_uses_the_colour_of_the_faction(metrics):
    option = echarts.health_distribution(metrics, "Terreur de la Teufel")
    assert option["series"][0]["data"][0]["itemStyle"]["color"] == LIGHT.series[1]


def test_heatmap_cells_are_percentages_by_location(metrics):
    option = echarts.hit_locations(metrics)
    cells = option["series"][0]["data"]
    names = list(metrics["members"])
    for row in range(len(names)):
        total = sum(c["value"][2] for c in cells if c["value"][1] == row)
        assert total == pytest.approx(100, abs=1.5)  # rounding of each cell
    assert {c["value"][0] for c in cells} <= set(range(6))
    assert option["visualMap"]["inRange"]["color"] == list(LIGHT.sequential)


def test_heatmap_skips_characters_who_were_never_hit(metrics):
    edited = dict(metrics, hit_locations=dict(metrics["hit_locations"], **{"Else Sigloben": {}}))
    cells = echarts.hit_locations(edited)["series"][0]["data"]
    row = list(metrics["members"]).index("Else Sigloben")
    assert not [c for c in cells if c["value"][1] == row]


def test_heatmap_text_stays_readable_on_both_themes(metrics):
    def colours(theme):
        cells = echarts.hit_locations(metrics, "hits", theme)["series"][0]["data"]
        peak = max(c["value"][2] for c in cells)
        return {c["label"]["color"]: c["value"][2] / peak for c in cells}

    # on the light theme the darkest cells get white text, on the dark theme the lightest ones get dark text
    assert max(v for c, v in colours(LIGHT).items() if c == "#0b0b0b") < 0.5
    assert min(v for c, v in colours(DARK).items() if c == "#0b0b0b") >= 0.5


def test_damage_heatmap_has_its_own_title(metrics):
    assert "damage" in echarts.hit_locations(metrics, "damage")["title"]["text"]
    assert "damage" in echarts.CHARTS["Where the damage lands"](metrics)["title"]["text"]


def test_comparison_shows_the_change_against_the_base():
    config = load_simulation_config("sim/job1.json")
    outcomes = run_comparison(config, load_inventory("db/db.json"),
                              [{"name": "no Else", "remove_members": ["Else Sigloben"]}], 100, seed=1)
    option = echarts.comparison(outcomes)
    rows = _series(option, "custom")[0]["data"]
    assert [r[4].split(" (")[0].endswith("%") for r in rows] == [True, True]
    assert "(" not in rows[0][4] and "(" in rows[1][4]
    assert option["yAxis"]["data"] == ["base", "no Else"]


def test_chart_height_grows_with_the_number_of_rows():
    assert echarts.chart_height(2) < echarts.chart_height(8)
