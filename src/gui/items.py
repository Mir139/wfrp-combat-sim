"""Items panel: browse and edit the item database."""
import tkinter as tk
from tkinter import messagebox, ttk

TYPE_LABELS = {"melee_weapons": "Melee weapons", "ranged_weapons": "Ranged weapons", "armors": "Armors"}
# (key, kind): kinds are text, int (stored as a string, like the database does), list (comma separated) and bool
FIELDS = {
    "melee_weapons": [("name", "text"), ("reach", "text"), ("damage", "int"), ("attributes", "list"),
                      ("encumbrance", "text"), ("2M", "bool")],
    "ranged_weapons": [("name", "text"), ("range", "int"), ("damage", "int"), ("attributes", "list"),
                       ("encumbrance", "text"), ("2M", "bool"), ("range_BF", "bool"), ("damage_BF", "bool")],
    "armors": [("name", "text"), ("penalty", "list"), ("location", "text"), ("armor_points", "int"), ("attributes", "list")],
}
DEFAULTS = {"melee_weapons": {"reach": "Moyenne", "damage": "4", "attributes": [], "encumbrance": "1", "2M": False},
            "ranged_weapons": {"range": "20", "damage": "4", "attributes": [], "encumbrance": "1", "2M": False,
                               "range_BF": False, "damage_BF": False},
            "armors": {"penalty": [], "location": "Tous", "armor_points": "1", "attributes": []}}


def display(value):
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, bool):
        return "yes" if value else ""
    return str(value)


class ItemsPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.item_type = tk.StringVar(value=TYPE_LABELS["melee_weapons"])
        self.search = tk.StringVar()
        self._build()

    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="Open database...", command=self.app.open_db).pack(side=tk.LEFT)
        ttk.Button(bar, text="Save database", command=self.app.save_db).pack(side=tk.LEFT, padx=4)
        self.path_label = ttk.Label(bar, foreground="#52514e")
        self.path_label.pack(side=tk.LEFT, padx=12)

        filters = ttk.Frame(self)
        filters.pack(fill=tk.X, pady=8)
        type_box = ttk.Combobox(filters, textvariable=self.item_type, values=list(TYPE_LABELS.values()), state="readonly", width=16)
        type_box.pack(side=tk.LEFT)
        type_box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(filters, text="Search").pack(side=tk.LEFT, padx=(16, 4))
        entry = ttk.Entry(filters, textvariable=self.search, width=26)
        entry.pack(side=tk.LEFT)
        self.search.trace_add("write", lambda *a: self.refresh())

        holder = ttk.Frame(self)
        holder.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(holder, show="headings", selectmode="browse")
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.bind("<Double-1>", lambda e: self.edit())

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(buttons, text="Add", command=self.add).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Edit", command=self.edit).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Delete", command=self.delete).pack(side=tk.LEFT)
        self.count = ttk.Label(buttons, foreground="#52514e")
        self.count.pack(side=tk.RIGHT)

    @property
    def type_key(self):
        return next(k for k, label in TYPE_LABELS.items() if label == self.item_type.get())

    @property
    def items(self):
        return self.app.inventory[self.type_key]

    def db_changed(self):
        self.path_label.config(text=self.app.db_path or "(unsaved database)")
        self.refresh()

    def refresh(self):
        fields = [key for key, _ in FIELDS[self.type_key]]
        self.tree.config(columns=fields)
        for key in fields:
            self.tree.heading(key, text=key)
            self.tree.column(key, width=170 if key in ("name", "attributes", "penalty") else 80, anchor=tk.W)
        self.tree.delete(*self.tree.get_children())
        needle = self.search.get().strip().lower()
        shown = 0
        for index, item in enumerate(self.items):
            if needle and needle not in " ".join(display(item.get(k, "")) for k in fields).lower():
                continue
            self.tree.insert("", tk.END, iid=str(index), values=[display(item.get(k, "")) for k in fields])
            shown += 1
        self.count.config(text=f"{shown} of {len(self.items)} items")

    def selected_index(self):
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def add(self):
        self.open_editor(None)

    def edit(self):
        index = self.selected_index()
        if index is not None:
            self.open_editor(index)

    def delete(self):
        index = self.selected_index()
        if index is None:
            return
        name = self.items[index]["name"]
        users = [m["name"] for f in self.app.job["factions"] for m in f["members"]
                 if any(i["type"] == self.type_key and i["name"] == name for i in m.get("inventory", []))]
        message = f"Delete '{name}'?"
        if users:
            message += f"\nIt is used by: {', '.join(users)}."
        if messagebox.askyesno("Delete", message):
            del self.items[index]
            self.refresh()
            self.app.factions_panel.db_changed()

    def open_editor(self, index):
        item_type = self.type_key
        item = dict(DEFAULTS[item_type], name="") if index is None else dict(self.items[index])
        window = tk.Toplevel(self)
        window.title("Add an item" if index is None else f"Edit {item['name']}")
        window.transient(self.winfo_toplevel())
        window.grab_set()
        variables = {}
        for row, (key, kind) in enumerate(FIELDS[item_type]):
            label = key + (" (comma separated)" if kind == "list" else "")
            ttk.Label(window, text=label).grid(row=row, column=0, sticky=tk.W, padx=8, pady=3)
            if kind == "bool":
                variables[key] = tk.BooleanVar(value=bool(item.get(key)))
                ttk.Checkbutton(window, variable=variables[key]).grid(row=row, column=1, sticky=tk.W)
            else:
                variables[key] = tk.StringVar(value=display(item.get(key, "")))
                ttk.Entry(window, textvariable=variables[key], width=34).grid(row=row, column=1, padx=8, pady=3)

        def save():
            try:
                new = self.read_item(item_type, variables, index)
            except ValueError as error:
                messagebox.showerror("Invalid value", str(error), parent=window)
                return
            if index is None:
                self.items.append(new)
            else:
                self.items[index] = new
            window.destroy()
            self.refresh()
            self.app.factions_panel.db_changed()

        buttons = ttk.Frame(window)
        buttons.grid(row=len(FIELDS[item_type]), column=0, columnspan=2, pady=8)
        ttk.Button(buttons, text="Save", command=save).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side=tk.LEFT)

    def read_item(self, item_type, variables, index):
        item = {}
        for key, kind in FIELDS[item_type]:
            value = variables[key].get()
            if kind == "bool":
                item[key] = bool(value)
            elif kind == "list":
                item[key] = [part.strip() for part in value.split(",") if part.strip()]
            elif kind == "int":
                try:
                    item[key] = str(int(value.strip()))
                except ValueError:
                    raise ValueError(f"'{key}' must be a whole number, not '{value}'") from None
            else:
                item[key] = value.strip()
        if not item["name"]:
            raise ValueError("The name cannot be empty")
        if any(other["name"] == item["name"] for i, other in enumerate(self.items) if i != index):
            raise ValueError(f"There is already an item named '{item['name']}'")
        if item_type == "armors" and "," in item["location"]:
            item["location"] = [part.strip() for part in item["location"].split(",")]
        return item
