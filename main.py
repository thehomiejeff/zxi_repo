#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main entry point for ZXI Bot
Handles bot initialization, command registration, and callback routing
"""

import os
import sys
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union

# Check Python Telegram Bot version
try:
    from telegram import __version__ as ptb_version
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    
    if int(ptb_version.split('.')[0]) >= 20:
        # For version 20.x and above
        from telegram.ext import (
            Application, CommandHandler, CallbackQueryHandler, 
            MessageHandler, ContextTypes, filters
        )
        USING_NEW_API = True
    else:
        # For version 13.x
        from telegram.ext import (
            Updater, CommandHandler, CallbackQueryHandler, 
            MessageHandler, Filters, Dispatcher
        )
        USING_NEW_API = False
except ImportError:
    print("python-telegram-bot package not found. Please install it with: pip install python-telegram-bot")
    sys.exit(1)

# Import utility modules
from utils.logger import setup_logger, get_logger
from utils.database import Database
from utils.fangen_lore_manager import FangenLoreManager
from utils.quest_manager import QuestManager
from utils.callback_utils import parse_callback_data, create_callback_data
from utils.error_handler import error_handler, ErrorContext

# Import command handlers
from handlers.lore_handlers import LoreCommandHandlers
from handlers.quest_handlers import QuestCommandHandlers

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv package not found. Using environment variables directly.")

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("BOT_TOKEN not found in environment variables. Please set it in .env file or environment.")
    sys.exit(1)

BOT_NAME = os.getenv('BOT_NAME', 'ZXI')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Set up logging
setup_logger(LOG_LEVEL)
logger = get_logger(__name__)

# Global variables
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Command handlers
@error_handler(error_type="command", custom_message="I couldn't process that command. Please try again.")
async def start_command(update: Update, context: Union[ContextTypes.DEFAULT_TYPE, Any]) -> None:
    """Handle the /start command."""
    if not update or not update.message:
        logger.error("Update or message is None in start_command")
        return
        
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")
    
    # Get database from context
    db = None
    if USING_NEW_API:
        db = context.application.bot_data.get("db")
    else:
        db = context.bot_data.get("db")
    
    if db:
        # Check if user exists in database
        if not db.user_exists(user.id):
            # Register new user
            db.register_user(user.id, user.username)
            
            welcome_message = (
                f"🌟 *Welcome to {BOT_NAME}, {user.first_name}!* 🌟\n\n"
                "I'm your guide to the mystical world of Fangen, a realm of elemental forces, "
                "ancient empires, and legendary beings.\n\n"
                "Here's what you can do:\n"
                "• Explore the lore with /lore\n"
                "• Search for specific information with /search\n"
                "• Discover random lore with /discover\n"
                "• Embark on quests with /quests\n"
                "• View your collection with /collection\n\n"
                "What would you like to do first?"
            )
        else:
            # Update last active timestamp
            db.execute_query(
                "UPDATE users SET last_active = ? WHERE user_id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user.id)
            )
            
            welcome_message = (
                f"*Welcome back to {BOT_NAME}, {user.first_name}!*\n\n"
                "What would you like to do today?\n\n"
                "• Explore the lore with /lore\n"
                "• Search for specific information with /search\n"
                "• Discover random lore with /discover\n"
                "• Embark on quests with /quests\n"
                "• View your collection with /collection"
            )
    else:
        logger.error("Database not found in context")
        welcome_message = (
            f"*Welcome to {BOT_NAME}!*\n\n"
            "I'm experiencing some technical difficulties at the moment. "
            "Please try again later."
        )
    
    # Create keyboard
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📚 Explore Lore", callback_data=create_callback_data("lore_menu")),
            InlineKeyboardButton("🔍 Search", callback_data=create_callback_data("search_menu"))
        ],
        [
            InlineKeyboardButton("🎲 Discover", callback_data=create_callback_data("lore_discover")),
            InlineKeyboardButton("⚔️ Quests", callback_data=create_callback_data("quest_menu"))
        ],
        [
            InlineKeyboardButton("📋 Collection", callback_data=create_callback_data("lore_collection")),
            InlineKeyboardButton("❓ Help", callback_data=create_callback_data("help_menu"))
        ]
    ])
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@error_handler(error_type="command", custom_message="I couldn't process that command. Please try again.")
async def help_command(update: Update, context: Union[ContextTypes.DEFAULT_TYPE, Any]) -> None:
    """Handle the /help command."""
    if not update or not update.message:
        logger.error("Update or message is None in help_command")
        return
        
    help_text = (
        f"*{BOT_NAME} Help Guide*\n\n"
        "*Basic Commands*\n"
        "• /start - Begin your journey or return to the main menu\n"
        "• /help - Display this help message\n\n"
        
        "*Lore Commands*\n"
        "• /lore - Explore the world of Fangen\n"
        "• /search [term] - Search for specific lore\n"
        "• /discover - Find random lore entries\n"
        "• /collection - View your discovered lore\n\n"
        
        "*Quest Commands*\n"
        "• /quests - View available quests\n"
        "• /quest [name] - Start or continue a specific quest\n"
        "• /active - See your active quests\n"
        "• /inventory - Check your items\n"
        "• /craft - Craft new items\n"
        "• /characters - View characters you've met\n"
        "• /interact [character] - Interact with a character\n\n"
        
        "For more detailed help on a specific feature, use the buttons below:"
    )
    
    # Create keyboard
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📚 Lore Help", callback_data=create_callback_data("help_lore")),
            InlineKeyboardButton("⚔️ Quest Help", callback_data=create_callback_data("help_quests"))
        ],
        [
            InlineKeyboardButton("🧰 Inventory Help", callback_data=create_callback_data("help_inventory")),
            InlineKeyboardButton("👥 Character Help", callback_data=create_callback_data("help_characters"))
        ],
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
        ]
    ])
    
    await update.message.reply_text(
        help_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@error_handler(error_type="callback", custom_message="I couldn't process that button press. Please try again.")
async def handle_callback(update: Update, context: Union[ContextTypes.DEFAULT_TYPE, Any]) -> None:
    """Handle callback queries."""
    if not update or not update.callback_query or not update.effective_user:
        logger.error("Update, callback_query, or effective_user is None in handle_callback")
        return
        
    query = update.callback_query
    
    # Parse callback data
    try:
        callback_data = parse_callback_data(query.data)
        action = callback_data.get("action", "")
    except Exception as e:
        logger.error(f"Failed to parse callback data: {e}")
        await query.answer("Invalid callback data")
        return
    
    # Get handlers from context
    lore_handlers = None
    quest_handlers = None
    
    if USING_NEW_API:
        lore_handlers = context.application.bot_data.get("lore_handlers")
        quest_handlers = context.application.bot_data.get("quest_handlers")
    else:
        lore_handlers = context.bot_data.get("lore_handlers")
        quest_handlers = context.bot_data.get("quest_handlers")
    
    # Route to appropriate handler
    try:
        if action.startswith("lore_"):
            if lore_handlers:
                await lore_handlers.handle_callback(update, context, callback_data)
            else:
                logger.error("lore_handlers not found in context")
                await query.answer("Lore handlers not available")
        elif action.startswith("quest_"):
            if quest_handlers:
                await quest_handlers.handle_callback(update, context, callback_data)
            else:
                logger.error("quest_handlers not found in context")
                await query.answer("Quest handlers not available")
        elif action.startswith("search_"):
            if lore_handlers:
                await lore_handlers.handle_callback(update, context, callback_data)
            else:
                logger.error("lore_handlers not found in context")
                await query.answer("Search handlers not available")
        elif action.startswith("help_"):
            await query.answer("Opening help section")
            await handle_help_callback(update, context, callback_data)
        elif action == "main_menu":
            await query.answer("Returning to main menu")
            # Create a fake update to reuse the start_command
            await start_command(update, context)
        else:
            logger.warning(f"Unknown callback action: {action}")
            await query.answer("Unknown action")
    except Exception as e:
        logger.error(f"Error handling callback: {e}")
        await query.answer("Error processing your request")

async def handle_help_callback(update: Update, context: Union[ContextTypes.DEFAULT_TYPE, Any], callback_data: Dict[str, Any]) -> None:
    """Handle help-related callbacks."""
    if not update or not update.callback_query:
        logger.error("Update or callback_query is None in handle_help_callback")
        return
        
    query = update.callback_query
    action = callback_data.get("action", "")
    
    # Help text based on action
    if action == "help_lore":
        help_text = (
            "*Lore Help*\n\n"
            "The world of Fangen is rich with lore, history, and mysteries to discover.\n\n"
            "*Commands:*\n"
            "• /lore - Browse lore categories\n"
            "• /search [term] - Search for specific lore entries\n"
            "• /discover - Find random lore entries\n"
            "• /collection - View your discovered lore\n\n"
            
            "*Tips:*\n"
            "• Use specific search terms for better results\n"
            "• Discover new lore regularly to build your collection\n"
            "• Some lore is only revealed through quests or character interactions"
        )
    elif action == "help_quests":
        help_text = (
            "*Quest Help*\n\n"
            "Embark on adventures throughout Fangen, make choices, and shape your destiny.\n\n"
            "*Commands:*\n"
            "• /quests - View available quests\n"
            "• /quest [name] - Start or continue a specific quest\n"
            "• /active - See your active quests\n\n"
            
            "*Tips:*\n"
            "• Your choices affect quest outcomes\n"
            "• Some quests require specific items or lore knowledge\n"
            "• Quests may unlock new characters, items, or lore"
        )
    elif action == "help_inventory":
        help_text = (
            "*Inventory Help*\n\n"
            "Collect items, craft new ones, and use them in your adventures.\n\n"
            "*Commands:*\n"
            "• /inventory - View your collected items\n"
            "• /craft - View available crafting recipes\n"
            "• /craft [item] - Craft a specific item\n\n"
            
            "*Tips:*\n"
            "• Items can be found during quests\n"
            "• Some items are required for specific quests\n"
            "• Rare items can be crafted from common ones"
        )
    elif action == "help_characters":
        help_text = (
            "*Character Help*\n\n"
            "Meet and interact with the inhabitants of Fangen.\n\n"
            "*Commands:*\n"
            "• /characters - View characters you've met\n"
            "• /interact - Speak with characters from Fangen\n"
            "• /interact [name] - Speak with a specific character\n\n"
            
            "*Tips:*\n"
            "• Characters remember your interactions\n"
            "• Building relationships can unlock new quests\n"
            "• Characters may provide hints about lore and quests"
        )
    else:
        help_text = "Help section not found."
    
    # Create keyboard
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("« Back to Help", callback_data=create_callback_data("help_menu")),
            InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
        ]
    ])
    
    await query.edit_message_text(
        help_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def post_init(application: Application) -> None:
    """Post-initialization setup for the application."""
    logger.info("Performing post-initialization setup")
    
    try:
        # Initialize database
        db = Database()
        application.bot_data["db"] = db
        
        # Initialize lore manager
        lore_manager = FangenLoreManager()
        application.bot_data["lore_manager"] = lore_manager
        
        # Initialize quest manager
        quest_manager = QuestManager(db, lore_manager)
        application.bot_data["quest_manager"] = quest_manager
        
        # Initialize handlers with dependencies
        lore_handlers = LoreCommandHandlers(db, lore_manager)
        application.bot_data["lore_handlers"] = lore_handlers
        
        quest_handlers = QuestCommandHandlers(db, quest_manager, lore_manager)
        application.bot_data["quest_handlers"] = quest_handlers
        
        logger.info("Bot components initialized successfully")
    except Exception as e:
        logger.error(f"Error in post_init: {e}")
        raise

def main() -> None:
    """Start the bot."""
    try:
        if USING_NEW_API:
            # For version 20.x and above - Use Application
            logger.info("Using python-telegram-bot v20+ API")
            
            # Initialize database and managers first
            db = Database()
            lore_manager = FangenLoreManager()
            quest_manager = QuestManager(db, lore_manager)
            
            # Initialize handlers with proper dependencies
            lore_handlers = LoreCommandHandlers(db, lore_manager)
            quest_handlers = QuestCommandHandlers(db, quest_manager, lore_manager)
            
            # Build application with post_init for additional setup
            application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
            
            # Store components in bot_data for access in handlers
            application.bot_data["db"] = db
            application.bot_data["lore_manager"] = lore_manager
            application.bot_data["quest_manager"] = quest_manager
            application.bot_data["lore_handlers"] = lore_handlers
            application.bot_data["quest_handlers"] = quest_handlers
            
            # Add command handlers
            application.add_handler(CommandHandler("start", start_command))
            application.add_handler(CommandHandler("help", help_command))
            
            # Add lore command handlers
            application.add_handler(CommandHandler("lore", lore_handlers.lore_command))
            application.add_handler(CommandHandler("search", lore_handlers.search_command))
            application.add_handler(CommandHandler("discover", lore_handlers.discover_command))
            application.add_handler(CommandHandler("collection", lore_handlers.collection_command))
            
            # Add quest command handlers
            application.add_handler(CommandHandler("quests", quest_handlers.quests_command))
            application.add_handler(CommandHandler("quest", quest_handlers.quest_command))
            application.add_handler(CommandHandler("active", quest_handlers.active_command))
            application.add_handler(CommandHandler("inventory", quest_handlers.inventory_command))
            application.add_handler(CommandHandler("craft", quest_handlers.craft_command))
            application.add_handler(CommandHandler("characters", quest_handlers.characters_command))
            application.add_handler(CommandHandler("interact", quest_handlers.interact_command))
            
            # Add callback query handler
            application.add_handler(CallbackQueryHandler(handle_callback))
            
            # Start the bot
            logger.info("Starting bot")
            application.run_polling()
            
        else:
            # For version 13.x - Use Updater
            logger.info("Using python-telegram-bot v13.x API")
            
            # Create the Updater and pass it your bot's token
            updater = Updater(BOT_TOKEN)
            
            # Get the dispatcher to register handlers
            dispatcher = updater.dispatcher
            
            # Initialize bot components
            db = Database()
            dispatcher.bot_data["db"] = db
            
            lore_manager = FangenLoreManager()
            dispatcher.bot_data["lore_manager"] = lore_manager
            
            quest_manager = QuestManager(db, lore_manager)
            dispatcher.bot_data["quest_manager"] = quest_manager
            
            lore_handlers = LoreCommandHandlers(db, lore_manager)
            dispatcher.bot_data["lore_handlers"] = lore_handlers
            
            quest_handlers = QuestCommandHandlers(db, quest_manager, lore_manager)
            dispatcher.bot_data["quest_handlers"] = quest_handlers
            
            # Add command handlers
            dispatcher.add_handler(CommandHandler("start", start_command))
            dispatcher.add_handler(CommandHandler("help", help_command))
            
            # Add lore command handlers
            dispatcher.add_handler(CommandHandler("lore", lore_handlers.lore_command))
            dispatcher.add_handler(CommandHandler("search", lore_handlers.search_command))
            dispatcher.add_handler(CommandHandler("discover", lore_handlers.discover_command))
            dispatcher.add_handler(CommandHandler("collection", lore_handlers.collection_command))
            
            # Add quest command handlers
            dispatcher.add_handler(CommandHandler("quests", quest_handlers.quests_command))
            dispatcher.add_handler(CommandHandler("quest", quest_handlers.quest_command))
            dispatcher.add_handler(CommandHandler("active", quest_handlers.active_command))
            dispatcher.add_handler(CommandHandler("inventory", quest_handlers.inventory_command))
            dispatcher.add_handler(CommandHandler("craft", quest_handlers.craft_command))
            dispatcher.add_handler(CommandHandler("characters", quest_handlers.characters_command))
            dispatcher.add_handler(CommandHandler("interact", quest_handlers.interact_command))
            
            # Add callback query handler
            dispatcher.add_handler(CallbackQueryHandler(handle_callback))
            
            # Start the bot
            logger.info("Starting bot")
            updater.start_polling()
            
            # Run the bot until you press Ctrl-C
            updater.idle()
            
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
