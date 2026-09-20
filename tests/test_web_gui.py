"""Drives the web interface with NiceGUI's simulated user (no browser needed)."""
import asyncio
import json

import pytest
from nicegui import ui
from nicegui.elements.upload_files import SmallFileUpload
from nicegui.testing import User

from src.gui import register
from src.gui.state import AppState
from src.jobs import new_character, new_job


@pytest.fixture
def state(tmp_path):
    """The example job and database, but files are written to a temporary folder."""
    state = AppState(job_dir=str(tmp_path / "sim"), db_dir=str(tmp_path / "db"))
    state.load_defaults()
    state.db_path = None
    state.workers = 1
    return state


async def open_app(user, state):
    register(state)
    await user.open("/")
    await user.should_see("WFRP Combat Simulator")


def element(user, marker):
    return user.find(marker=marker).elements.pop()


def click(user, marker):
    user.find(marker=marker).click()


async def settle(seconds=0.2):
    await asyncio.sleep(seconds)


def select_node(user, node):
    user.find(ui.tree).trigger("update:selected", args=node)


async def open_tab(user, name):
    user.find(kind=ui.tab, content=name).click()
    await settle(0.1)


async def upload(user, content, name="file.json"):
    data = content if isinstance(content, bytes) else json.dumps(content).encode("utf-8")
    await user.find(kind=ui.upload).elements.pop().handle_uploads([SmallFileUpload(name=name, content_type="application/json", _data=data)])
    await settle()


def titles(user):
    """Titles of the interactive charts of the page, in order."""
    return [c.options["title"]["text"] for c in sorted(user.find(kind=ui.echart).elements, key=lambda c: c.id)]


def table_with(user, column):
    """The table of the page that has a column of that name."""
    return next(t for t in user.find(ui.table).elements if any(c["name"] == column for c in t.columns))


async def run_simulation(user, state, count=200):
    await open_tab(user, "Results")
    element(user, "combats").set_value(count)
    element(user, "seed").set_value(1)
    click(user, "run")
    for _ in range(200):
        if state.runs:
            break
        await asyncio.sleep(0.05)
    await user.should_see("Combat length")


# --- factions -------------------------------------------------------------------------------------------

async def test_the_page_lists_the_factions_and_their_characters(user: User, state):
    await open_app(user, state)
    for text in ("Factions", "Items", "Results", "Joueurs (5)", "Gunnar Hrolfsson", "Terreur de la Teufel", "sim/job1.json"):
        await user.should_see(text)


async def test_selecting_a_character_shows_its_editor(user: User, state):
    await open_app(user, state)
    select_node(user, "f0m0")
    await user.should_see("Character: Gunnar Hrolfsson")
    await user.should_see("(2M) Hache")
    assert element(user, "field-CC").value == 45


async def test_a_faction_editor_has_no_character_fields(user: User, state):
    await open_app(user, state)
    select_node(user, "f1")
    await user.should_see("Faction: Faction2")
    await user.should_not_see(marker="field-CC")
    await user.should_not_see(marker="choice-behavior")
    await user.should_see(marker="choice-targeting")


async def test_editing_a_characteristic_updates_the_job(user: User, state):
    await open_app(user, state)
    select_node(user, "f0m0")
    await user.should_see("Character: Gunnar Hrolfsson")
    element(user, "field-CC").set_value(77)
    assert state.job["factions"][0]["members"][0]["CC"] == 77


async def test_an_invalid_edit_is_refused_reported_and_reverted(user: User, state):
    await open_app(user, state)
    select_node(user, "f0m0")
    await user.should_see("Character: Gunnar Hrolfsson")
    box = element(user, "field-health")
    box.set_value(0)
    assert state.job["factions"][0]["members"][0]["health"] == 18
    assert user.notify.contains("positive")
    assert box.value == 18


async def test_clearing_a_number_while_typing_does_not_change_the_job(user: User, state):
    await open_app(user, state)
    select_node(user, "f0m0")
    await user.should_see("Character: Gunnar Hrolfsson")
    element(user, "field-CC").set_value(None)
    assert state.job["factions"][0]["members"][0]["CC"] == 45
    assert not user.notify.messages


async def test_tactics_can_be_set_and_cleared(user: User, state):
    await open_app(user, state)
    select_node(user, "f0m0")
    await user.should_see("Character: Gunnar Hrolfsson")
    member = state.job["factions"][0]["members"][0]
    element(user, "choice-targeting").set_value("weakest")
    element(user, "choice-behavior").set_value("melee")
    element(user, "field-rout_threshold").set_value(0.4)
    assert (member["targeting"], member["behavior"], member["rout_threshold"]) == ("weakest", "melee", 0.4)
    element(user, "choice-targeting").set_value("")
    element(user, "field-rout_threshold").set_value(None)
    assert "targeting" not in member and "rout_threshold" not in member


async def test_renaming_commits_on_blur_and_updates_the_tree(user: User, state):
    await open_app(user, state)
    select_node(user, "f0m0")
    await user.should_see("Character: Gunnar Hrolfsson")
    element(user, "name").set_value("Gunnar the Bold")
    assert state.job["factions"][0]["members"][0]["name"] == "Gunnar Hrolfsson"  # not committed yet
    user.find(marker="name").trigger("blur")
    assert state.job["factions"][0]["members"][0]["name"] == "Gunnar the Bold"
    await user.should_see("Character: Gunnar the Bold")


async def test_a_name_already_taken_is_refused(user: User, state):
    await open_app(user, state)
    select_node(user, "f0m0")
    await user.should_see("Character: Gunnar Hrolfsson")
    box = element(user, "name")
    box.set_value("Else Sigloben")
    user.find(marker="name").trigger("blur")
    assert state.job["factions"][0]["members"][0]["name"] == "Gunnar Hrolfsson"
    assert user.notify.contains("already a character named")
    assert box.value == "Gunnar Hrolfsson"


async def test_add_duplicate_and_remove_a_character(user: User, state):
    await open_app(user, state)
    select_node(user, "f1")
    await user.should_see("Faction: Faction2")
    click(user, "add-character")
    await user.should_see("Character: New character")
    click(user, "duplicate")
    await user.should_see("Character: New character 2")
    assert [m["name"] for m in state.job["factions"][1]["members"]] == ["Terreur de la Teufel", "New character", "New character 2"]
    click(user, "remove")
    await settle()
    assert len(state.job["factions"][1]["members"]) == 2
    assert state.selection is None
    await user.should_see("Select a faction or a character")


async def test_add_character_without_a_selection_is_refused(user: User, state):
    await open_app(user, state)
    click(user, "add-character")
    assert user.notify.contains("Select a faction first")


async def test_add_and_remove_a_faction(user: User, state):
    await open_app(user, state)
    click(user, "add-faction")
    await user.should_see("Faction: Faction 3")
    assert len(state.job["factions"]) == 3
    click(user, "remove")
    await settle()
    assert len(state.job["factions"]) == 2  # an empty faction is removed without asking


async def test_removing_a_faction_with_characters_asks_first(user: User, state):
    await open_app(user, state)
    select_node(user, "f0")
    await user.should_see("Faction: Joueurs")
    click(user, "remove")
    await user.should_see("Remove 'Joueurs' and its 5 characters?")
    assert len(state.job["factions"]) == 2
    click(user, "confirm")
    await settle()
    assert [f["name"] for f in state.job["factions"]] == ["Faction2"]


async def test_the_inventory_can_be_extended_and_trimmed(user: User, state):
    await open_app(user, state)
    select_node(user, "f0m0")
    await user.should_see("Character: Gunnar Hrolfsson")
    inventory = state.job["factions"][0]["members"][0]["inventory"]
    before = len(inventory)
    element(user, "inventory-item").set_value("(2M) Bâton de combat")
    click(user, "add-item")
    assert inventory[-1] == {"type": "melee_weapons", "name": "(2M) Bâton de combat"}
    await settle()
    click(user, f"remove-item-{before}")
    assert len(inventory) == before


async def test_changing_the_item_type_offers_the_items_of_that_type(user: User, state):
    await open_app(user, state)
    select_node(user, "f0m0")
    await user.should_see("Character: Gunnar Hrolfsson")
    element(user, "inventory-type").set_value("armors")
    assert "Armure lourde" in element(user, "inventory-item").options
    element(user, "inventory-item").set_value("Armure lourde")
    click(user, "add-item")
    assert state.job["factions"][0]["members"][0]["inventory"][-1] == {"type": "armors", "name": "Armure lourde"}


async def test_a_new_job_replaces_the_current_one(user: User, state):
    await open_app(user, state)
    click(user, "new-job")
    await user.should_see("(unsaved job)")
    assert [f["name"] for f in state.job["factions"]] == ["Faction 1", "Faction 2"] and state.job_path is None


async def test_saving_writes_a_file_in_the_job_folder(user: User, state, tmp_path):
    await open_app(user, state)
    click(user, "save-job")
    await user.should_see("Save the job")
    element(user, "file-name").set_value("my fight.json")
    click(user, "save-in-folder")
    path = tmp_path / "sim" / "my fight.json"
    assert json.loads(path.read_text(encoding="utf-8")) == state.job and state.job_path == str(path)
    assert user.notify.contains("Saved to")


async def test_saving_never_escapes_the_job_folder(user: User, state, tmp_path):
    await open_app(user, state)
    click(user, "save-job")
    await user.should_see("Save the job")
    element(user, "file-name").set_value("../../evil")
    click(user, "save-in-folder")
    assert (tmp_path / "sim" / "evil.json").exists() and not (tmp_path / "evil.json").exists()


async def test_saving_does_not_overwrite_another_job(user: User, state, tmp_path):
    (tmp_path / "sim").mkdir()
    (tmp_path / "sim" / "taken.json").write_text("{}")
    await open_app(user, state)
    click(user, "save-job")
    await user.should_see("Save the job")
    element(user, "file-name").set_value("taken")
    click(user, "save-in-folder")
    assert (tmp_path / "sim" / "taken.json").read_text() == "{}" and user.notify.contains("already exists")


async def test_downloading_the_job(user: User, state):
    await open_app(user, state)
    click(user, "save-job")
    await user.should_see("Save the job")
    click(user, "download-job")
    response = await user.download.next()
    assert json.loads(response.content) == state.job


async def test_opening_a_job_from_the_folder(user: User, state, tmp_path):
    (tmp_path / "sim").mkdir()
    other = {"factions": [{"name": "A", "members": [new_character("Solo A")]}, {"name": "B", "members": [new_character("Solo B")]}]}
    (tmp_path / "sim" / "other.json").write_text(json.dumps(other), encoding="utf-8")
    await open_app(user, state)
    click(user, "open-job")
    await user.should_see("Open a job")
    element(user, "job-file").set_value("other.json")
    click(user, "open-selected")
    await settle()
    assert [f["name"] for f in state.job["factions"]] == ["A", "B"] and state.job_path == str(tmp_path / "sim" / "other.json")
    await user.should_see("Solo A")


async def test_opening_a_file_that_is_not_a_job_is_refused(user: User, state, tmp_path):
    (tmp_path / "sim").mkdir()
    (tmp_path / "sim" / "bad.json").write_text(json.dumps({"nothing": 1}), encoding="utf-8")
    await open_app(user, state)
    click(user, "open-job")
    await user.should_see("Open a job")
    element(user, "job-file").set_value("bad.json")
    click(user, "open-selected")
    assert user.notify.contains("no 'factions'") and state.job_path.endswith("job1.json")


async def test_uploading_a_job(user: User, state):
    await open_app(user, state)
    click(user, "open-job")
    await user.should_see("Open a job")
    job = new_job()
    job["factions"][0]["members"].append(new_character("Uploaded"))
    await upload(user, job)
    assert state.job["factions"][0]["members"][0]["name"] == "Uploaded" and state.job_path is None


async def test_uploading_garbage_instead_of_a_job_is_refused(user: User, state):
    await open_app(user, state)
    click(user, "open-job")
    await user.should_see("Open a job")
    await upload(user, b"this is not json")
    assert user.notify.contains("Cannot open") and state.job_path.endswith("job1.json")


async def test_importing_characters_from_a_file(user: User, state):
    await open_app(user, state)
    select_node(user, "f1")
    await user.should_see("Faction: Faction2")
    click(user, "import-characters")
    await user.should_see("Import characters")
    await upload(user, [new_character("Terreur de la Teufel"), new_character("Newcomer")])
    await user.should_see("2 character(s) found")
    assert element(user, "import-faction").value == 1  # the selected faction
    click(user, "do-import")
    await settle()
    assert [m["name"] for m in state.job["factions"][1]["members"]] == ["Terreur de la Teufel", "Terreur de la Teufel 2", "Newcomer"]
    assert user.notify.contains("2 character(s) imported")


async def test_importing_only_the_chosen_characters(user: User, state):
    await open_app(user, state)
    click(user, "import-characters")
    await user.should_see("Import characters")
    await upload(user, [new_character("Keep"), new_character("Skip")])
    element(user, "import-1").set_value(False)
    click(user, "do-import")
    await settle()
    names = [m["name"] for m in state.job["factions"][0]["members"]]
    assert "Keep" in names and "Skip" not in names


async def test_importing_characters_warns_about_unknown_items(user: User, state):
    await open_app(user, state)
    click(user, "import-characters")
    await user.should_see("Import characters")
    stranger = new_character("Stranger")
    stranger["inventory"] = [{"type": "armors", "name": "Mithril"}]
    await upload(user, stranger)
    click(user, "do-import")
    await settle()
    assert user.notify.contains("Mithril")


async def test_importing_a_file_without_characters_is_refused(user: User, state):
    await open_app(user, state)
    click(user, "import-characters")
    await user.should_see("Import characters")
    await upload(user, {"nothing": 1})
    assert user.notify.contains("Cannot import") and len(state.job["factions"][0]["members"]) == 5


# --- items ------------------------------------------------------------------------------------------------------

async def test_the_items_tab_lists_the_database_by_type(user: User, state):
    await open_app(user, state)
    await open_tab(user, "Items")
    await user.should_see("29 items")
    element(user, "item-kind").set_value("armors")
    await user.should_see("5 items")
    element(user, "item-kind").set_value("ranged_weapons")
    await user.should_see("25 items")


async def test_the_search_box_filters_the_table(user: User, state):
    await open_app(user, state)
    await open_tab(user, "Items")
    user.find(marker="search").type("Hache")
    assert user.find(ui.table).elements.pop().filter == "Hache"


async def test_adding_an_item(user: User, state):
    await open_app(user, state)
    await open_tab(user, "Items")
    element(user, "item-kind").set_value("armors")
    click(user, "items-add")
    await user.should_see("Add an item")
    element(user, "dialog-name").set_value("Cotte de test")
    element(user, "dialog-armor_points").set_value("2")
    element(user, "dialog-location").set_value("Tête, Corps")
    click(user, "dialog-save")
    await settle()
    assert state.inventory["armors"][-1] == {"name": "Cotte de test", "penalty": [], "location": ["Tête", "Corps"],
                                             "armor_points": "2", "attributes": []}
    await user.should_see("6 items")


async def test_an_invalid_item_is_refused_and_the_database_is_unchanged(user: User, state):
    await open_app(user, state)
    await open_tab(user, "Items")
    element(user, "item-kind").set_value("armors")
    click(user, "items-add")
    await user.should_see("Add an item")
    element(user, "dialog-name").set_value("Armure lourde")  # already exists
    click(user, "dialog-save")
    assert user.notify.contains("already an item named")
    element(user, "dialog-name").set_value("Nouvelle")
    element(user, "dialog-armor_points").set_value("lots")
    click(user, "dialog-save")
    assert user.notify.contains("whole number") and len(state.inventory["armors"]) == 5


async def test_editing_an_item_from_the_selection(user: User, state):
    await open_app(user, state)
    await open_tab(user, "Items")
    element(user, "item-kind").set_value("armors")
    await settle(0.1)
    click(user, "items-edit")
    assert user.notify.contains("Select an item first")
    table = user.find(ui.table).elements.pop()
    table.selected = [table.rows[3]]
    click(user, "items-edit")
    await user.should_see("Edit Armure lourde")
    element(user, "dialog-armor_points").set_value("4")
    click(user, "dialog-save")
    await settle()
    assert state.inventory["armors"][3]["armor_points"] == "4"


async def test_deleting_an_item_warns_when_it_is_used(user: User, state):
    await open_app(user, state)
    await open_tab(user, "Items")
    element(user, "item-kind").set_value("ranged_weapons")
    await settle(0.1)
    table = user.find(ui.table).elements.pop()
    index = next(i for i, item in enumerate(state.inventory["ranged_weapons"]) if item["name"] == "Pistolet")
    table.selected = [table.rows[index]]
    click(user, "items-delete")
    await user.should_see("It is used by: Else Sigloben")
    click(user, "confirm")
    await settle()
    assert all(item["name"] != "Pistolet" for item in state.inventory["ranged_weapons"])
    assert user.notify.messages == []


async def test_saving_the_database_writes_to_the_db_folder(user: User, state, tmp_path):
    await open_app(user, state)
    await open_tab(user, "Items")
    click(user, "download-db")
    assert json.loads((await user.download.next()).content) == state.db_data
    click(user, "save-db")
    saved = tmp_path / "db" / "db.json"
    assert json.loads(saved.read_text(encoding="utf-8")) == state.db_data and state.db_path == str(saved)


async def test_opening_a_database_from_the_folder(user: User, state, tmp_path):
    (tmp_path / "db").mkdir()
    custom = {"inventory": {"melee_weapons": [{"name": "Épée", "reach": "Moyenne", "damage": "5", "attributes": [], "encumbrance": "1", "2M": False}]}}
    (tmp_path / "db" / "custom.json").write_text(json.dumps(custom), encoding="utf-8")
    await open_app(user, state)
    await open_tab(user, "Items")
    click(user, "open-db")
    await user.should_see("Open an item database")
    element(user, "db-file").set_value("custom.json")
    click(user, "open-selected-db")
    await settle()
    assert [i["name"] for i in state.inventory["melee_weapons"]] == ["Épée"] and state.inventory["armors"] == []
    await user.should_see("1 items")


async def test_opening_a_file_that_is_not_a_database_is_refused(user: User, state, tmp_path):
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "bad.json").write_text(json.dumps({"nothing": 1}), encoding="utf-8")
    await open_app(user, state)
    await open_tab(user, "Items")
    click(user, "open-db")
    await user.should_see("Open an item database")
    element(user, "db-file").set_value("bad.json")
    click(user, "open-selected-db")
    assert user.notify.contains("no 'inventory'") and state.inventory["armors"]


# --- results -------------------------------------------------------------------------------------------------------

async def test_before_any_run_the_results_tab_invites_to_run(user: User, state):
    await open_app(user, state)
    await open_tab(user, "Results")
    await user.should_see("Run a simulation to see the results.")


async def test_the_settings_come_from_the_job(user: User, state):
    state.job["simulation"] = {"num_simulations": 321, "initial_distance": 7}
    await open_app(user, state)
    await open_tab(user, "Results")
    assert element(user, "combats").value == 321 and element(user, "distance").value == 7


async def test_running_a_simulation_shows_the_summary_and_a_chart(user: User, state):
    await open_app(user, state)
    await run_simulation(user, state, 200)
    assert len(state.runs) == 1 and state.run.metrics["total_battles"] == 200 and state.run.logs == 100
    for text in ("Joueurs", "Faction2", "Combat length", "median"):
        await user.should_see(text)
    assert titles(user)[:2] == ["Chance of winning", "Chance of surviving"]
    assert state.job["simulation"]["num_simulations"] == 200  # the settings are kept in the job


async def test_a_seeded_run_is_reproducible(user: User, state):
    await open_app(user, state)
    await run_simulation(user, state, 100)
    click(user, "run")
    for _ in range(200):
        if len(state.runs) == 2:
            break
        await asyncio.sleep(0.05)
    first, second = state.runs
    assert first.metrics["survival_probabilities"] == second.metrics["survival_probabilities"]
    assert state.current_run == 1


async def test_every_chart_is_built_from_the_run(user: User, state):
    await open_app(user, state)
    await run_simulation(user, state, 100)
    names = list(state.run.metrics["members"])
    assert titles(user) == ["Chance of winning", "Chance of surviving", *names, "Where the hits land", "Where the damage lands"]


async def test_the_table_tab_lists_every_character(user: User, state):
    await open_app(user, state)
    await run_simulation(user, state, 100)
    table = table_with(user, "survives")
    assert [row["name"] for row in table.rows] == [m["name"] for f in state.job["factions"] for m in f["members"]]
    assert all("%" in row["survives"] for row in table.rows)


async def test_the_replay_tab_shows_a_fight_log(user: User, state):
    await open_app(user, state)
    await run_simulation(user, state, 100)
    table = table_with(user, "attacker")
    assert table.rows[0]["action"] == "Combat starts" and len(table.rows) > 5
    before = list(table.rows)
    element(user, "fight-select").set_value(1)
    await settle(0.1)
    after = table_with(user, "attacker").rows
    assert after[0]["action"] == "Combat starts" and after != before  # another fight


async def test_the_replay_says_when_no_log_was_kept(user: User, state):
    from src.loader import create_characters
    from src.simulation import Simulation
    simulation = Simulation(create_characters(state.job["factions"], state.inventory), seed=1)
    results = simulation.run_simulation(20, keep_logs=0)
    state.add_run(results, simulation.gather_metrics(results))
    await open_app(user, state)
    await open_tab(user, "Results")
    user.find(kind=ui.tab, content="Replay").click()
    await settle(0.1)
    await user.should_see("No fight log was kept for this run.")


async def test_switching_run_changes_the_displayed_results(user: User, state):
    await open_app(user, state)
    await run_simulation(user, state, 50)
    element(user, "seed").set_value(2)
    click(user, "run")
    for _ in range(200):
        if len(state.runs) == 2:
            break
        await asyncio.sleep(0.05)
    assert state.current_run == 1
    element(user, "run-select").set_value(0)
    await settle(0.1)
    assert state.current_run == 0


async def test_the_dark_switch_recolours_the_charts(user: User, state):
    await open_app(user, state)
    await run_simulation(user, state, 50)
    assert {c.options["backgroundColor"] for c in user.find(kind=ui.echart).elements} == {"#fcfcfb"}
    element(user, "dark").set_value(True)
    await settle(0.2)
    assert state.dark
    assert {c.options["backgroundColor"] for c in user.find(kind=ui.echart).elements} == {"#1a1a19"}


async def test_downloads_of_the_results(user: User, state):
    await open_app(user, state)
    await run_simulation(user, state, 50)
    click(user, "download-json")
    assert json.loads((await user.download.next()).content)["metrics"]["total_battles"] == 50
    click(user, "download-csv")
    assert (await user.download.next()).content.decode().startswith("faction,name,survival")
    click(user, "download-png")
    archive = (await user.download.next(timeout=10)).content
    assert archive[:2] == b"PK" and b"survival.png" in archive


async def test_a_job_with_problems_is_not_run(user: User, state):
    state.job["factions"][0]["members"][0]["inventory"].append({"type": "armors", "name": "Nope"})
    await open_app(user, state)
    await open_tab(user, "Results")
    click(user, "run")
    await settle(0.1)
    assert not state.runs and user.notify.contains("Nope")


async def test_invalid_settings_are_reported(user: User, state):
    await open_app(user, state)
    await open_tab(user, "Results")
    element(user, "combats").set_value(-5)
    click(user, "run")
    await settle(0.1)
    assert not state.runs and user.notify.contains("must be positive")


async def test_editing_the_job_changes_what_is_simulated(user: User, state):
    await open_app(user, state)
    select_node(user, "f1")
    await user.should_see("Faction: Faction2")
    click(user, "add-character")
    await user.should_see("Character: New character")
    await run_simulation(user, state, 50)
    assert "New character" in state.run.metrics["members"]
