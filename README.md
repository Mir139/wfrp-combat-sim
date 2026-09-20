# WFRP Combat Simulator

Monte-Carlo combat simulator for **Warhammer Fantasy Roleplay 4th edition**. Describe two groups of
characters and their equipment in JSON, run thousands of fights, and get win probabilities, individual
survival rates and remaining health, so a GM can estimate how dangerous an encounter is for the party.

The rules are a **simplified** version of WFRP 4e: see [Rules](#rules) for what is modelled and
[Known limitations](#known-limitations) for what is approximated or missing.

## Installation

Developed and tested with Python 3.14. The GUI needs Tkinter (a system package on some Linux distributions,
e.g. `python3-tk`); the charts need matplotlib, which `requirements.txt` installs.

```
git clone https://github.com/Mir139/wfrp-combat-sim.git
cd wfrp-combat-sim
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run everything from the project root, as modules (`src` is a package).

**Command line**: estimate a job with many fights and print a report:

```
python -m src.simulation sim/job1.json -n 10000 --seed 1 -j 0
```

| Option | Description |
|---|---|
| `job` | Job file (default `sim/job1.json`) |
| `--db FILE` | Item database (default `db/db.json`) |
| `-n`, `--num-simulations` | Number of fights (default: the job's `num_simulations`, else 10000) |
| `--seed N` | Seed for reproducible results |
| `-j`, `--workers N` | Worker processes, `0` for one per CPU (default 1). The results do not depend on it |
| `--confidence C` | Confidence level of the intervals (default 0.95) |
| `--histogram` | Also print the remaining-health histogram of every character |
| `--compare FILE` | What-if analysis, see [Comparing scenarios](#comparing-scenarios) |
| `--plots DIR` | Save the charts as PNG files in `DIR` (with `--compare`: one comparison chart per faction) |
| `--json FILE` / `--csv FILE` | Export the metrics (CSV: one row per character, or per scenario and faction with `--compare`) |

**GUI** (Tkinter, three panels):

```
python -m src.gui
```

- **Factions**: edit the job. Add, duplicate and remove factions and characters, edit their characteristics,
  tactics (fighting style, targeting, rout) and inventory, open and save job files. *Import characters* reads a
  single character, a list, a faction or a whole job file, lets you choose which ones to add, and warns about
  items missing from the database.
- **Items**: browse, search and edit the item database (weapons and armors), open and save it. Deleting an item
  warns when characters use it.
- **Results**: set the number of combats, the distance and an optional seed, run, and browse the runs. Each run
  shows the text report and one of five charts (see [Charts](#charts)), lets you replay the log of any of the
  first 100 fights, and exports the charts, the JSON and the CSV. A job with problems (missing field, unknown
  item, duplicate name) is refused with the list of problems.

The default job and database are loaded at start-up. A run of 10000 combats blocks the window for a few seconds.

**From Python**: pass a seed to get reproducible results. When you use `workers` above 1, the script must be
guarded by `if __name__ == "__main__":`, because worker processes re-import it.

```python
from src.loader import load_inventory, load_simulation_config, create_characters
from src.simulation import Simulation

inventory = load_inventory("db/db.json")
config = load_simulation_config("sim/job1.json")
factions = create_characters(config["factions"], inventory)

sim = Simulation(factions, seed=42, initial_distance=12)
results = sim.run_simulation(10000, keep_logs=0, workers=4)  # keep_logs: fights that keep their action log
print(sim.gather_metrics(results))
```

**Tests**:

```
pytest
```

## Results

`gather_metrics` (and the report, JSON and CSV outputs) provide:

- **Chance of winning** of every faction, the number of draws, and the average Wounds left by the winners.
- **Per character**: probability of surviving (fleeing or surrendering counts as surviving), of dying, of
  being the first to fall, of routing, and the average Wounds left when alive.
- **Rounds per combat**: mean, median, min, max.
- **Remaining-health distribution** per character (`remaining_health_distribution`): the count of fights for
  every final value of Wounds, dead characters being 0. `--histogram` prints it in ten slices.
- **Confidence intervals** (Wilson score, 95% by default) on every probability, in `confidence_intervals`.
  With 10000 fights they are about ±1 point around 50% and much tighter near 0% or 100%.

Ten thousand fights of the example job take about 3 seconds on one core, and under a second on several. Only
the first 100 fights keep their action log, to bound the memory use.

### Charts

`--plots` and the GUI draw (matplotlib; one colour per faction, kept whatever is displayed):

- **Chance of winning** per faction, and **chance of surviving** per character, as bars with their confidence
  whiskers and the value at the tip.
- **Remaining Wounds**: for each character, the share of combats ending with each amount of Wounds.
- **Where the hits land** (and **where the damage lands**): a heatmap of the share of the hits (or the damage)
  each character takes on each body location. The raw counts are in `hit_locations` in the metrics.
- **Comparison** (`--compare --plots`): the chance of winning of a faction across the scenarios, with the change
  against the base scenario.

### Comparing scenarios

`--compare` runs the job and a list of variants of it with the **same seed**, so the differences between
scenarios are not blurred by dice noise, and prints the win chances and the survival of every character with
the change against the base scenario. A comparison file (see `sim/compare_example.json`) contains `variants`
and `sweeps`:

```json
{
    "variants": [
        { "name": "Molrella wears heavy armor",
          "add_items": [{ "member": "Molrella Tuilecaramel", "type": "armors", "name": "Armure lourde" }] },
        { "name": "Without Else", "remove_members": ["Else Sigloben"] }
    ],
    "sweeps": [
        { "copy_member": "Terreur de la Teufel", "counts": [1, 2, 3] },
        { "member": "Terreur de la Teufel", "field": "CC", "values": [50, 70] }
    ]
}
```

A variant can combine these operations, applied in this order:

| Operation | Effect |
|---|---|
| `simulation` | Override simulation settings, e.g. `{"initial_distance": 6}` |
| `faction_set` | Override faction fields, e.g. `{"Faction2": {"targeting": "weakest"}}` |
| `remove_members` | List of character names to remove |
| `copy_members` | `[{"member": "Goblin", "count": 2}]` adds clones named `Goblin 2`, `Goblin 3` |
| `add_members` | `[{"faction": "Faction2", "member": {...}}]` adds a full character |
| `set` | Override character fields, e.g. `{"Amris": {"CC": 60}}` |
| `add_items` / `remove_items` | Give or take an item: `{"member", "type", "name"}` / `{"member", "name"}` |

A sweep expands into one variant per value: either the values of a characteristic (`member`, `field`, `values`)
or a number of extra clones of an enemy (`copy_member`, `counts`).

## Configuration

### Job file (`sim/*.json`)

A job describes two or more factions and the simulation settings. Every faction fights every other one
(free-for-all); the last faction with fighters left wins.

| Field | Description |
|---|---|
| `factions[].name` | Faction name |
| `factions[].members[]` | Characters (see below) |
| `factions[].targeting`, `on_rout`, `rout_threshold` | Optional defaults for all members (see [Tactics](#tactics)) |
| `simulation.num_simulations` | Number of fights to run (default 10000) |
| `simulation.initial_distance` | Optional. Yards between the two sides at the start (default 12) |

A character has a `name`, `health` (Wounds) and the characteristics `M`, `CC`, `CT`, `F`, `E`, `I`, `Ag`,
`Dex`, `Int`, `FM`, `Soc`, plus an `inventory` referencing items of the database by `type` and `name`.
The optional `behavior` field (`"melee"` or `"ranged"`) forces the fighting style; otherwise it is
deduced from the equipment and from `CC` versus `CT`. The optional `targeting`, `on_rout` and
`rout_threshold` fields set the tactics and override the faction defaults.

```json
{
    "factions": [
        {
            "name": "Joueurs",
            "members": [
                {
                    "name": "Gunnar", "health": 18, "M": 4,
                    "CC": 45, "CT": 26, "F": 38, "E": 51, "I": 34, "Ag": 23,
                    "Dex": 38, "Int": 28, "FM": 52, "Soc": 18,
                    "inventory": [
                        { "type": "melee_weapons", "name": "(2M) Hache" },
                        { "type": "armors", "name": "Armure légère" }
                    ]
                }
            ]
        },
        {
            "name": "Faction2",
            "members": [
                {
                    "name": "Archer", "health": 12, "M": 4, "behavior": "ranged",
                    "targeting": "weakest", "on_rout": "flee",
                    "CC": 30, "CT": 45, "F": 30, "E": 30, "I": 30, "Ag": 30,
                    "Dex": 30, "Int": 30, "FM": 30, "Soc": 30,
                    "inventory": [
                        { "type": "ranged_weapons", "name": "(2M) Arc long" }
                    ]
                }
            ]
        }
    ],
    "simulation": { "num_simulations": 1000, "initial_distance": 12 }
}
```

### Item database (`db/db.json`)

Items are grouped under `melee_weapons`, `ranged_weapons` and `armors`.

- **Weapons** have `damage` and `attributes`. Melee weapons add the wielder's Strength Bonus (BF);
  ranged weapons do so only with `damage_BF`. For ranged weapons, `range` is in yards, or a multiple of BF
  when `range_BF` is set.
- **Armors** have `armor_points` and a `location`: `"Tous"` (all zones) or a list among `Tête`,
  `Bras gauche`, `Bras droit`, `Corps`, `Jambe gauche`, `Jambe droite`. Armors stack.

## Rules

Fighters act in Initiative order, each round, until a single faction has fighters left (a fight is a draw if
nobody is left, or after 1000 rounds). Combat is on a plane: the factions start on the vertices of a regular
polygon whose side is `initial_distance` yards (two factions simply face each other), all members of a faction
sharing the same spot. Two fighters are *engaged* when within 2 yards of each other.

**Tests.** Roll d100 against the target number. A roll of 5 or less always succeeds, 96 or more always
fails. SL is the difference of the tens digits. A double is a critical on a success and a fumble on a failure.

**Melee.** Opposed test, the attacker must succeed. The higher SL wins; on equal SL the higher target number
wins, then the defender. The defender takes the better of parry (`CC`) or dodge (`Ag`). Damage is
`BF + weapon + SL difference`, minus Toughness Bonus (BE) and the armor of the location (minimum 1).
The location comes from the reversed attack roll.

**Ranged.** Simple test with a range modifier, damage is `weapon (+ BF) + SL` minus BE and armor.

| Distance | Modifier |
|---|---|
| ≤ 2 yards | +40 |
| ≤ ½ range | +20 |
| ≤ range | 0 |
| ≤ 2× range | −10 |
| ≤ 3× range | −20 |
| beyond | no shot |

Powder and crossbow weapons must be reloaded (`Recharge N` actions, `Répétition N` shots per load), so a
fighter carrying two pistols fires both before reloading.

**Movement.** Walk 2×M yards, run 4×M yards. A melee fighter walks to the target and attacks in the same
turn if that puts them in melee, otherwise runs and does not attack. A shooter fires from where they stand
when in range, otherwise walks closer first. An engaged shooter fires a loaded pistol point blank, else fights
in melee. The weapon used in melee is the harmful weapon with the highest damage; with none, the fighter is unarmed.

**Conditions.**

| Condition | Effect | Ends |
|---|---|---|
| Stunned | −10 to tests | Toughness (E) test at the end of the turn |
| Prone | −20 in melee, attackers get +20 | Standing up uses the Move |
| Bleeding | Lose 1 Wound per level at the start of each turn | Never (see limitations) |

A critical hit ignores armor and inflicts Bleeding and Stunned. A melee fumble knocks the attacker prone; a
ranged fumble jams the weapon.

### Tactics

**Targeting.** Each fighter picks a target among the enemies still in the fight (or among the engaged ones once
in melee) according to `targeting`; ties are broken randomly. The default is `nearest`.

| Strategy | Target |
|---|---|
| `nearest` | Closest enemy |
| `weakest` | Enemy with the fewest Wounds left |
| `dangerous` | Enemy with the highest damage potential (skill × damage of their best weapon) |
| `random` | Random enemy, kept until it is out of the fight |

**Morale.** Fighters fight to the death unless `on_rout` is set to `"flee"` or `"surrender"`. They then take a
Cool test (Willpower, `FM`) the first time they are wounded down to `rout_threshold` of their starting Wounds
(default 0.25), and the first time half of their faction is dead or out of the fight. On a failure they leave the
fight: they can no longer be attacked, but they are alive and count as survivors. The metrics report the chance
of each character routing in `individual_rout_probabilities`.

**Weapon attributes handled:** Défensive (+1 SL when parrying), Protectrice N, Précise, Imprécise,
Assommante, Recharge N, Répétition N.

## Known limitations

These are the points to check against the rulebook and the features not implemented yet.

**Approximations to validate**
- **Critical hits** ignore armor and inflict Bleeding + Stunned. The critical wound tables are not
  reproduced.
- **Bleeding** cannot be stopped: no test, no healing.
- **Death** happens at 0 Wounds. There is no unconsciousness and no accumulation of critical wounds.
- **Protectrice N** adds N armor points against ranged attacks only, which is an interpretation of the rule.
- **Ranged fumbles** jam the weapon, which must then be fully reloaded.
- **Range bands** and the ±20 / +40 modifiers are written from memory and may not match the book.
- **Opposed tests**: a failed attacker always misses, even if the defender failed worse.
- **Positioning**: all fighters of a faction share the same spot, so once melee starts everybody is engaged with
  everybody.
- **Fleeing** is instantaneous: there is no pursuit, no free attack and no chance to be caught. A fighter who
  surrenders is never harmed afterwards.
- **Morale** is tested once per trigger, without modifiers (no Fear/Terror, no leader, no Stunned penalty).
- **Factions** are all hostile to each other; there is no way to declare allies or a shared side.

**Not implemented**
- Weapon attributes: Empaleuse, Taille, Percutante, Dévastatrice, Pointue, Rapide, Lente, Immobilisante,
  Dangereuse, Explosion, Inoffensive (beyond choosing another weapon first).
- Thrown weapons (knife, javelin, rock, bomb) have unlimited ammunition, and area effects are ignored.
- Advantage, manoeuvres beyond parry/dodge, reach, two-handed/off-hand rules.
- Import of character sheets from Foundry VTT or the WFRP GM Toolkit (only this project's own JSON is read, see
  `import_characters`), and a graphical editor for comparison files (they are written by hand).
- A dark theme for the charts, and progress display for long runs in the GUI.
- Retreating to fight another day, regrouping, and target choice based on cover or line of sight.

## Project structure

```
db/db.json            item database (weapons and armors)
sim/job1.json         example job
sim/compare_example.json  example comparison file
src/
  rules.py            tests, opposed tests, range modifiers
  character.py        characteristics, states, weapon choice, attacks
  combat.py           one fight: placement, movement, targeting, morale, actions, log, winner
  simulation.py       many fights (seeded, parallel), metrics with confidence intervals
  stats.py            Wilson confidence intervals
  compare.py          what-if variants and sweeps
  report.py           text, JSON and CSV output
  cli.py              command line (python -m src.simulation)
  plots.py            matplotlib charts
  jobs.py             job validation, blank characters, import of characters
  gui/                Tkinter interface: __init__ (application), factions, items, results
  inventory.py        items, armor points, reloading
  loader.py           JSON -> characters
  faction.py          group of characters
  utils.py            dice helpers
tests/                pytest suite
```

## Contributing

Pull requests and issues are welcome.

## License

MIT, see [LICENSE](LICENSE).
