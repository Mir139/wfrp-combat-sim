"""State of the application: the job and the item database being edited, and the runs made so far."""
import json
import os
import time
from dataclasses import dataclass, field

from src.jobs import ITEM_TYPES, new_job

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JOB_DIR = os.path.join(ROOT, "sim")
DB_DIR = os.path.join(ROOT, "db")
DEFAULT_JOB = os.path.join(JOB_DIR, "job1.json")
DEFAULT_DB = os.path.join(DB_DIR, "db.json")


def read_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def json_files(directory):
    """Names of the JSON files of a directory."""
    return sorted(name for name in os.listdir(directory) if name.endswith(".json")) if os.path.isdir(directory) else []


def safe_json_name(name, fallback):
    """A file name that stays inside its folder and ends with .json."""
    name = os.path.basename((name or "").strip()) or fallback
    return name if name.endswith(".json") else name + ".json"


@dataclass
class Run:
    results: list
    metrics: dict
    logs: int  # fights that kept their action log
    created: str = field(default_factory=lambda: time.strftime("%H:%M:%S"))


class AppState:
    """One instance is shared by all the browser tabs of this local application."""

    def __init__(self, job_dir=JOB_DIR, db_dir=DB_DIR):
        self.job = new_job()
        self.job_path = None
        self.db_data = {"inventory": {item_type: [] for item_type in ITEM_TYPES}}
        self.db_path = None
        self.job_dir = job_dir
        self.db_dir = db_dir
        self.runs = []
        self.current_run = None  # index in `runs`
        self.selection = None  # ("faction", fi) or ("member", fi, mi)
        self.dark = False
        self.workers = 0  # processes used by a run, 0 for one per CPU

    @property
    def inventory(self):
        return self.db_data["inventory"]

    def set_job(self, job, path=None):
        self.job = job
        self.job_path = path
        self.selection = None

    def set_db(self, data, path=None):
        data.setdefault("inventory", {})
        for item_type in ITEM_TYPES:
            data["inventory"].setdefault(item_type, [])
        self.db_data = data
        self.db_path = path

    def load_defaults(self):
        if os.path.exists(DEFAULT_DB):
            self.set_db(read_json(DEFAULT_DB), DEFAULT_DB)
        if os.path.exists(DEFAULT_JOB):
            self.set_job(read_json(DEFAULT_JOB), DEFAULT_JOB)

    def add_run(self, results, metrics):
        self.runs.append(Run(results, metrics, sum(1 for r in results if r["action_log"] is not None)))
        self.current_run = len(self.runs) - 1
        return self.runs[-1]

    @property
    def run(self):
        return self.runs[self.current_run] if self.current_run is not None else None
