"""The NiceGUI application: a header with the theme switch and three tabs (factions, items, results)."""
import argparse

from nicegui import ui

from src.gui.factions import FactionsPanel
from src.gui.items import ItemsPanel
from src.gui.results import ResultsPanel
from src.gui.state import AppState
from src.palette import DARK, LIGHT


ui.button.default_props("no-caps")


def register(state):
    """Register the page of the application, working on `state`."""

    @ui.page("/")
    def index():
        ui.colors(primary=LIGHT.series[0])
        ui.add_css(f".muted {{ color: {LIGHT.ink_secondary}; }} .body--dark .muted {{ color: {DARK.ink_secondary}; }}")
        dark = ui.dark_mode(value=state.dark)
        results = ResultsPanel(state)
        factions = FactionsPanel(state, on_job_changed=results.job_changed)
        items = ItemsPanel(state, on_db_changed=lambda: factions.editor.refresh())

        def toggle(event):
            state.dark = event.value
            dark.set_value(event.value)
            results.theme_changed()

        with ui.header().classes("items-center justify-between px-6"):
            ui.label("WFRP Combat Simulator").classes("text-xl font-medium")
            ui.switch("Dark", value=state.dark, on_change=toggle).mark("dark")
        with ui.column().classes("w-full max-w-7xl mx-auto"):
            with ui.tabs().classes("w-full").props("align=left no-caps") as tabs:
                factions_tab = ui.tab("Factions", icon="groups")
                items_tab = ui.tab("Items", icon="inventory_2")
                results_tab = ui.tab("Results", icon="insights")
            with ui.tab_panels(tabs, value=factions_tab).classes("w-full"):
                with ui.tab_panel(factions_tab):
                    factions.build()
                with ui.tab_panel(items_tab):
                    items.build()
                with ui.tab_panel(results_tab):
                    results.build()

    return index


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m src.gui", description="Open the simulator in your browser.")
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on (default: %(default)s)")
    parser.add_argument("--port", type=int, default=8080, help="port (default: %(default)s)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args(argv)
    state = AppState()
    state.load_defaults()
    register(state)
    ui.run(host=args.host, port=args.port, title="WFRP Combat Simulator", reload=False, show=not args.no_browser)
