# ZXI: The Lore-Driven Telegram Companion for the World of Fangen

ZXI is a feature-rich Telegram bot that brings the mystical world of Fangen to life through interactive storytelling, quests, character interactions, and lore exploration.

## 🌟 Features

- **Rich Lore Exploration**: Browse, search, and discover the extensive lore of Fangen
- **Interactive Quests**: Embark on adventures with branching storylines and meaningful choices
- **Character Interactions**: Meet and build relationships with the inhabitants of Fangen
- **Inventory & Crafting**: Collect items and craft powerful artifacts
- **Persistent Progress**: Your discoveries, relationships, and achievements are saved

## 🚀 Setup Instructions

### Prerequisites

- Python 3.7+
- A Telegram account
- A Telegram Bot Token (obtained from [BotFather](https://t.me/botfather))

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/thehomiejeff/zxi_repo.git
   cd zxi_repo
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Update to the latest python-telegram-bot:
   ```bash
   pip install python-telegram-bot --upgrade
   ```

5. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your preferred text editor
   ```

6. Run the setup script to initialize directories and database:
   ```bash
   python setup.py
   ```

### Pre-run Verification

Before running the bot, verify that:

1. All necessary database tables exist (run `python setup.py --verify`)
2. The `.env` file contains all required variables
3. The bot token is valid
4. All handler files are properly initialized

### Running the Bot

Start the bot with:
```bash
python main.py
```

## 📋 Commands

### Basic Commands
- `/start` - Begin your journey or return to the main menu
- `/help` - Display help message with available commands

### Lore Commands
- `/lore` - Explore the world of Fangen
- `/search [term]` - Search for specific lore
- `/discover` - Find random lore entries
- `/collection` - View your discovered lore

### Quest Commands
- `/quests` - View available quests
- `/quest [name]` - Start or continue a specific quest
- `/active` - See your active quests
- `/inventory` - Check your items
- `/craft` - Craft new items
- `/characters` - View characters you've met
- `/interact [character]` - Interact with a character

## 🌍 The World of Fangen

Fangen is a realm where elemental forces are not just natural phenomena but living essences interwoven with the destiny of its inhabitants. The world's history is marked by ancient empires, cataclysmic events, and a continuous struggle between order and chaos.

Key elements of the world include:
- **Elemental Forces**: Diamond, Paper, Fire, and other elements exist as physical manifestations
- **The Alpha Empire**: A powerful regime led by the Alpha Empress
- **The Great Wormhole**: A portal between dimensions, accidentally reopened by Wagami
- **Legendary Beings**: Characters like Hand of Diamond, Fist of Ape, and the Legendary Beasts

## 📁 Project Structure

```
zxi_repo/
├── main.py                 # Main entry point
├── config.py               # Configuration file
├── .env                    # Environment variables (create from .env.example)
├── setup.py                # Setup script for initialization
├── requirements.txt        # Project dependencies
├── data/                   # Data directory
│   ├── lore.txt            # Lore data file
│   └── fangen.db           # SQLite database (created by setup.py)
├── handlers/               # Command handlers
│   ├── __init__.py         # Package initializer
│   ├── lore_handlers.py    # Lore-related command handlers
│   └── quest_handlers.py   # Quest-related command handlers
├── utils/                  # Utility modules
│   ├── __init__.py         # Package initializer
│   ├── database.py         # Database utility
│   ├── logger.py           # Logging utility
│   ├── fangen_lore_manager.py # Fangen-specific lore manager
│   ├── quest_manager.py    # Quest management utility
│   ├── callback_utils.py   # Callback data utilities
│   ├── error_handler.py    # Error handling utilities
│   └── ui_utils.py         # UI creation utilities
└── logs/                   # Log files directory (auto-created)
```

## 🛠️ Development

### Adding New Quests

Quests are structured as scenes with choices that affect the narrative progression. To add a new quest:
1. Create a structured quest description in the lore file with scenes, choices, and outcomes
2. Ensure all required items and rewards are properly defined
3. Test the quest flow to ensure all branches work correctly

### Adding New Characters

To add a new character:
1. Add the character profile to the lore file with backstory, personality, and relationships
2. Create dialogue patterns for the character in the FangenLoreManager
3. Test character interactions to ensure they respond appropriately

### Adding New Crafting Recipes

To add a new crafting recipe:
1. Define the recipe in the database with required components and results
2. Add any quest prerequisites if needed
3. Update the lore file with information about the new item

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Special thanks to all the contributors who helped bring the world of Fangen to life
- Inspired by the rich tradition of interactive storytelling and text-based adventures
- Built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)

---
*"In the world of Fangen, every choice shapes destiny, every element tells a story, and every character holds a piece of the truth."*
