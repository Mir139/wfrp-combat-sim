# Warhammer Fantasy Role Play Combat Simulator

## Overview
The WFRP Combat Simulator is a turn-based combat simulation framework designed for role-playing games. It allows users to define characters with various attributes, manage their inventories, and simulate combat scenarios between different factions. The project aims to provide insights into survival probabilities and combat dynamics. It is based on the 4th edition of the game Warhammer Fantasy Role Play.

## Project Structure
```
rpg-combat-simulator
├── src
│   ├── __init__.py
│   ├── character.py
│   ├── combat.py
│   ├── faction.py
│   ├── inventory.py
│   ├── simulation.py
│   └── utils.py
├── tests
│   ├── __init__.py
│   ├── test_character.py
│   ├── test_combat.py
│   ├── test_faction.py
│   ├── test_inventory.py
│   └── test_simulation.py
├── requirements.txt
└── README.md
```

## Features
- **Character Management**: Define characters with attributes such as name, health, attack, defense, and faction.
- **Inventory System**: Manage items that characters can hold, affecting their combat capabilities.
- **Turn-Based Combat**: Simulate combat phases between characters with defined rules.
- **Faction Management**: Group characters into factions and manage their interactions.
- **Simulation and Metrics**: Run multiple combat simulations to derive survival probabilities and other metrics.
- **Graphical User Interface**: A simple and modern GUI to manage and run simulations.

## Installation
1. Clone the repository:
   ```
   git clone https://github.com/Mir139/wfrp-combat-sim.git
   ```
2. Navigate to the project directory:
   ```
   cd rpg-combat-simulator
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage
To simulate combat, you can use the graphical user interface or run the simulation directly from the command line.

### Using the GUI
1. Run the GUI:
   ```python
   gui.py
   ```
2. Use the interface to load `job1.json` and `db.json`, configure the number of simulations, and run the simulation.

### Running from the Command Line
1. Ensure `job1.json` and `db.json` are properly configured.
2. Run the simulation:
   ```python
   python src/simulation.py
   ```

## Testing
Unit tests are provided for each component of the project. To run the tests, use:
```
pytest tests/
```

## Configuration Files
- **job1.json**: Defines the factions and their members for the simulation.
- **db.json**: Contains the inventory items that can be used by characters.

### Example Configuration (job1.json)
   ```json
   {
    "factions": [
        {
            "name": "Faction1",
            "members": [
                {
                    "name": "Hero1",
                    "health": 10,
                    "M": 4,
                    "CC": 50,
                    "CT": 30,
                    "F": 40,
                    "E": 30,
                    "I": 20,
                    "Ag": 30,
                    "Dex": 20,
                    "Int": 30,
                    "FM": 20,
                    "Soc": 10,
                    "inventory": [
                        {
                            "type": "melee_weapons",
                            "name": "(2M) Épée bâtarde"
                        },
                        {
                            "type": "armors",
                            "name": "Armure lourde"
                        }
                    ]
                },
                {
                    "name": "Hero2",
                    "health": 12,
                    "M": 4,
                    "CC": 35,
                    "CT": 45,
                    "F": 35,
                    "E": 25,
                    "I": 25,
                    "Ag": 25,
                    "Dex": 25,
                    "Int": 25,
                    "FM": 25,
                    "Soc": 15,
                    "inventory": [
                        {
                            "type": "ranged_weapons",
                            "name": "(2M) Arc long"
                        },
                        {
                            "type": "armors",
                            "name": "Armure légère"
                        }
                    ]
                }
            ]
        },
        {
            "name": "Faction2",
            "members": [
                {
                    "name": "Enemy1",
                    "health": 14,
                    "M": 4,
                    "CC": 40,
                    "CT": 20,
                    "F": 30,
                    "E": 20,
                    "I": 10,
                    "Ag": 20,
                    "Dex": 10,
                    "Int": 20,
                    "FM": 10,
                    "Soc": 5,
                    "inventory": [
                        {
                            "type": "melee_weapons",
                            "name": "Hache"
                        },
                        {
                            "type": "armors",
                            "name": "Armure moyenne"
                        }
                    ]
                },
                {
                    "name": "Enemy2",
                    "health": 16,
                    "M": 4,
                    "CC": 30,
                    "CT": 35,
                    "F": 25,
                    "E": 15,
                    "I": 15,
                    "Ag": 15,
                    "Dex": 15,
                    "Int": 15,
                    "FM": 15,
                    "Soc": 10,
                    "inventory": [
                        {
                            "type": "ranged_weapons",
                            "name": "Arbalète"
                        },
                        {
                            "type": "armors",
                            "name": "Armure légère"
                        }
                    ]
                }
            ]
        }
    ],
    "simulation": {
        "num_simulations": 100
    }
}
```

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.