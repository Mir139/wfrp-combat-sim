# RPG Combat Simulator

## Overview
The RPG Combat Simulator is a turn-based combat simulation framework designed for role-playing games. It allows users to define characters with various attributes, manage their inventories, and simulate combat scenarios between different factions. The project aims to provide insights into survival probabilities and combat dynamics.

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

## Installation
1. Clone the repository:
   ```
   git clone <repository-url>
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
To simulate combat, create instances of the `Character`, `Faction`, and `Combat` classes. Use the `Simulation` class to run multiple combat scenarios and analyze the results.

## Testing
Unit tests are provided for each component of the project. To run the tests, use:
```
pytest tests/
```

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.