"""Results panel: run the simulation, then browse the metrics, the interactive charts and the fights."""
import copy

from nicegui import run, ui

from src import echarts
from src.combat import DEFAULT_DISTANCE
from src.gui.common import notify_error, notify_problems
from src.jobs import validate_job
from src.loader import create_characters
from src.palette import THEMES
from src.report import csv_text, json_text, log_rows, metrics_rows, pct, pct_interval
from src.simulation import DEFAULT_NUM_SIMULATIONS, Simulation

CHART_TABS = ["Winning", "Surviving", "Wounds", "Hits", "Damage", "Table", "Replay"]


class ResultsPanel:
    def __init__(self, state):
        self.state = state
        self.tab = CHART_TABS[0]
        self.fight = 0
        self.progress = {"done": 0, "total": 1}

    @property
    def theme(self):
        return THEMES["dark" if self.state.dark else "light"]

    # --- layout ---------------------------------------------------------------------

    def build(self):
        settings = self.state.job.get("simulation", {})
        with ui.card().props("flat bordered").classes("w-full"):
            with ui.row().classes("items-end gap-4"):
                self.count = ui.number("Combats", value=settings.get("num_simulations", DEFAULT_NUM_SIMULATIONS),
                                       min=1, format="%.0f").classes("w-32").mark("combats")
                self.distance = ui.number("Distance (yards)", value=settings.get("initial_distance", DEFAULT_DISTANCE),
                                          min=1, format="%.0f").classes("w-36").mark("distance")
                self.seed = ui.number("Seed (optional)", value=None, format="%.0f").classes("w-36").props("clearable").mark("seed")
                self.run_button = ui.button("Run simulation", icon="play_arrow", on_click=self.start).mark("run")
            self.bar = ui.linear_progress(value=0, show_value=False).classes("w-full")
            self.bar.set_visibility(False)
            self.status = ui.label().classes("muted")
        self.timer = ui.timer(0.2, self.tick, active=False)
        self.show()

    def job_changed(self):
        settings = self.state.job.get("simulation", {})
        self.count.set_value(settings.get("num_simulations", DEFAULT_NUM_SIMULATIONS))
        self.distance.set_value(settings.get("initial_distance", DEFAULT_DISTANCE))

    def theme_changed(self):
        self.show.refresh()

    # --- running --------------------------------------------------------------------------

    def read_settings(self):
        try:
            count = int(self.count.value)
            distance = float(self.distance.value)
            seed = None if self.seed.value in (None, "") else int(self.seed.value)
        except (TypeError, ValueError):
            raise ValueError("The number of combats, the distance and the seed must be numbers") from None
        if count <= 0 or distance <= 0:
            raise ValueError("The number of combats and the distance must be positive")
        return count, distance, seed

    async def start(self):
        problems = validate_job(self.state.job, self.state.inventory)
        if problems:
            notify_problems("The job cannot be run", problems)
            return
        try:
            count, distance, seed = self.read_settings()
        except ValueError as error:
            notify_error(str(error))
            return
        self.state.job.setdefault("simulation", {}).update({"num_simulations": count, "initial_distance": distance})
        job, inventory, workers = copy.deepcopy(self.state.job), self.state.inventory, self.state.workers
        self.progress = {"done": 0, "total": count}

        def work():
            factions = create_characters(job["factions"], inventory)
            simulation = Simulation(factions, seed=seed, initial_distance=distance)
            results = simulation.run_simulation(count, workers=workers, progress=lambda done, total: self.progress.update(done=done))
            return results, simulation.gather_metrics(results)

        self.run_button.disable()
        self.bar.set_value(0)
        self.bar.set_visibility(True)
        self.status.set_text(f"Running {count:,} combats...")
        self.timer.activate()
        try:
            results, metrics = await run.io_bound(work)
        except Exception as error:  # reported to the user instead of leaving the interface stuck
            notify_error(f"The simulation failed: {error}")
            return
        finally:
            self.timer.deactivate()
            self.bar.set_visibility(False)
            self.run_button.enable()
        self.status.set_text(f"Done: {count:,} combats")
        self.state.add_run(results, metrics)
        self.fight = 0
        self.show.refresh()

    def tick(self):
        self.bar.set_value(self.progress["done"] / max(self.progress["total"], 1))

    # --- results ----------------------------------------------------------------------------

    @ui.refreshable_method
    def show(self):
        run_ = self.state.run
        if run_ is None:
            with ui.card().props("flat bordered").classes("w-full items-center p-8"):
                ui.icon("insights", size="xl").classes("muted")
                ui.label("Run a simulation to see the results.").classes("muted")
            return
        metrics = run_.metrics
        with ui.row().classes("w-full items-center gap-3"):
            labels = {i: f"Run {i + 1} at {r.created}: " + ", ".join(f"{f} {pct(p)}" for f, p in r.metrics["survival_probabilities"].items())
                      for i, r in enumerate(self.state.runs)}
            ui.select(labels, value=self.state.current_run, label="Run", on_change=self.change_run).classes("w-96").props("dense outlined").mark("run-select")
            ui.space()
            ui.button("JSON", icon="download", on_click=lambda: self.download("json")).props("flat").mark("download-json")
            ui.button("CSV", icon="download", on_click=lambda: self.download("csv")).props("flat").mark("download-csv")
            ui.button("Charts (PNG)", icon="image", on_click=lambda: self.download("png")).props("flat").mark("download-png")
        self.summary(metrics)
        with ui.tabs(value=self.tab, on_change=self.change_tab).classes("w-full").props("dense align=left no-caps") as tabs:
            for name in CHART_TABS:
                ui.tab(name)
        with ui.tab_panels(tabs, value=self.tab).classes("w-full").props("keep-alive=false"):
            with ui.tab_panel("Winning"):
                self.chart(echarts.win_probabilities(metrics, self.theme), echarts.chart_height(len(metrics["survival_probabilities"])))
            with ui.tab_panel("Surviving"):
                self.chart(echarts.survival(metrics, self.theme), echarts.chart_height(len(metrics["members"]), 130))
            with ui.tab_panel("Wounds"):
                with ui.grid().classes("w-full grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-4"):
                    for name in metrics["members"]:
                        self.chart(echarts.health_distribution(metrics, name, self.theme), 260)
            with ui.tab_panel("Hits"):
                self.chart(echarts.hit_locations(metrics, "hits", self.theme), echarts.chart_height(len(metrics["members"]), 140))
            with ui.tab_panel("Damage"):
                self.chart(echarts.hit_locations(metrics, "damage", self.theme), echarts.chart_height(len(metrics["members"]), 140))
            with ui.tab_panel("Table"):
                self.table(metrics)
            with ui.tab_panel("Replay"):
                self.replay(run_)

    def change_run(self, event):
        self.state.current_run = event.value
        self.fight = 0
        self.show.refresh()

    def change_tab(self, event):
        self.tab = event.value

    def chart(self, option, height):
        return ui.echart(option).classes("w-full").style(f"height: {height}px; background: {self.theme.surface}; border-radius: 6px")

    def summary(self, metrics):
        colors = echarts.faction_colors(metrics, self.theme)
        intervals = metrics["confidence_intervals"]["survival_probabilities"]
        with ui.row().classes("w-full gap-4"):
            for faction, value in metrics["survival_probabilities"].items():
                with ui.card().props("flat bordered").classes("min-w-48"):
                    with ui.row().classes("items-center gap-2"):
                        ui.element("div").style(f"width: 10px; height: 10px; border-radius: 2px; background: {colors[faction]}")
                        ui.label(faction).classes("text-subtitle2")
                    ui.label(pct(value)).classes("text-h4")
                    ui.label(f"chance of winning {pct_interval(intervals[faction])}").classes("text-caption muted")
            with ui.card().props("flat bordered").classes("min-w-48"):
                ui.label("Combat length").classes("text-subtitle2")
                rounds = metrics.get("rounds") or {}
                ui.label(f"{rounds.get('mean', 0):.1f} rounds").classes("text-h4")
                ui.label(f"median {rounds.get('median', 0):g}, max {rounds.get('max', 0)}, {metrics['draws']} draws"
                         f" over {metrics['total_battles']:,} combats").classes("text-caption muted")

    def table(self, metrics):
        rows = []
        for row in metrics_rows(metrics):
            name = row["name"]
            rows.append({"name": name, "faction": row["faction"],
                         "survives": f"{pct(row['survival'])} {pct_interval((row['survival_ci_low'], row['survival_ci_high']))}",
                         "dies": f"{pct(row['death'])} {pct_interval((row['death_ci_low'], row['death_ci_high']))}",
                         "first": pct(row["falls_first"]), "hp": f"{row['average_remaining_health']:.1f}", "rout": pct(row["rout"])})
        columns = [{"name": k, "label": label, "field": k, "align": "left"} for k, label in
                   [("name", "Name"), ("faction", "Faction"), ("survives", "Survives"), ("dies", "Dies"),
                    ("first", "Falls first"), ("hp", "Wounds left (alive)"), ("rout", "Routs")]]
        ui.table(columns=columns, rows=rows, row_key="name").classes("w-full").props("flat bordered dense")

    def replay(self, run_):
        if not run_.logs:
            ui.label("No fight log was kept for this run.").classes("muted")
            return
        options = {i: f"Fight {i + 1}" for i in range(run_.logs)}
        selector = ui.select(options, value=min(self.fight, run_.logs - 1), label="Fight").classes("w-48").props("dense outlined").mark("fight-select")
        table_area = ui.column().classes("w-full")

        def render(index):
            self.fight = index
            table_area.clear()
            columns = [{"name": k, "label": label, "field": k, "align": "left"} for k, label in
                       [("action", "Action"), ("attacker", "Attacker"), ("target", "Target"), ("roll", "Roll"),
                        ("dr", "DR"), ("damage", "Damage"), ("target_hp", "Target HP")]]
            rows = [dict(row, id=i) for i, row in enumerate(log_rows(run_.results[index]["action_log"]))]
            with table_area:
                ui.table(columns=columns, rows=rows, row_key="id", pagination={"rowsPerPage": 25}).classes("w-full").props("flat bordered dense")

        selector.on_value_change(lambda e: render(e.value))
        render(min(self.fight, run_.logs - 1))

    def download(self, kind):
        run_ = self.state.run
        if run_ is None:
            return
        if kind == "json":
            ui.download(json_text({"job": self.state.job, "metrics": run_.metrics}).encode("utf-8"), "results.json")
        elif kind == "csv":
            ui.download(csv_text(metrics_rows(run_.metrics)).encode("utf-8"), "results.csv")
        else:
            from src.plots import charts_zip
            ui.download(charts_zip(run_.metrics), "charts.zip")
