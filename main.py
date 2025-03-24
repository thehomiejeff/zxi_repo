#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ZXI: The Lore-Driven Telegram Companion for the World of Fangen
Main entry point for the Telegram bot
"""

import logging
import os
import sys
import json
from datetime import datetime
import importlib

from config import BOT_TOKEN, ADMIN_IDS, LOG_LEVEL
from utils.logger import setup_logger

# Set up logging
logger = setup_logger(__name__, LOG_LEVEL)

# Check python-telegram-bot version and import appropriate modules
def get_telegram_bot_version():
    try:
        import telegram
        version = telegram.__version__.split('.')
        major_version = int(version[0])
        return major_version
    except (ImportError, AttributeError, ValueError, IndexError):
        logger.warning("Could not determine python-telegram-bot version, assuming version 13.x")
        return 13

# Import appropriate modules based on version
PTB_VERSION = get_telegram_bot_version()
logger.info(f"Detected python-telegram-bot version: {PTB_VERSION}.x")

if PTB_VERSION >= 20:
    # For version 20.x and above
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        ContextTypes,
        filters,
    )
    USING_NEW_API = True
else:
    # For version 13.x and below
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Updater,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        CallbackContext,
        Filters,
    )
    USING_NEW_API = False
    # Alias for compatibility
    ContextTypes = type('ContextTypes', (), {'DEFAULT_TYPE': CallbackContext})
    filters = Filters

# Import the rest of our modules
from utils.database import Database
from utils.fangen_lore_manager import FangenLoreManager
from utils.quest_manager import QuestManager
from utils.callback_utils import create_callback_data, parse_callback_data
from utils.error_handler import error_handler, ErrorContext, global_error_handler
from utils.ui_utils import create_styled_button, create_menu_keyboard
from handlers.lore_handlers import LoreCommandHandlers
from handlers.quest_handlers import QuestCommandHandlers

@error_handler(error_type="general", custom_message="I encountered an issue processing your request. Please try again.")
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued.
    
    Welcomes the user to the bot, registers them in the database if they're new,
    and presents the main menu options.
    
    Args:
        update: The update containing the command
        context: The context object for the bot
    """
    if not update or not update.effective_user:
        return
    
    user = update.effective_user
    user_id = user.id
    username = user.username or "Unknown"
    
    # Get database from context
    db = context.bot_data.get("db")
    if not db:
        await update.message.reply_text("Bot is still initializing. Please try again in a moment.")
        return
    
    # Register user if new
    with ErrorContext(db):
        if not db.user_exists(user_id):
            db.register_user(user_id, username)
            logger.info(f"New user registered: {username} ({user_id})")
    
    # Welcome message
    welcome_text = (
        f"🌟 *Welcome to the World of Fangen, {user.first_name}!* 🌟\n\n"
        "I am your guide to the mystical realm where ancient traditions and "
        "elemental powers shape the destiny of all beings.\n\n"
        "Here you can:\n"
        "• Explore the rich lore of Fangen\n"
        "• Embark on quests across the realm\n"
        "• Craft powerful items with mystical properties\n"
        "• Interact with the inhabitants of this world\n\n"
        "What would you like to do first?"
    )
    
    # Create menu keyboard
    menu_items = [
        ("📚 Explore Lore", create_callback_data("lore_menu"), "primary"),
        ("🗺️ View Quests", create_callback_data("quest_menu"), "primary"),
        ("👥 Meet Characters", create_callback_data("character_menu"), "secondary"),
        ("🔍 Search Knowledge", create_callback_data("search_menu"), "secondary")
    ]
    
    keyboard = create_menu_keyboard(menu_items)
    
    # Send welcome message with menu
    await update.message.reply_text(
        welcome_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@error_handler(error_type="general", custom_message="I encountered an issue processing your help request.")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued.
    
    Provides information about available commands and how to use the bot.
    
    Args:
        update: The update containing the command
        context: The context object for the bot
    """
    if not update or not update.message:
        return
    
    help_text = (
        "*ZXI: Your Guide to Fangen*\n\n"
        "Here are the commands you can use:\n\n"
        "*Basic Commands:*\n"
        "/start - Begin your journey or return to the main menu\n"
        "/help - Display this help message\n\n"
        
        "*Lore Commands:*\n"
        "/lore - Explore the world of Fangen\n"
        "/search [term] - Search for specific lore\n"
        "/discover - Find random lore entries\n"
        "/collection - View your discovered lore\n\n"
        
        "*Quest Commands:*\n"
        "/quests - View available quests\n"
        "/quest [name] - Start or continue a specific quest\n"
        "/active - See your active quests\n"
        "/inventory - Check your items\n"
        "/craft - Craft new items\n"
        "/characters - View characters you've met\n"
        "/interact [character] - Interact with a character\n\n"
        
        "You can also tap buttons and links to navigate through the bot."
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode="Markdown"
    )

@error_handler(error_type="callback", custom_message="I couldn't process that action. Please try again.")
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline keyboards.
    
    Routes the callback to the appropriate handler based on the action.
    
    Args:
        update: The update containing the callback query
        context: The context object for the bot
    """
    if not update or not update.callback_query:
        return
    
    # Store the last action for retry functionality
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    
    callback_query = update.callback_query
    
    try:
        # Parse the callback data
        callback_data = parse_callback_data(callback_query.data)
        
        # Store for retry
        context.user_data['last_callback'] = callback_query.data
        
        # Get the action
        action = callback_data.get("action", "")
        
        # Get handlers from context
        lore_handlers = context.bot_data.get("lore_handlers")
        quest_handlers = context.bot_data.get("quest_handlers")
        
        if not lore_handlers or not quest_handlers:
            await callback_query.answer("Bot is still initializing. Please try again in a moment.")
            return
        
        # Route to appropriate handler based on action prefix
        if action.startswith("lore"):
            await lore_handlers.handle_callback(update, context, callback_data)
        elif action.startswith("quest"):
            await quest_handlers.handle_callback(update, context, callback_data)
        elif action == "character_menu":
            await quest_handlers.characters_menu(update, context)
        elif action == "search_menu":
            await lore_handlers.search_menu(update, context)
        elif action == "retry":
            # Retry last action
            last_callback = context.user_data.get('last_callback')
            if last_callback and last_callback != callback_query.data:
                # Create a new callback query with the last action
                callback_query.data = last_callback
                await handle_callback(update, context)
            else:
                await callback_query.answer("No previous action to retry.")
        else:
            # Unknown action
            logger.warning(f"Unknown callback action: {action}")
            await callback_query.answer("I don't recognize that action.")
    except Exception as e:
        logger.error(f"Error handling callback: {e}", exc_info=True)
        await callback_query.answer("An error occurred. Please try again.")

@error_handler(error_type="message", custom_message="I couldn't process your message. Please try again.")
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle non-command messages.
    
    Processes natural language input and routes to appropriate handlers.
    
    Args:
        update: The update containing the message
        context: The context object for the bot
    """
    if not update or not update.message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Get handlers from context
    lore_handlers = context.bot_data.get("lore_handlers")
    quest_handlers = context.bot_data.get("quest_handlers")
    
    if not lore_handlers or not quest_handlers:
        await update.message.reply_text("Bot is still initializing. Please try again in a moment.")
        return
    
    # Check if user is in a conversation state
    db = context.bot_data.get("db")
    if not db:
        await update.message.reply_text("Bot is still initializing. Please try again in a moment.")
        return
    
    with ErrorContext(db):
        user_state = db.get_user_state(user_id)
    
    # Route based on user state
    if user_state and "quest_active" in user_state and user_state["quest_active"]:
        # User is in an active quest, route to quest handler
        await quest_handlers.handle_quest_input(update, context)
    elif user_state and "character_interaction" in user_state and user_state["character_interaction"]:
        # User is interacting with a character, route to character handler
        await quest_handlers.handle_character_input(update, context)
    else:
        # Try to interpret as a search query
        if len(message_text.split()) > 1:  # More than one word, likely a search
            await lore_handlers.search_command(update, context)
        else:
            # Default response
            await update.message.reply_text(
                "I'm not sure what you're asking. Try using a command like /help to see what I can do."
            )

# Initialize bot components
async def post_init(application):
    """Initialize bot components after the application is built.
    
    Args:
        application: The application instance
    """
    try:
        logger.info("Initializing bot components...")
        
        # Initialize database
        db = Database()
        application.bot_data["db"] = db
        
        # Initialize lore manager
        lore_manager = FangenLoreManager()
        application.bot_data["lore_manager"] = lore_manager
        
        # Initialize quest manager
        quest_manager = QuestManager(db)
        application.bot_data["quest_manager"] = quest_manager
        
        # Initialize handlers with dependencies
        lore_handlers = LoreCommandHandlers(db, lore_manager)
        application.bot_data["lore_handlers"] = lore_handlers
        
        quest_handlers = QuestCommandHandlers(db, quest_manager, lore_manager)
        application.bot_data["quest_handlers"] = quest_handlers
        
        logger.info("Bot components initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize bot components: {e}")
        raise

def main() -> None:
    """Start the bot."""
    try:
        if USING_NEW_API:
            # For version 20.x and above - Use Application
            logger.info("Using python-telegram-bot v20+ API")
            application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
            
            # Add command handlers
            application.add_handler(CommandHandler("start", start_command))
            application.add_handler(CommandHandler("help", help_command))
            
            # Add lore command handlers
            lore_handlers = LoreCommandHandlers(None, None)  # Will be properly initialized in post_init
            application.add_handler(CommandHandler("lore", lore_handlers.lore_command))
            application.add_handler(CommandHandler("search", lore_handlers.search_command))
            application.add_handler(CommandHandler("discover", lore_handlers.discover_command))
            application.add_handler(CommandHandler("collection", lore_handlers.collection_command))
            
            # Add quest command handlers
            quest_handlers = QuestCommandHandlers(None, None, None)  # Will be properly initialized in post_init
            application.add_handler(CommandHandler("quests", quest_handlers.quests_command))
            application.add_handler(CommandHandler("quest", quest_handlers.quest_command))
            application.add_handler(CommandHandler("active", quest_handlers.active_quests_command))
            application.add_handler(CommandHandler("inventory", quest_handlers.inventory_command))
            application.add_handler(CommandHandler("craft", quest_handlers.craft_command))
            application.add_handler(CommandHandler("characters", quest_handlers.characters_command))
            application.add_handler(CommandHandler("interact", quest_handlers.interact_command))
            
            # Add callback query handler
            application.add_handler(CallbackQueryHandler(handle_callback))
            
            # Add message handler for non-command messages
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            
            # Add error handler
            application.add_error_handler(global_error_handler)
            
            # Start the Bot
            logger.info("Starting bot with Application API...")
            application.run_polling()
        else:
            # For version 13.x and below - Use Updater
            logger.info("Using python-telegram-bot v13 API")
            updater = Updater(BOT_TOKEN)
            dispatcher = updater.dispatcher
            
            # Initialize bot components
            db = Database()
            dispatcher.bot_data["db"] = db
            
            lore_manager = FangenLoreManager()
            dispatcher.bot_data["lore_manager"] = lore_manager
            
            quest_manager = QuestManager(db)
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
            dispatcher.add_handler(CommandHandler("active", quest_handlers.active_quests_command))
            dispatcher.add_handler(CommandHandler("inventory", quest_handlers.inventory_command))
            dispatcher.add_handler(CommandHandler("craft", quest_handlers.craft_command))
            dispatcher.add_handler(CommandHandler("characters", quest_handlers.characters_command))
            dispatcher.add_handler(CommandHandler("interact", quest_handlers.interact_command))
            
            # Add callback query handler
            dispatcher.add_handler(CallbackQueryHandler(handle_callback))
            
            # Add message handler for non-command messages
            dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
            
            # Add error handler
            dispatcher.add_error_handler(global_error_handler)
            
            # Start the Bot
            logger.info("Starting bot with Updater API...")
            updater.start_polling()
            updater.idle()
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
