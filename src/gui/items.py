"""Items panel: browse, search and edit the item database."""
import json
import os

from nicegui import ui

from src.database import DEFAULTS, FIELDS, TYPE_LABELS, display, form_values, item_from_values, items_using
from src.gui.common import confirm, notify_error
from src.gui.state import json_files, read_json, safe_json_name, write_json


class ItemsPanel:
    def __init__(self, state, on_db_changed=None):
        self.state = state
        self.on_db_changed = on_db_changed or (lambda: None)
        self.item_type = "melee_weapons"

    # --- layout ----------------------------------------------------------------------

    def build(self):
        with ui.row().classes("w-full items-center gap-1"):
            ui.button("Open", icon="folder_open", on_click=self.open_dialog).props("flat").mark("open-db")
            ui.button("Save", icon="save", on_click=self.save).props("flat").mark("save-db")
            ui.button("Download", icon="download", on_click=self.download).props("flat").mark("download-db")
            self.path_label = ui.label().classes("muted ml-4")
        with ui.row().classes("w-full items-center gap-4 mt-2"):
            ui.toggle(TYPE_LABELS, value=self.item_type, on_change=self.change_type).props("no-caps").mark("item-kind")
            self.search = ui.input(placeholder="Search").props("dense outlined clearable").classes("w-64").mark("search")
            ui.space()
            ui.button("Add", icon="add", on_click=lambda: self.edit_dialog(None)).props("outline").mark("items-add")
            ui.button("Edit", icon="edit", on_click=self.edit_selected).props("outline").mark("items-edit")
            ui.button("Delete", icon="delete", on_click=self.delete).props("outline color=negative").mark("items-delete")
        self.table_area = ui.column().classes("w-full")
        self.render_table()
        self.update_path()

    def update_path(self):
        self.path_label.set_text(os.path.relpath(self.state.db_path) if self.state.db_path else "(unsaved database)")

    def change_type(self, event):
        self.item_type = event.value
        self.render_table()

    @property
    def items(self):
        return self.state.inventory[self.item_type]

    def render_table(self):
        self.table_area.clear()
        fields = [key for key, _ in FIELDS[self.item_type]]
        columns = [{"name": key, "label": key, "field": key, "align": "left", "sortable": True} for key in fields]
        rows = [{"idx": i, **{key: display(item.get(key, "")) for key in fields}} for i, item in enumerate(self.items)]
        with self.table_area:
            self.table = ui.table(columns=columns, rows=rows, row_key="idx", selection="single",
                                  pagination={"rowsPerPage": 15}).classes("w-full").props("flat bordered dense")
            self.table.on("rowDblclick", lambda e: self.edit_dialog(int(e.args[1]["idx"])))
            self.search.bind_value_to(self.table, "filter")
            self.count = ui.label(f"{len(rows)} items").classes("muted").mark("item-count")

    def edit_selected(self):
        index = self.selected_index()
        if index is None:
            notify_error("Select an item first")
        else:
            self.edit_dialog(index)

    def selected_index(self):
        return self.table.selected[0]["idx"] if self.table.selected else None

    # --- editing ---------------------------------------------------------------------------

    def edit_dialog(self, index):
        item = dict(DEFAULTS[self.item_type]) if index is None else dict(self.items[index])
        values = form_values(self.item_type, item)
        widgets = {}
        with ui.dialog() as dialog, ui.card().classes("w-[30rem]"):
            ui.label("Add an item" if index is None else f"Edit {item['name']}").classes("text-lg font-medium")
            for key, kind in FIELDS[self.item_type]:
                if kind == "bool":
                    widgets[key] = ui.checkbox(key, value=values[key]).mark(f"dialog-{key}")
                else:
                    hint = " (comma separated)" if kind == "list" else " (whole number)" if kind == "int" else ""
                    widgets[key] = ui.input(key + hint, value=values[key]).classes("w-full").props("dense outlined").mark(f"dialog-{key}")

            def save():
                other = {o["name"] for i, o in enumerate(self.items) if i != index}
                try:
                    new = item_from_values(self.item_type, {k: w.value for k, w in widgets.items()}, other)
                except ValueError as error:
                    notify_error(str(error))
                    return
                if index is None:
                    self.items.append(new)
                else:
                    self.items[index] = new
                dialog.close()
                self.render_table()
                self.on_db_changed()

            with ui.row().classes("w-full justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", icon="check", on_click=save).props("outline").mark("dialog-save")
        dialog.open()

    async def delete(self):
        index = self.selected_index()
        if index is None:
            notify_error("Select an item first")
            return
        name = self.items[index]["name"]
        users = items_using(self.state.job, self.item_type, name)
        message = f"Delete '{name}'?" + (f"\nIt is used by: {', '.join(users)}." if users else "")
        if await confirm(message, "Delete"):
            del self.items[index]
            self.render_table()
            self.on_db_changed()

    # --- files -------------------------------------------------------------------------------------

    def save(self):
        path = self.state.db_path or os.path.join(self.state.db_dir, "db.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_json(path, self.state.db_data)
        self.state.db_path = path
        self.update_path()
        ui.notify(f"Saved to {os.path.relpath(path)}", type="positive")

    def download(self):
        ui.download(json.dumps(self.state.db_data, ensure_ascii=False, indent=4).encode("utf-8"),
                    safe_json_name(os.path.basename(self.state.db_path or ""), "db.json"))

    def load_db(self, data, path=None):
        self.state.set_db(data, path)
        self.render_table()
        self.update_path()
        self.on_db_changed()

    def open_dialog(self):
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Open an item database").classes("text-lg font-medium")
            files = json_files(self.state.db_dir)
            choice = ui.select(files, label=f"Databases in {os.path.basename(self.state.db_dir)}/",
                               value=files[0] if files else None).classes("w-full").mark("db-file")

            def open_selected():
                path = os.path.join(self.state.db_dir, choice.value)
                try:
                    data = read_json(path)
                    self.check_db(data)
                except (OSError, ValueError, TypeError) as error:
                    notify_error(f"Cannot open the database: {error}")
                    return
                dialog.close()
                self.load_db(data, path)

            opener = ui.button("Open", icon="folder_open", on_click=open_selected).props("outline").mark("open-selected-db")
            opener.set_enabled(bool(files))
            ui.separator()
            ui.label("or upload a database file").classes("muted")

            async def uploaded(event):
                try:
                    data = json.loads(await event.file.text())
                    self.check_db(data)
                except (ValueError, TypeError) as error:
                    notify_error(f"Cannot open {event.file.name}: {error}")
                    return
                dialog.close()
                self.load_db(data, None)

            ui.upload(on_upload=uploaded, auto_upload=True, label="Choose a .json file").props("accept=.json flat").classes("w-full")
            ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    @staticmethod
    def check_db(data):
        if not isinstance(data, dict) or not isinstance(data.get("inventory"), dict):
            raise ValueError("this file has no 'inventory'")
