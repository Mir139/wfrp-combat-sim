"""Tkinter interface with three panels: factions editor, item database and results."""
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.jobs import ITEM_TYPES, new_job, validate_job

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_JOB = os.path.join(ROOT, "sim", "job1.json")
DEFAULT_DB = os.path.join(ROOT, "db", "db.json")


def read_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


class SimulationGUI:
    """Holds the job and the item database being edited, shared by the three panels."""

    def __init__(self, root):
        # imported here so that the pure-logic modules stay importable without a display
        from src.gui.factions import FactionsPanel
        from src.gui.items import ItemsPanel
        from src.gui.results import ResultsPanel

        self.root = root
        self.root.title("WFRP Combat Simulator")
        self.root.geometry("1280x780")
        self.job = new_job()
        self.job_path = None
        self.db_data = {"inventory": {item_type: [] for item_type in ITEM_TYPES}}
        self.db_path = None

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.factions_panel = FactionsPanel(self.notebook, self)
        self.items_panel = ItemsPanel(self.notebook, self)
        self.results_panel = ResultsPanel(self.notebook, self)
        self.notebook.add(self.factions_panel, text="Factions")
        self.notebook.add(self.items_panel, text="Items")
        self.notebook.add(self.results_panel, text="Results")
        self.load_defaults()

    @property
    def inventory(self):
        return self.db_data["inventory"]

    def load_defaults(self):
        if os.path.exists(DEFAULT_DB):
            self.set_db(read_json(DEFAULT_DB), DEFAULT_DB)
        if os.path.exists(DEFAULT_JOB):
            self.set_job(read_json(DEFAULT_JOB), DEFAULT_JOB)

    def set_job(self, job, path=None):
        self.job = job
        self.job_path = path
        self.factions_panel.job_changed()
        self.results_panel.job_changed()

    def set_db(self, data, path=None):
        self.db_data = data
        self.db_data.setdefault("inventory", {})
        for item_type in ITEM_TYPES:
            self.db_data["inventory"].setdefault(item_type, [])
        self.db_path = path
        self.items_panel.db_changed()
        self.factions_panel.db_changed()

    def open_job(self):
        path = filedialog.askopenfilename(title="Open a job", filetypes=[("JSON", "*.json")], initialdir=os.path.join(ROOT, "sim"))
        if not path:
            return
        try:
            job = read_json(path)
            if "factions" not in job:
                raise ValueError("this file has no 'factions'")
        except (OSError, ValueError) as error:
            messagebox.showerror("Error", f"Cannot open {path}: {error}")
            return
        self.set_job(job, path)
        problems = validate_job(job, self.inventory)
        if problems:
            messagebox.showwarning("Job loaded with problems", "\n".join(problems[:15]))

    def save_job(self):
        path = filedialog.asksaveasfilename(title="Save the job", defaultextension=".json", filetypes=[("JSON", "*.json")],
                                            initialdir=os.path.join(ROOT, "sim"))
        if path:
            write_json(path, self.job)
            self.job_path = path
            self.factions_panel.job_changed(keep_selection=True)

    def open_db(self):
        path = filedialog.askopenfilename(title="Open an item database", filetypes=[("JSON", "*.json")],
                                          initialdir=os.path.join(ROOT, "db"))
        if not path:
            return
        try:
            data = read_json(path)
            if "inventory" not in data:
                raise ValueError("this file has no 'inventory'")
        except (OSError, ValueError) as error:
            messagebox.showerror("Error", f"Cannot open {path}: {error}")
            return
        self.set_db(data, path)

    def save_db(self):
        path = self.db_path or filedialog.asksaveasfilename(title="Save the item database", defaultextension=".json",
                                                            filetypes=[("JSON", "*.json")], initialdir=os.path.join(ROOT, "db"))
        if path:
            write_json(path, self.db_data)
            self.db_path = path
            self.items_panel.db_changed()


def main():
    root = tk.Tk()
    SimulationGUI(root)
    root.mainloop()
