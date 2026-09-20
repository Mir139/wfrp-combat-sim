"""Factions panel: edit the job (factions, characters, tactics, inventory), open, save and import."""
import json
import os

from nicegui import ui

from src.character import ROUT_BEHAVIORS, TARGETING_STRATEGIES
from src.gui.common import confirm, notify_error, notify_problems
from src.gui.state import json_files, read_json, safe_json_name, write_json
from src.jobs import (BEHAVIORS, CHARACTERISTICS, ITEM_TYPES, add_characters, add_faction, add_member, character_problems,
                      characters_from_data, duplicate_member, new_job, set_field, validate_job)

TYPE_LABELS = {"melee_weapons": "Melee weapon", "ranged_weapons": "Ranged weapon", "armors": "Armor"}
CHOICES = {"behavior": BEHAVIORS, "targeting": list(TARGETING_STRATEGIES), "on_rout": list(ROUT_BEHAVIORS)}
CHOICE_LABELS = {"behavior": "Fighting style", "targeting": "Targeting", "on_rout": "On rout"}


class FactionsPanel:
    def __init__(self, state, on_job_changed=None):
        self.state = state
        self.on_job_changed = on_job_changed or (lambda: None)
        self.tree = None

    # --- layout --------------------------------------------------------------------

    def build(self):
        with ui.row().classes("w-full items-center gap-1"):
            ui.button("New", icon="note_add", on_click=self.new_job).props("flat").mark("new-job")
            ui.button("Open", icon="folder_open", on_click=self.open_dialog).props("flat").mark("open-job")
            ui.button("Save", icon="save", on_click=self.save_dialog).props("flat").mark("save-job")
            ui.button("Import characters", icon="person_add", on_click=self.import_dialog).props("flat").mark("import-characters")
            self.path_label = ui.label().classes("muted ml-4")
        with ui.splitter(value=28).classes("w-full").style("min-height: 560px") as splitter:
            with splitter.before:
                with ui.column().classes("w-full gap-2 pr-3"):
                    self.tree = ui.tree(self.tree_nodes(), node_key="id", label_key="label",
                                        on_select=self.on_tree_select).classes("w-full").props("selected-color=primary")
                    self.tree.expand()
                    with ui.row().classes("gap-1"):
                        ui.button("Faction", icon="add", on_click=self.add_faction).props("dense outline").mark("add-faction")
                        ui.button("Character", icon="add", on_click=self.add_character).props("dense outline").mark("add-character")
                        ui.button(icon="content_copy", on_click=self.duplicate).props("dense outline").tooltip("Duplicate").mark("duplicate")
                        ui.button(icon="delete", on_click=self.remove).props("dense outline color=negative").tooltip("Remove").mark("remove")
            with splitter.after:
                with ui.column().classes("w-full pl-3"):
                    self.editor()
        self.update_path()

    def update_path(self):
        self.path_label.set_text(os.path.relpath(self.state.job_path) if self.state.job_path else "(unsaved job)")

    # --- tree ------------------------------------------------------------------------------

    def tree_nodes(self):
        return [{"id": f"f{fi}", "label": f"{f['name']} ({len(f['members'])})",
                 "children": [{"id": f"f{fi}m{mi}", "label": m["name"]} for mi, m in enumerate(f["members"])]}
                for fi, f in enumerate(self.state.job["factions"])]

    def refresh_tree(self, select=None):
        self.tree._props["nodes"] = self.tree_nodes()
        self.tree.update()
        self.tree.expand()
        if select is not None:
            self.select(select)

    def select(self, selection):
        self.state.selection = selection
        if selection is None:
            self.tree.deselect()
        else:
            self.tree.select(f"f{selection[1]}" if selection[0] == "faction" else f"f{selection[1]}m{selection[2]}")
        self.editor.refresh()

    def on_tree_select(self, event):
        node = event.value
        if node is None:
            return
        if "m" in node:
            faction, member = node[1:].split("m")
            selection = ("member", int(faction), int(member))
        else:
            selection = ("faction", int(node[1:]))
        if selection != self.state.selection:
            self.state.selection = selection
            self.editor.refresh()

    def current(self):
        selection = self.state.selection
        if not selection:
            return None
        faction = self.state.job["factions"][selection[1]]
        return faction if selection[0] == "faction" else faction["members"][selection[2]]

    # --- editor ------------------------------------------------------------------------------

    @ui.refreshable_method
    def editor(self):
        data = self.current()
        if data is None:
            ui.label("Select a faction or a character to edit it.").classes("muted")
            return
        is_member = self.state.selection[0] == "member"
        ui.label(("Character" if is_member else "Faction") + f": {data['name']}").classes("text-lg font-medium")
        name = ui.input("Name", value=data["name"]).classes("w-72").mark("name")
        name.on("blur", lambda: self.commit(data, "name", name.value, lambda: name.set_value(data["name"])))
        name.on("keydown.enter", lambda: self.commit(data, "name", name.value, lambda: name.set_value(data["name"])))
        if is_member:
            self.characteristics(data)
        self.tactics(data, is_member)
        if is_member:
            self.inventory(data)

    def characteristics(self, data):
        with ui.row().classes("gap-3 items-end flex-wrap"):
            for key, label in [("health", "Wounds")] + [(c, c) for c in CHARACTERISTICS]:
                box = ui.number(label, value=data[key], format="%.0f", min=0 if key != "health" else 1).classes("w-24").mark(f"field-{key}")
                box.on_value_change(lambda e, key=key, box=box: self.commit_number(data, key, e.value, box))

    def tactics(self, data, is_member):
        with ui.card().props("flat bordered").classes("w-full"):
            ui.label("Tactics (blank: default)").classes("text-subtitle2")
            with ui.row().classes("gap-3 items-end"):
                for key in (["behavior"] if is_member else []) + ["targeting", "on_rout"]:
                    options = {"": "(default)", **{c: c for c in CHOICES[key]}}
                    choice = ui.select(options, label=CHOICE_LABELS[key], value=data.get(key) or "").classes("w-40").mark(f"choice-{key}")
                    choice.on_value_change(lambda e, key=key: self.commit(data, key, e.value))
                threshold = ui.number("Rout threshold", value=data.get("rout_threshold"), min=0, max=1, step=0.05,
                                      format="%.2f").classes("w-36").props("clearable").mark("field-rout_threshold")
                threshold.on_value_change(lambda e: self.commit(data, "rout_threshold", e.value))

    def inventory(self, data):
        with ui.card().props("flat bordered").classes("w-full"):
            ui.label("Inventory").classes("text-subtitle2")
            for index, item in enumerate(data.get("inventory", [])):
                with ui.row().classes("w-full items-center"):
                    ui.badge(TYPE_LABELS.get(item["type"], item["type"])).props("outline")
                    ui.label(item["name"]).classes("grow")
                    ui.button(icon="close", on_click=lambda i=index: self.remove_item(data, i)).props("flat dense round size=sm").mark(f"remove-item-{index}")
            if not data.get("inventory"):
                ui.label("Nothing carried.").classes("muted")
            with ui.row().classes("items-end gap-2 mt-2"):
                kind = ui.select({k: v for k, v in TYPE_LABELS.items()}, value=ITEM_TYPES[0], label="Type").classes("w-44").mark("inventory-type")
                names = [i["name"] for i in self.state.inventory.get(kind.value, [])]
                item = ui.select(names, value=names[0] if names else None, label="Item", with_input=True).classes("w-72").mark("inventory-item")

                def change_type(event):
                    options = [i["name"] for i in self.state.inventory.get(event.value, [])]
                    item.set_options(options, value=options[0] if options else None)

                kind.on_value_change(change_type)
                ui.button("Add", icon="add", on_click=lambda: self.add_item(data, kind.value, item.value)).props("outline").mark("add-item")

    # --- editing ---------------------------------------------------------------------------------

    def commit(self, target, key, value, revert=None):
        try:
            set_field(self.state.job, target, key, value)
        except (ValueError, TypeError) as error:
            notify_error(str(error))
            if revert:
                revert()
            return
        if key == "name":
            self.refresh_tree()
            self.editor.refresh()
        self.on_job_changed()

    def commit_number(self, target, key, value, box):
        if value is None:  # the box is being typed into
            return
        self.commit(target, key, value, lambda: box.set_value(target[key]))

    def add_item(self, data, item_type, name):
        if not name:
            notify_error("Choose an item first")
            return
        data.setdefault("inventory", []).append({"type": item_type, "name": name})
        self.editor.refresh()

    def remove_item(self, data, index):
        del data["inventory"][index]
        self.editor.refresh()

    def add_faction(self):
        self.refresh_tree(("faction", add_faction(self.state.job)))
        self.on_job_changed()

    def add_character(self):
        if not self.state.selection:
            notify_error("Select a faction first")
            return
        faction = self.state.selection[1]
        self.refresh_tree(("member", faction, add_member(self.state.job, faction)))
        self.on_job_changed()

    def duplicate(self):
        if not self.state.selection or self.state.selection[0] != "member":
            notify_error("Select a character to duplicate")
            return
        faction, member = self.state.selection[1:]
        self.refresh_tree(("member", faction, duplicate_member(self.state.job, faction, member)))
        self.on_job_changed()

    async def remove(self):
        selection = self.state.selection
        if not selection:
            return
        factions = self.state.job["factions"]
        if selection[0] == "faction":
            faction = factions[selection[1]]
            if faction["members"] and not await confirm(f"Remove '{faction['name']}' and its {len(faction['members'])} characters?", "Remove"):
                return
            del factions[selection[1]]
        else:
            del factions[selection[1]]["members"][selection[2]]
        self.state.selection = None
        self.refresh_tree()
        self.editor.refresh()
        self.on_job_changed()

    # --- files -------------------------------------------------------------------------------------

    def load_job(self, job, path=None):
        self.state.set_job(job, path)
        self.refresh_tree()
        self.editor.refresh()
        self.update_path()
        self.on_job_changed()
        problems = validate_job(job, self.state.inventory)
        if problems:
            notify_problems("The job has problems", problems)

    def new_job(self):
        self.load_job(new_job())

    def open_dialog(self):
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Open a job").classes("text-lg font-medium")
            files = json_files(self.state.job_dir)
            choice = ui.select(files, label=f"Jobs in {os.path.basename(self.state.job_dir)}/",
                               value=files[0] if files else None).classes("w-full").mark("job-file")

            def open_selected():
                try:
                    path = os.path.join(self.state.job_dir, choice.value)
                    job = read_json(path)
                    self.check_job(job)
                except (OSError, ValueError, TypeError) as error:
                    notify_error(f"Cannot open the job: {error}")
                    return
                dialog.close()
                self.load_job(job, path)

            opener = ui.button("Open", icon="folder_open", on_click=open_selected).props("outline").mark("open-selected")
            opener.set_enabled(bool(files))
            ui.separator()
            ui.label("or upload a job file").classes("muted")

            async def uploaded(event):
                try:
                    job = json.loads(await event.file.text())
                    self.check_job(job)
                except (ValueError, TypeError) as error:
                    notify_error(f"Cannot open {event.file.name}: {error}")
                    return
                dialog.close()
                self.load_job(job, None)

            ui.upload(on_upload=uploaded, auto_upload=True, label="Choose a .json file").props("accept=.json flat").classes("w-full")
            ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    @staticmethod
    def check_job(job):
        if not isinstance(job, dict) or not isinstance(job.get("factions"), list):
            raise ValueError("this file has no 'factions'")

    def save_dialog(self):
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Save the job").classes("text-lg font-medium")
            default = os.path.basename(self.state.job_path) if self.state.job_path else "my_job.json"
            name = ui.input("File name", value=default).classes("w-full").mark("file-name")

            def save():
                filename = safe_json_name(name.value, "my_job.json")
                path = os.path.join(self.state.job_dir, filename)
                if os.path.exists(path) and path != self.state.job_path:
                    notify_error(f"{filename} already exists: choose another name or download the job")
                    return
                os.makedirs(self.state.job_dir, exist_ok=True)
                write_json(path, self.state.job)
                self.state.job_path = path
                self.update_path()
                ui.notify(f"Saved to {os.path.relpath(path)}", type="positive")
                dialog.close()

            def download():
                ui.download(json.dumps(self.state.job, ensure_ascii=False, indent=4).encode("utf-8"),
                            safe_json_name(name.value, "my_job.json"))

            with ui.row().classes("w-full justify-end"):
                ui.button("Download", icon="download", on_click=download).props("flat").mark("download-job")
                ui.button("Save in sim/", icon="save", on_click=save).props("outline").mark("save-in-folder")
        dialog.open()

    def import_dialog(self):
        with ui.dialog() as dialog, ui.card().classes("w-[28rem]"):
            ui.label("Import characters").classes("text-lg font-medium")
            ui.label("A character, a list, a faction or a whole job file (JSON).").classes("muted")
            body = ui.column().classes("w-full")

            async def uploaded(event):
                try:
                    characters = characters_from_data(json.loads(await event.file.text()))
                except (ValueError, TypeError) as error:
                    notify_error(f"Cannot import {event.file.name}: {error}")
                    return
                self.choose_characters(dialog, body, characters)

            with body:
                ui.upload(on_upload=uploaded, auto_upload=True, label="Choose a .json file").props("accept=.json flat").classes("w-full")
            ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    def choose_characters(self, dialog, body, characters):
        """Let the user pick which of the imported characters to add, and to which faction."""
        factions = {i: f["name"] for i, f in enumerate(self.state.job["factions"])}
        if not factions:
            notify_error("The job has no faction to import into")
            return
        body.clear()
        with body:
            ui.label(f"{len(characters)} character(s) found").classes("font-medium")
            checks = [ui.checkbox(c["name"], value=True).mark(f"import-{i}") for i, c in enumerate(characters)]
            selection = self.state.selection
            target = ui.select(factions, label="Into faction", value=selection[1] if selection else 0).classes("w-full").mark("import-faction")

            def do_import():
                chosen = [c for c, check in zip(characters, checks) if check.value]
                if not chosen:
                    notify_error("No character selected")
                    return
                add_characters(self.state.job, target.value, chosen)
                dialog.close()
                self.refresh_tree(("faction", target.value))
                self.on_job_changed()
                ui.notify(f"{len(chosen)} character(s) imported", type="positive")
                problems = [p for c in chosen for p in character_problems(c, c["name"], self.state.inventory)]
                if problems:
                    notify_problems("Imported with problems", problems)

            ui.button("Import", icon="person_add", on_click=do_import).props("outline").mark("do-import")
