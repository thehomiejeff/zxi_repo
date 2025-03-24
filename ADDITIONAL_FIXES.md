# ZXI Bot Additional Fixes

This document outlines the additional fixes made to address the new errors encountered during testing.

## Summary of Fixes

1. **Invalid Escape Sequence in Regular Expression**
   - Fixed the invalid escape sequence `\d` in `fangen_lore_manager.py` by using a raw string prefix (`fr'...'`)
   - This resolves the SyntaxWarning: `invalid escape sequence '\d'`

2. **Python-Telegram-Bot Version Compatibility**
   - Implemented a version detection system to support both older (v13.x) and newer (v20+) versions of the python-telegram-bot library
   - Added conditional imports based on the detected version
   - Created separate initialization paths for each version
   - This resolves the error: `'Updater' object has no attribute '_Updater__polling_cleanup_cb'`

3. **Module Import Error**
   - Added code to insert the project root directory into the Python path in key files
   - Modified import statements to ensure proper module resolution
   - This resolves the error: `ModuleNotFoundError: No module named 'utils'`

## Detailed Changes by File

### utils/fangen_lore_manager.py
- Added `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` to ensure the project root is in the Python path
- Fixed the invalid escape sequence by changing:
  ```python
  quest_desc_pattern = f'Quest: {re.escape(title)}(.*?)(?:Scene \d+:|$)'
  ```
  to:
  ```python
  quest_desc_pattern = fr'Quest: {re.escape(title)}(.*?)(?:Scene \d+:|$)'
  ```

### utils/logger.py
- Added `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` to ensure the project root is in the Python path
- This ensures that the `config` module can be imported correctly

### main.py
- Completely restructured to support both v13.x and v20+ of python-telegram-bot
- Added version detection logic:
  ```python
  def get_telegram_bot_version():
      try:
          import telegram
          version = telegram.__version__.split('.')
          major_version = int(version[0])
          return major_version
      except (ImportError, AttributeError, ValueError, IndexError):
          logger.warning("Could not determine python-telegram-bot version, assuming version 13.x")
          return 13
  ```
- Implemented conditional imports based on version
- Created two separate initialization paths in the `main()` function:
  - For v20+: Uses the `Application` class
  - For v13.x: Uses the `Updater` class

## Installation and Usage

The improved codebase now works with both older and newer versions of the python-telegram-bot library:

1. For python-telegram-bot v13.x:
   ```
   pip install python-telegram-bot==13.15
   ```

2. For python-telegram-bot v20+:
   ```
   pip install python-telegram-bot
   ```

The bot will automatically detect which version is installed and use the appropriate API.

## Running the Bot

1. Extract the archive: `tar -xzvf zxi_improved_fixed_v2.tar.gz`
2. Navigate to the directory: `cd zxi_improved`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the bot: `python3 main.py`

The bot should now run without the previously encountered errors, regardless of which version of python-telegram-bot is installed.
