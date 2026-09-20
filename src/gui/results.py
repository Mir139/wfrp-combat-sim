"""Results panel: run the simulation, browse the metrics and charts, replay a fight, export."""
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from src import plots
from src.combat import DEFAULT_DISTANCE
from src.jobs import validate_job
from src.loader import create_characters
from src.report import format_report, metrics_rows, pct, write_csv, write_json
from src.simulation import DEFAULT_KEEP_LOGS, DEFAULT_NUM_SIMULATIONS, Simulation

MIN_DPI, MAX_DPI = 60, 140

CHARTS = {
    "Chance of winning": plots.plot_win_probabilities,
    "Chance of surviving": plots.plot_survival,
    "Remaining Wounds": lambda metrics: plots.plot_health_distribution(metrics, columns=2),
    "Where the hits land": plots.plot_hit_locations,
    "Where the damage lands": lambda metrics: plots.plot_hit_locations(metrics, "damage"),
}


class ResultsPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.runs = []  # one dict per run: results, metrics, logs, label
        self.figure_canvas = None
        self._drawn_width = 0
        self._shown = None  # the run whose report is displayed
        self._resize_job = None
        self.num_simulations = tk.StringVar(value=str(DEFAULT_NUM_SIMULATIONS))
        self.distance = tk.StringVar(value=str(DEFAULT_DISTANCE))
        self.seed = tk.StringVar()
        self.chart = tk.StringVar(value=next(iter(CHARTS)))
        self._build()

    # --- layout ------------------------------------------------------------

    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X)
        for text, variable, width in (("Combats", self.num_simulations, 8), ("Distance (yards)", self.distance, 6),
                                      ("Seed (optional)", self.seed, 8)):
            ttk.Label(bar, text=text).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Entry(bar, textvariable=variable, width=width).pack(side=tk.LEFT, padx=(0, 14))
        self.run_button = ttk.Button(bar, text="Run simulation", command=self.run)
        self.run_button.pack(side=tk.LEFT)
        self.status = ttk.Label(bar, foreground="#52514e")
        self.status.pack(side=tk.LEFT, padx=12)

        panes = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, pady=8)

        left = ttk.Frame(panes)
        ttk.Label(left, text="Runs").pack(anchor=tk.W)
        self.runs_tree = ttk.Treeview(left, columns=("n", "time", "wins"), show="headings", height=6, selectmode="browse")
        for key, text, width in (("n", "#", 30), ("time", "Time", 60), ("wins", "Chance of winning", 230)):
            self.runs_tree.heading(key, text=text)
            self.runs_tree.column(key, width=width, anchor=tk.W)
        self.runs_tree.pack(fill=tk.X)
        self.runs_tree.bind("<<TreeviewSelect>>", self.on_select)

        replay = ttk.Frame(left)
        replay.pack(fill=tk.X, pady=6)
        ttk.Label(replay, text="Replay fight").pack(side=tk.LEFT)
        self.fight = ttk.Combobox(replay, state="readonly", width=12)
        self.fight.pack(side=tk.LEFT, padx=6)
        ttk.Button(replay, text="Show log", command=self.show_log).pack(side=tk.LEFT)

        export = ttk.Frame(left)
        export.pack(fill=tk.X)
        for text, command in (("Save charts...", self.save_charts), ("Export JSON...", self.export_json),
                              ("Export CSV...", self.export_csv)):
            ttk.Button(export, text=text, command=command).pack(side=tk.LEFT, padx=(0, 4))

        report_holder = ttk.Frame(left)
        report_holder.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.report = tk.Text(report_holder, wrap=tk.NONE, width=58, height=22, font="TkFixedFont", state=tk.DISABLED)
        report_scroll = ttk.Scrollbar(report_holder, orient="horizontal", command=self.report.xview)
        self.report.configure(xscrollcommand=report_scroll.set)
        report_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.report.pack(fill=tk.BOTH, expand=True)
        panes.add(left, weight=3)

        right = ttk.Frame(panes)
        selector = ttk.Frame(right)
        selector.pack(fill=tk.X)
        ttk.Label(selector, text="Chart").pack(side=tk.LEFT)
        box = ttk.Combobox(selector, textvariable=self.chart, values=list(CHARTS), state="readonly", width=24)
        box.pack(side=tk.LEFT, padx=6)
        box.bind("<<ComboboxSelected>>", lambda e: self.draw_chart())
        self.canvas_holder = ttk.Frame(right)
        self.canvas_holder.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.scroll_canvas = tk.Canvas(self.canvas_holder, background=plots.SURFACE, highlightthickness=0, width=600)
        scrollbar = ttk.Scrollbar(self.canvas_holder, orient="vertical", command=self.scroll_canvas.yview)
        self.scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for sequence, delta in (("<Button-4>", -1), ("<Button-5>", 1)):
            self.scroll_canvas.bind(sequence, lambda e, d=delta: self.scroll_canvas.yview_scroll(d, "units"))
        self.scroll_canvas.bind("<Configure>", self.on_canvas_resize)
        self.scroll_canvas.bind("<MouseWheel>", lambda e: self.scroll_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        panes.add(right, weight=4)

    # --- running ---------------------------------------------------------------

    def job_changed(self):
        settings = self.app.job.get("simulation", {})
        self.num_simulations.set(str(settings.get("num_simulations", DEFAULT_NUM_SIMULATIONS)))
        self.distance.set(str(settings.get("initial_distance", DEFAULT_DISTANCE)))

    def run(self):
        job = self.app.job
        problems = validate_job(job, self.app.inventory)
        if problems:
            messagebox.showerror("The job cannot be run", "\n".join(problems[:15]) + ("\n..." if len(problems) > 15 else ""))
            return
        try:
            count = int(self.num_simulations.get())
            distance = float(self.distance.get())
            seed = int(self.seed.get()) if self.seed.get().strip() else None
            if count <= 0 or distance <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid settings", "The number of combats and the distance must be positive numbers, "
                                                     "and the seed a whole number.")
            return
        job.setdefault("simulation", {}).update({"num_simulations": count, "initial_distance": distance})
        self.run_button.config(state=tk.DISABLED)
        self.status.config(text=f"Running {count:,} combats...")
        self.winfo_toplevel().config(cursor="watch")
        self.update_idletasks()
        try:
            factions = create_characters(job["factions"], self.app.inventory)
            sim = Simulation(factions, seed=seed, initial_distance=distance)
            started = time.time()
            results = sim.run_simulation(count, keep_logs=DEFAULT_KEEP_LOGS)
            metrics = sim.gather_metrics(results)
        except Exception as error:  # shown to the user rather than freezing the window
            messagebox.showerror("Error", f"Failed to run the simulation: {error}")
            return
        finally:
            self.run_button.config(state=tk.NORMAL)
            self.winfo_toplevel().config(cursor="")
        self.status.config(text=f"Done in {time.time() - started:.1f} s")
        run = {"results": results, "metrics": metrics, "logs": sum(1 for r in results if r["action_log"] is not None)}
        self.runs.append(run)
        wins = ", ".join(f"{name} {pct(p)}" for name, p in metrics["survival_probabilities"].items())
        iid = self.runs_tree.insert("", 0, iid=str(len(self.runs) - 1),
                                    values=(len(self.runs), time.strftime("%H:%M:%S"), wins))
        self.runs_tree.selection_set(iid)
        self.on_select()

    def current(self):
        selection = self.runs_tree.selection()
        return self.runs[int(selection[0])] if selection else None

    def on_select(self, _event=None):
        run = self.current()
        if run is None or run is self._shown:
            return
        self._shown = run
        self.report.config(state=tk.NORMAL)
        self.report.delete("1.0", tk.END)
        self.report.insert(tk.END, format_report(run["metrics"]))
        self.report.config(state=tk.DISABLED)
        self.fight.config(values=[f"Fight {i + 1}" for i in range(run["logs"])])
        if run["logs"]:
            self.fight.current(0)
        self.draw_chart()

    # --- charts ----------------------------------------------------------------

    def on_canvas_resize(self, event):
        """Redraw the chart when the panel width changes, so it always fits."""
        if self._drawn_width and abs(event.width - self._drawn_width) < 8:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(120, self.draw_chart)

    def draw_chart(self):
        self._resize_job = None
        run = self.current()
        if self.figure_canvas is not None:
            self.figure_canvas.get_tk_widget().destroy()
            self.figure_canvas = None
        if run is None:
            return
        figure = CHARTS[self.chart.get()](run["metrics"])
        available = self.scroll_canvas.winfo_width()
        self._drawn_width = available
        if available > 1:  # scale the whole figure, text included, to the panel width
            figure.set_dpi(min(max(available / figure.get_figwidth(), MIN_DPI), MAX_DPI))
        self.figure_canvas = FigureCanvasTkAgg(figure, master=self.scroll_canvas)
        width, height = (int(v * figure.dpi) for v in figure.get_size_inches())
        widget = self.figure_canvas.get_tk_widget()
        widget.config(width=width, height=height)
        self.scroll_canvas.delete("all")
        self.scroll_canvas.create_window(0, 0, window=widget, anchor=tk.NW, width=width, height=height)
        self.scroll_canvas.configure(scrollregion=(0, 0, width, height))
        self.figure_canvas.draw()

    def save_charts(self):
        run = self.current()
        if run is None:
            return
        directory = filedialog.askdirectory(title="Save the charts in...")
        if directory:
            paths = plots.save_plots(run["metrics"], directory)
            messagebox.showinfo("Charts saved", f"{len(paths)} charts written to {directory}")

    # --- replay and export -----------------------------------------------------------

    def show_log(self):
        run = self.current()
        index = self.fight.current()
        if run is None or index < 0:
            messagebox.showwarning("Replay", "Run a simulation and select a fight first.")
            return
        self.open_details_window(run["results"][index]["action_log"], index)

    def open_details_window(self, action_log, index):
        window = tk.Toplevel(self)
        window.title(f"Fight {index + 1}")
        columns = ("Action", "Attacker", "Target", "Roll", "DR", "Damage", "Target HP")
        tree = ttk.Treeview(window, columns=columns, show="headings")
        for column, width in zip(columns, (100, 150, 150, 70, 70, 60, 90)):
            tree.heading(column, text=column)
            tree.column(column, width=width)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky=tk.NSEW, pady=10)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        window.rowconfigure(0, weight=1)
        window.columnconfigure(0, weight=1)
        self.populate_log(tree, action_log)

    @staticmethod
    def populate_log(tree, action_log):
        for action in action_log:
            kind = action["action"]
            details = action.get("details")
            if kind == "initiate_combat":
                values = ("Initiate Combat", "", "", "", "", "", "")
            elif kind == "engage":
                values = ("Engage", action["attacker"], action["target"], "", "", "", "")
            elif kind == "attack":
                flags = " (critical)" if details["critical"] else " (fumble)" if details["fumble"] else ""
                values = ("Attack" + flags, action["attacker"], action["target"],
                          f"{details['attack_roll']} | {details['enemy_roll']}",
                          f"{details['attack_dr']} | {details['enemy_dr']}", details["damage"], action["enemy_health"])
            elif kind == "ranged_attack":
                flags = " (critical)" if details["critical"] else " (fumble)" if details["fumble"] else ""
                values = ("Ranged Attack" + flags, action["attacker"], action["target"], details["attack_roll"],
                          details["attack_dr"], details["damage"], action["enemy_health"])
            elif kind == "rout":
                values = (f"Rout ({details['outcome']})", action["attacker"], "", details["roll"], "", "", "")
            else:  # move, run, stand_up, reload, bleed
                damage = details.get("damage", "") if isinstance(details, dict) else ""
                values = (kind.replace("_", " ").title(), action["attacker"],
                          action["target"] if action["target"] != action["attacker"] else "", "", "", damage,
                          action.get("enemy_health", ""))
            tree.insert("", tk.END, values=values)

    def export_json(self):
        run = self.current()
        path = run and filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            write_json(path, {"job": self.app.job_path, "metrics": run["metrics"]})

    def export_csv(self):
        run = self.current()
        path = run and filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            write_csv(path, metrics_rows(run["metrics"]))
