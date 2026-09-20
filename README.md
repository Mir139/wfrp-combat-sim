# WFRP Combat Simulator

Monte-Carlo combat simulator for **Warhammer Fantasy Roleplay 4th edition**. Describe two groups of
characters and their equipment in JSON, run thousands of fights, and get win probabilities, individual
survival rates and remaining health, so a GM can estimate how dangerous an encounter is for the party.

The rules are a **simplified** version of WFRP 4e: see [Rules](#rules) for what is modelled and
[Known limitations](#known-limitations) for what is approximated or missing.

## Installation

Requires Python 3.12 or later (the GUI uses nested f-string quotes).

```
git clone https://github.com/Mir139/wfrp-combat-sim.git
cd wfrp-combat-sim
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run everything from the project root, as modules (`src` is a package).

**Command line**: runs `sim/job1.json` against `db/db.json` and prints the metrics:

```
python -m src.simulation
```

**GUI** (Tkinter): pick the database and job files, set the number of simulations, run, then browse
the metrics of each job and replay the log of any single fight:

```
python -m src.gui
```

**From Python**: pass a seed to get reproducible results:

```python
from src.loader import load_inventory, load_simulation_config, create_characters
from src.simulation import Simulation

inventory = load_inventory("db/db.json")
config = load_simulation_config("sim/job1.json")
factions = create_characters(config["factions"], inventory)

sim = Simulation(factions, seed=42, initial_distance=12)
results = sim.run_simulation(1000)
print(sim.gather_metrics(results))
```

**Tests**:

```
pytest
```

## Configuration

### Job file (`sim/*.json`)

A job describes two or more factions and the simulation settings. Every faction fights every other one
(free-for-all); the last faction with fighters left wins.

| Field | Description |
|---|---|
| `factions[].name` | Faction name |
| `factions[].members[]` | Characters (see below) |
| `factions[].targeting`, `on_rout`, `rout_threshold` | Optional defaults for all members (see [Tactics](#tactics)) |
| `simulation.num_simulations` | Number of fights to run |
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
- Retreating to fight another day, regrouping, and target choice based on cover or line of sight.

## Project structure

```
db/db.json            item database (weapons and armors)
sim/job1.json         example job
src/
  rules.py            tests, opposed tests, range modifiers
  character.py        characteristics, states, weapon choice, attacks
  combat.py           one fight: placement, movement, targeting, morale, actions, log, winner
  simulation.py       many fights, metrics
  inventory.py        items, armor points, reloading
  loader.py           JSON -> characters
  faction.py          group of characters
  utils.py            dice helpers
  gui.py              Tkinter interface
tests/                pytest suite
```

## Contributing

Pull requests and issues are welcome.

## License

MIT, see [LICENSE](LICENSE).
