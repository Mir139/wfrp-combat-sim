"""Factions panel: edit the job (factions, characters, inventories) and import character sheets."""
import copy
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.character import ROUT_BEHAVIORS, TARGETING_STRATEGIES
from src.jobs import BEHAVIORS, CHARACTERISTICS, ITEM_TYPES, character_problems, import_characters, new_character

AUTO = ""  # blank choice: not set, the default applies
TYPE_LABELS = {"melee_weapons": "Melee weapon", "ranged_weapons": "Ranged weapon", "armors": "Armor"}


def unique_name(base, taken):
    if base not in taken:
        return base
    k = 2
    while f"{base} {k}" in taken:
        k += 1
    return f"{base} {k}"


class FactionsPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.selected = None  # ("faction", fi) or ("member", fi, mi)
        self._build()

    # --- layout ------------------------------------------------------------

    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="New job", command=self.new_job).pack(side=tk.LEFT)
        ttk.Button(bar, text="Open job...", command=self.app.open_job).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Save job as...", command=self.app.save_job).pack(side=tk.LEFT)
        ttk.Button(bar, text="Import characters...", command=self.import_dialog).pack(side=tk.LEFT, padx=12)
        self.path_label = ttk.Label(bar, foreground="#52514e")
        self.path_label.pack(side=tk.LEFT, padx=8)

        panes = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, pady=8)

        left = ttk.Frame(panes)
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse", height=20)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        buttons = ttk.Frame(left)
        buttons.pack(fill=tk.X, pady=(6, 0))
        for text, command in (("Add faction", self.add_faction), ("Add character", self.add_character),
                              ("Duplicate", self.duplicate), ("Remove", self.remove)):
            ttk.Button(buttons, text=text, command=command).pack(side=tk.LEFT, padx=(0, 4))
        panes.add(left, weight=1)

        self.form = ttk.Frame(panes, padding=(12, 0))
        panes.add(self.form, weight=2)
        self.vars = {}
        self.widgets = {}  # key -> widgets of the field, to show or hide them
        self._build_form()

    def _build_form(self):
        self.title = ttk.Label(self.form, text="Select a faction or a character", font=("TkDefaultFont", 11, "bold"))
        self.title.grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 8))

        self.fields = ttk.Frame(self.form)
        self.fields.grid(row=1, column=0, columnspan=4, sticky=tk.W)
        self._field("name", "Name", 0, 0, width=28, span=3)
        self._field("health", "Wounds", 1, 0)
        for i, characteristic in enumerate(CHARACTERISTICS):
            self._field(characteristic, characteristic, 1 + (i + 1) // 2, ((i + 1) % 2) * 2)

        tactics = ttk.LabelFrame(self.form, text="Tactics (blank: default)", padding=6)
        tactics.grid(row=2, column=0, columnspan=4, sticky=tk.EW, pady=8)
        self.tactics = tactics
        self._combo("behavior", "Fighting style", [AUTO] + BEHAVIORS, tactics, 0, 0)
        self._combo("targeting", "Targeting", [AUTO] + list(TARGETING_STRATEGIES), tactics, 0, 2)
        self._combo("on_rout", "On rout", [AUTO] + list(ROUT_BEHAVIORS), tactics, 1, 0)
        self.vars["rout_threshold"] = tk.StringVar()
        ttk.Label(tactics, text="Rout threshold").grid(row=1, column=2, sticky=tk.W, padx=(0, 6), pady=2)
        ttk.Entry(tactics, textvariable=self.vars["rout_threshold"], width=8).grid(row=1, column=3, sticky=tk.W)

        self.inventory_frame = ttk.LabelFrame(self.form, text="Inventory", padding=6)
        self.inventory_frame.grid(row=3, column=0, columnspan=4, sticky=tk.NSEW)
        self.form.rowconfigure(3, weight=1)
        self.form.columnconfigure(3, weight=1)
        self.inventory_list = tk.Listbox(self.inventory_frame, height=6, exportselection=False)
        self.inventory_list.grid(row=0, column=0, columnspan=4, sticky=tk.NSEW)
        self.inventory_frame.columnconfigure(0, weight=1)
        self.inventory_frame.rowconfigure(0, weight=1)
        self.item_type = tk.StringVar(value=TYPE_LABELS[ITEM_TYPES[0]])
        self.item_name = tk.StringVar()
        type_box = ttk.Combobox(self.inventory_frame, textvariable=self.item_type, values=list(TYPE_LABELS.values()),
                                state="readonly", width=14)
        type_box.grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        type_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_item_choices())
        self.item_box = ttk.Combobox(self.inventory_frame, textvariable=self.item_name, state="readonly", width=30)
        self.item_box.grid(row=1, column=1, sticky=tk.EW, padx=4, pady=(6, 0))
        ttk.Button(self.inventory_frame, text="Add", command=self.add_item).grid(row=1, column=2, pady=(6, 0))
        ttk.Button(self.inventory_frame, text="Remove selected", command=self.remove_item).grid(row=1, column=3, padx=4, pady=(6, 0))

        self.apply_button = ttk.Button(self.form, text="Apply changes", command=self.apply)
        self.apply_button.grid(row=4, column=0, sticky=tk.W, pady=(10, 0))
        self.set_form_enabled(False)

    def _field(self, key, label, row, column, width=8, span=1):
        self.vars[key] = tk.StringVar()
        text = ttk.Label(self.fields, text=label)
        text.grid(row=row, column=column, sticky=tk.W, padx=(0, 6), pady=2)
        entry = ttk.Entry(self.fields, textvariable=self.vars[key], width=width)
        entry.grid(row=row, column=column + 1, columnspan=span, sticky=tk.W, padx=(0, 18))
        self.widgets[key] = (text, entry)

    def _combo(self, key, label, values, parent, row, column):
        self.vars[key] = tk.StringVar()
        text = ttk.Label(parent, text=label)
        text.grid(row=row, column=column, sticky=tk.W, padx=(0, 6), pady=2)
        combo = ttk.Combobox(parent, textvariable=self.vars[key], values=values, state="readonly", width=12)
        combo.grid(row=row, column=column + 1, sticky=tk.W, padx=(0, 18))
        self.widgets[key] = (text, combo)

    # --- data <-> tree ---------------------------------------------------------

    @property
    def factions(self):
        return self.app.job["factions"]

    def job_changed(self, keep_selection=False):
        self.path_label.config(text=self.app.job_path or "(unsaved job)")
        self.refresh_tree(self.selected if keep_selection else None)

    def db_changed(self):
        self.refresh_item_choices()

    def refresh_tree(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for fi, faction in enumerate(self.factions):
            self.tree.insert("", tk.END, iid=f"f{fi}", text=f"{faction['name']} ({len(faction['members'])})", open=True)
            for mi, member in enumerate(faction["members"]):
                self.tree.insert(f"f{fi}", tk.END, iid=f"f{fi}m{mi}", text=member["name"])
        if select:
            iid = f"f{select[1]}" if select[0] == "faction" else f"f{select[1]}m{select[2]}"
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.selected = tuple(select)
                self.load_form()
                return
        self.selected = None
        self.load_form()

    def on_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        iid = selection[0]
        if "m" in iid:
            fi, mi = iid[1:].split("m")
            self.selected = ("member", int(fi), int(mi))
        else:
            self.selected = ("faction", int(iid[1:]))
        self.load_form()

    def current(self):
        if not self.selected:
            return None
        faction = self.factions[self.selected[1]]
        return faction if self.selected[0] == "faction" else faction["members"][self.selected[2]]

    def set_form_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for child in self.form.winfo_children():
            self._set_state(child, state)

    def _set_state(self, widget, state):
        try:
            widget.configure(state="readonly" if state == "normal" and isinstance(widget, ttk.Combobox) else state)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._set_state(child, state)

    def load_form(self):
        data = self.current()
        for var in self.vars.values():
            var.set("")
        self.inventory_list.delete(0, tk.END)
        self.set_form_enabled(data is not None)
        if data is None:
            self.title.config(text="Select a faction or a character")
            return
        is_member = self.selected[0] == "member"
        self.title.config(text=("Character" if is_member else "Faction") + f": {data['name']}")
        self.vars["name"].set(data["name"])
        for key in ("targeting", "on_rout", "rout_threshold"):
            self.vars[key].set("" if data.get(key) is None else str(data[key]))
        for key in ["health"] + CHARACTERISTICS + ["behavior"]:
            for widget in self.widgets[key]:
                (widget.grid if is_member else widget.grid_remove)()
        if is_member:
            for key in ["health"] + CHARACTERISTICS:
                self.vars[key].set(str(data[key]))
            self.vars["behavior"].set(data.get("behavior") or "")
            for item in data.get("inventory", []):
                self.inventory_list.insert(tk.END, f"{TYPE_LABELS.get(item['type'], item['type'])}: {item['name']}")
        for child in (self.inventory_frame,):
            self._set_state(child, "normal" if is_member else "disabled")
        self.refresh_item_choices()

    def refresh_item_choices(self):
        item_type = next((t for t, label in TYPE_LABELS.items() if label == self.item_type.get()), ITEM_TYPES[0])
        names = [item["name"] for item in self.app.inventory.get(item_type, [])]
        self.item_box.config(values=names)
        if self.item_name.get() not in names:
            self.item_name.set(names[0] if names else "")

    # --- editing ---------------------------------------------------------------------

    def _number(self, key, integer=True):
        text = self.vars[key].get().strip()
        try:
            return int(text) if integer else float(text)
        except ValueError:
            raise ValueError(f"'{key}' must be a number, not '{text}'") from None

    def apply(self):
        data = self.current()
        if data is None:
            return
        try:
            name = self.vars["name"].get().strip()
            if not name:
                raise ValueError("The name cannot be empty")
            changes = {"name": name}
            if self.selected[0] == "member":
                for key in ["health"] + CHARACTERISTICS:
                    changes[key] = self._number(key)
                if changes["health"] <= 0:
                    raise ValueError("'health' must be positive")
            threshold = self.vars["rout_threshold"].get().strip()
            if threshold:
                changes["rout_threshold"] = self._number("rout_threshold", integer=False)
                if not 0 < changes["rout_threshold"] <= 1:
                    raise ValueError("'rout_threshold' must be between 0 and 1")
            taken = {m["name"] for f in self.factions for m in f["members"]} - {data["name"]}
            if self.selected[0] == "member" and name in taken:
                raise ValueError(f"There is already a character named '{name}'")
        except ValueError as error:
            messagebox.showerror("Invalid value", str(error))
            return
        optional = ["targeting", "on_rout"] + (["behavior"] if self.selected[0] == "member" else [])
        for key in optional + ["rout_threshold"]:
            value = changes.get(key, self.vars[key].get().strip())
            if value in ("", None):
                data.pop(key, None)
            else:
                data[key] = value
        data.update({k: v for k, v in changes.items() if k != "rout_threshold"})
        self.refresh_tree(self.selected)
        self.app.results_panel.job_changed()

    def new_job(self):
        from src.jobs import new_job
        self.app.set_job(new_job(), None)

    def add_faction(self):
        name = unique_name(f"Faction {len(self.factions) + 1}", {f["name"] for f in self.factions})
        self.factions.append({"name": name, "members": []})
        self.refresh_tree(("faction", len(self.factions) - 1))

    def add_character(self):
        if not self.selected:
            messagebox.showinfo("Add a character", "Select a faction first")
            return
        fi = self.selected[1]
        taken = {m["name"] for f in self.factions for m in f["members"]}
        self.factions[fi]["members"].append(new_character(unique_name("New character", taken)))
        self.refresh_tree(("member", fi, len(self.factions[fi]["members"]) - 1))

    def duplicate(self):
        if not self.selected or self.selected[0] != "member":
            return
        fi, mi = self.selected[1:]
        clone = copy.deepcopy(self.factions[fi]["members"][mi])
        clone["name"] = unique_name(clone["name"], {m["name"] for f in self.factions for m in f["members"]})
        self.factions[fi]["members"].append(clone)
        self.refresh_tree(("member", fi, len(self.factions[fi]["members"]) - 1))

    def remove(self):
        if not self.selected:
            return
        if self.selected[0] == "faction":
            faction = self.factions[self.selected[1]]
            if faction["members"] and not messagebox.askyesno("Remove", f"Remove '{faction['name']}' and its {len(faction['members'])} characters?"):
                return
            del self.factions[self.selected[1]]
        else:
            del self.factions[self.selected[1]]["members"][self.selected[2]]
        self.selected = None
        self.refresh_tree()
        self.app.results_panel.job_changed()

    def add_item(self):
        data = self.current()
        if data is None or self.selected[0] != "member" or not self.item_name.get():
            return
        item_type = next(t for t, label in TYPE_LABELS.items() if label == self.item_type.get())
        data.setdefault("inventory", []).append({"type": item_type, "name": self.item_name.get()})
        self.load_form()

    def remove_item(self):
        data = self.current()
        selection = self.inventory_list.curselection()
        if data is None or not selection:
            return
        del data["inventory"][selection[0]]
        self.load_form()

    # --- import ------------------------------------------------------------------------

    def import_dialog(self):
        path = filedialog.askopenfilename(title="Import characters (character, list, or job file)",
                                          filetypes=[("JSON", "*.json")], initialdir=os.path.join(self.app_root(), "sim"))
        if not path:
            return
        try:
            characters = import_characters(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Import", f"Cannot import {path}: {error}")
            return
        self.choose_characters(characters)

    @staticmethod
    def app_root():
        from src.gui import ROOT
        return ROOT

    def choose_characters(self, characters):
        """Let the user pick which of the imported characters to add, and to which faction."""
        window = tk.Toplevel(self)
        window.title("Import characters")
        window.transient(self.winfo_toplevel())
        ttk.Label(window, text="Characters to import:").grid(row=0, column=0, sticky=tk.W, padx=8, pady=(8, 2))
        box = tk.Listbox(window, selectmode=tk.EXTENDED, height=min(12, len(characters)), exportselection=False)
        for character in characters:
            box.insert(tk.END, character["name"])
        box.select_set(0, tk.END)
        box.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=8)
        ttk.Label(window, text="Into faction:").grid(row=2, column=0, sticky=tk.W, padx=8, pady=6)
        names = [f["name"] for f in self.factions]
        target = tk.StringVar(value=names[self.selected[1]] if self.selected else names[0])
        ttk.Combobox(window, textvariable=target, values=names, state="readonly").grid(row=2, column=1, sticky=tk.W)

        def do_import():
            chosen = [characters[i] for i in box.curselection()]
            faction = self.factions[names.index(target.get())]
            taken = {m["name"] for f in self.factions for m in f["members"]}
            for character in chosen:
                character["name"] = unique_name(character["name"], taken)
                taken.add(character["name"])
                faction["members"].append(character)
            window.destroy()
            self.refresh_tree(("faction", names.index(target.get())))
            problems = [p for c in chosen for p in character_problems(c, c["name"], self.app.inventory)]
            if problems:
                messagebox.showwarning("Imported with problems", "\n".join(problems[:15]))

        ttk.Button(window, text="Import", command=do_import).grid(row=3, column=0, padx=8, pady=8, sticky=tk.W)
        ttk.Button(window, text="Cancel", command=window.destroy).grid(row=3, column=1, sticky=tk.W)
