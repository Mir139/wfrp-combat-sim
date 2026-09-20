"""Drives the real Tk interface; skipped when there is no display."""
import os
import tkinter as tk
from tkinter import messagebox

import pytest

pytest.importorskip("matplotlib")


@pytest.fixture
def app(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    errors = []
    for name in ("showerror", "showwarning", "showinfo"):
        monkeypatch.setattr(messagebox, name, lambda title, message, **kw: errors.append(message))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **kw: True)
    from src.gui import SimulationGUI
    gui = SimulationGUI(root)
    gui.errors = errors
    root.update()
    yield gui
    root.destroy()


def test_the_default_job_and_database_are_loaded(app):
    panel = app.factions_panel
    assert len(panel.tree.get_children()) == 2
    assert sum(len(panel.tree.get_children(f)) for f in panel.tree.get_children()) == 6
    assert "items" in app.items_panel.count.cget("text")


def test_editing_a_character_updates_the_job(app):
    panel = app.factions_panel
    panel.tree.selection_set("f0m0")
    app.root.update()
    assert panel.vars["name"].get() == "Gunnar Hrolfsson"
    panel.vars["CC"].set("77")
    panel.vars["targeting"].set("weakest")
    panel.apply()
    member = app.job["factions"][0]["members"][0]
    assert member["CC"] == 77 and member["targeting"] == "weakest"
    panel.vars["targeting"].set("")
    panel.apply()
    assert "targeting" not in member


def test_invalid_values_are_rejected_without_changing_the_job(app):
    panel = app.factions_panel
    panel.tree.selection_set("f0m0")
    app.root.update()
    panel.vars["CC"].set("abc")
    panel.apply()
    assert app.job["factions"][0]["members"][0]["CC"] == 45 and app.errors
    panel.vars["CC"].set("45")
    panel.vars["name"].set("Else Sigloben")  # already taken
    panel.apply()
    assert app.job["factions"][0]["members"][0]["name"] == "Gunnar Hrolfsson"


def test_inventory_add_and_remove(app):
    panel = app.factions_panel
    panel.tree.selection_set("f0m0")
    app.root.update()
    before = len(app.job["factions"][0]["members"][0]["inventory"])
    panel.item_type.set("Armor")
    panel.refresh_item_choices()
    panel.item_name.set("Armure lourde")
    panel.add_item()
    assert app.job["factions"][0]["members"][0]["inventory"][-1] == {"type": "armors", "name": "Armure lourde"}
    panel.inventory_list.selection_set(tk.END)
    panel.remove_item()
    assert len(app.job["factions"][0]["members"][0]["inventory"]) == before


def test_add_duplicate_and_remove_characters_and_factions(app):
    panel = app.factions_panel
    panel.tree.selection_set("f1")
    app.root.update()
    panel.add_character()
    panel.duplicate()
    names = [m["name"] for m in app.job["factions"][1]["members"]]
    assert names == ["Terreur de la Teufel", "New character", "New character 2"]
    panel.remove()
    panel.add_faction()
    assert len(app.job["factions"]) == 3 and app.job["factions"][2]["name"] == "Faction 3"


def test_database_editing_and_search(app):
    panel = app.items_panel
    panel.item_type.set("Armors")
    panel.refresh()
    total = len(app.inventory["armors"])
    panel.search.set("lourde")
    assert panel.count.cget("text").startswith("1 of")
    panel.search.set("")
    variables = {"name": tk.StringVar(value="Cotte"), "penalty": tk.StringVar(value="-10% Perception, -10% Discrétion"),
                 "location": tk.StringVar(value="Tête, Corps"), "armor_points": tk.StringVar(value="2"),
                 "attributes": tk.StringVar(value="Flexible")}
    item = panel.read_item("armors", variables, None)
    assert item == {"name": "Cotte", "penalty": ["-10% Perception", "-10% Discrétion"], "location": ["Tête", "Corps"],
                    "armor_points": "2", "attributes": ["Flexible"]}
    variables["armor_points"].set("many")
    with pytest.raises(ValueError):
        panel.read_item("armors", variables, None)
    variables["armor_points"].set("2")
    variables["name"].set("Armure lourde")
    with pytest.raises(ValueError):
        panel.read_item("armors", variables, None)
    assert len(app.inventory["armors"]) == total


def test_running_a_simulation_fills_the_results(app):
    panel = app.results_panel
    panel.num_simulations.set("200")
    panel.seed.set("1")
    panel.run()
    app.root.update()
    assert len(panel.runs) == 1 and panel.runs[0]["metrics"]["total_battles"] == 200
    assert panel.runs[0]["logs"] == 100 and len(panel.fight["values"]) == 100
    assert "200 combats" in panel.report.get("1.0", tk.END)
    for chart in ("Chance of winning", "Chance of surviving", "Remaining Wounds", "Where the hits land", "Where the damage lands"):
        panel.chart.set(chart)
        panel.draw_chart()
        app.root.update()
        assert panel.figure_canvas is not None
    assert not app.errors


def test_a_job_with_problems_is_not_run(app):
    app.job["factions"][0]["members"][0]["inventory"].append({"type": "armors", "name": "Nope"})
    app.results_panel.run()
    assert not app.results_panel.runs
    assert any("Nope" in message for message in app.errors)


def test_the_settings_of_the_job_are_shown_and_saved_back(app):
    panel = app.results_panel
    assert panel.num_simulations.get() == "10000"
    panel.num_simulations.set("50")
    panel.distance.set("20")
    panel.run()
    assert app.job["simulation"]["num_simulations"] == 50 and app.job["simulation"]["initial_distance"] == 20.0
    panel.num_simulations.set("-3")
    panel.run()
    assert len(panel.runs) == 1  # the second run was refused


def test_replaying_a_fight_lists_its_actions(app):
    panel = app.results_panel
    panel.num_simulations.set("30")
    panel.run()
    panel.fight.current(0)
    panel.show_log()
    windows = [w for w in panel.winfo_children() if isinstance(w, tk.Toplevel)]
    tree = [c for c in windows[-1].winfo_children() if c.winfo_class() == "Treeview"][0]
    rows = [tree.item(i, "values") for i in tree.get_children()]
    assert rows[0][0] == "Initiate Combat" and len(rows) > 5
