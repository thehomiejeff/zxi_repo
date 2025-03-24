#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command handlers for ChuzoBot's Quest System
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.logger import get_logger
from utils.fangen_lore_manager import FangenLoreManager
from utils.database import Database
from utils.quest_manager import QuestManager
from utils.callback_utils import (
    create_callback_data, 
    parse_callback_data, 
    validate_callback_data,
    quest_reference_manager,
    create_quest_view_callback,
    create_quest_start_callback,
    create_quest_choice_callback
)
from utils.error_handler import error_handler, ErrorContext
from utils.ui_utils import (
    create_styled_button,
    optimize_button_layout,
    create_paginated_keyboard,
    create_menu_keyboard
)
from config import BOT_NAME

logger = get_logger(__name__)

class QuestCommandHandlers:
    """Command handlers for quest-related features."""
    
    def __init__(self, quest_manager: QuestManager, lore_manager: FangenLoreManager, db: Database):
        """Initialize quest command handlers."""
        self.quest_manager = quest_manager
        self.lore_manager = lore_manager
        self.db = db
    
    @error_handler(error_type="general", custom_message="I couldn't access the quests. Please try again.")
    async def quests_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /quests command to browse available quests."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in quests_command")
            return
            
        user_id = update.effective_user.id
        
        # Log user action
        try:
            async with ErrorContext(update, context, "database"):
                self.db.execute_query(
                    "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (user_id,)
                )
        except Exception as e:
            logger.error(f"Database error in quests_command: {e}")
        
        # Get available quests
        try:
            available_quests = self.quest_manager.get_available_quests(user_id)
        except Exception as e:
            logger.error(f"Error getting available quests: {e}")
            available_quests = []
        
        if not available_quests:
            await update.message.reply_text(
                "No quests are currently available to you.\n\n"
                "Check back later or explore the world to unlock new quests.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Main Menu", callback_data='{"action":"main_menu"}')
                ]])
            )
            return
        
        # Create menu items for quests
        menu_items = []
        for quest in available_quests:
            quest_id = quest.get("quest_id")
            quest_name = quest.get("title", "Unnamed Quest")
            callback_data = create_quest_view_callback(quest_name, quest_id)
            menu_items.append((quest_name, callback_data, "secondary"))
        
        # Create keyboard with optimized layout
        keyboard = create_menu_keyboard(menu_items)
        
        # Add active quests button
        active_button = create_styled_button(
            "View Active Quests", 
            create_callback_data("active_quests"), 
            "primary"
        )
        keyboard.inline_keyboard.append([active_button])
        
        # Add main menu button
        menu_button = create_styled_button(
            "🏠 Main Menu", 
            create_callback_data("main_menu"), 
            "back"
        )
        keyboard.inline_keyboard.append([menu_button])
        
        await update.message.reply_text(
            "📜 *Available Quests* 📜\n\n"
            "Select a quest to view details:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @error_handler(error_type="general", custom_message="I couldn't access that quest. Please try again.")
    async def quest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /quest command to view a specific quest."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in quest_command")
            return
            
        user_id = update.effective_user.id
        quest_name = ' '.join(context.args) if context.args else None
        
        if not quest_name:
            await update.message.reply_text(
                "Please provide a quest name after the command.\n"
                "Example: `/quest The Lost Artifact`",
                parse_mode='Markdown'
            )
            return
        
        # Find quest by name
        try:
            quest = self.quest_manager.find_quest_by_name(quest_name)
        except Exception as e:
            logger.error(f"Error finding quest: {e}")
            quest = None
        
        if not quest:
            await update.message.reply_text(
                f"No quest found with the name '{quest_name}'.\n\n"
                f"Use /quests to see available quests."
            )
            return
        
        # Display quest details
        await self._display_quest_details(update, context, quest)
    
    async def _display_quest_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quest: Dict[str, Any]) -> None:
        """Display quest details with buttons to start or view active quest."""
        if not update or not update.effective_user:
            logger.error("Update or effective_user is None in _display_quest_details")
            return
            
        user_id = update.effective_user.id
        quest_id = quest.get("quest_id")
        quest_name = quest.get("title", "Unnamed Quest")
        
        # Check if user has this quest active
        try:
            active_quest = self.quest_manager.get_active_quest(user_id, quest_id)
        except Exception as e:
            logger.error(f"Error checking active quest: {e}")
            active_quest = None
        
        # Format quest details
        description = quest.get("description", "No description available.")
        difficulty = quest.get("difficulty", "Unknown")
        rewards = quest.get("rewards", [])
        
        rewards_text = ""
        if rewards:
            rewards_text = "\n\n*Rewards:*\n"
            for reward in rewards:
                rewards_text += f"• {reward.get('name', 'Unknown')} x{reward.get('quantity', 1)}\n"
        
        message = (
            f"📜 *{quest_name}* 📜\n\n"
            f"*Difficulty:* {difficulty}\n\n"
            f"{description}"
            f"{rewards_text}"
        )
        
        # Create buttons
        keyboard = []
        
        if active_quest:
            # Quest is active, add continue button
            keyboard.append([
                create_styled_button(
                    "Continue Quest", 
                    create_callback_data("quest_continue", id=quest_id), 
                    "primary"
                )
            ])
            
            # Add abandon button
            keyboard.append([
                create_styled_button(
                    "Abandon Quest", 
                    create_callback_data("quest_abandon", id=quest_id), 
                    "danger"
                )
            ])
        else:
            # Quest is not active, add start button
            keyboard.append([
                create_styled_button(
                    "Start Quest", 
                    create_quest_start_callback(quest_name, quest_id), 
                    "primary"
                )
            ])
        
        # Add back button
        keyboard.append([
            create_styled_button(
                "« Back to Quests", 
                create_callback_data("quests_back"), 
                "back"
            )
        ])
        
        # Send or edit message
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            elif update.message:
                await update.message.reply_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error sending quest details: {e}")
            # Try to send a simple message as fallback
            if update.effective_chat:
                try:
                    await update.effective_chat.send_message(
                        text=f"Error displaying quest details for '{quest_name}'. Please try again.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔄 Try Again", callback_data='{"action":"retry"}'),
                            InlineKeyboardButton("🏠 Main Menu", callback_data='{"action":"main_menu"}')
                        ]])
                    )
                except Exception as inner_e:
                    logger.error(f"Failed to send fallback message: {inner_e}")
    
    @error_handler(error_type="callback", custom_message="I couldn't process that button press. Please try again.")
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries for quest-related features."""
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
        
        # Answer callback query with appropriate message
        feedback_messages = {
            "quest_view": "Loading quest details...",
            "quest_start": "Starting quest...",
            "quest_choice": "Processing your choice...",
            "quest_abandon": "Abandoning quest...",
            "quest_continue": "Continuing quest...",
            "craft_check": "Checking recipe...",
            "craft_confirm": "Crafting item...",
            "inventory_details": "Loading item details...",
            "inventory_craft": "Opening crafting menu...",
            "inventory_back": "Going back...",
            "interact_char": "Interacting with character...",
            "interact_topic": "Discussing topic...",
            "quests_back": "Going back to quests...",
            "active_quests": "Loading active quests...",
            "characters_menu": "Loading characters...",
            "inventory_menu": "Loading inventory...",
            "quests_menu": "Loading quests..."
        }
        
        try:
            await query.answer(feedback_messages.get(action, "Processing..."))
        except Exception as e:
            logger.warning(f"Failed to answer callback query: {e}")
        
        # Get user ID
        user_id = update.effective_user.id
        
        # Store the current action in user_data for retry functionality
        if context and context.user_data is not None:
            context.user_data["last_action"] = query.data
        
        # Handle different callback types
        try:
            if action == "quest_view":
                await self._handle_quest_view_callback(update, context, callback_data)
            elif action == "quest_start":
                await self._handle_quest_start_callback(update, context, callback_data)
            elif action == "quest_choice":
                await self._handle_quest_choice_callback(update, context, callback_data)
            elif action == "quest_abandon":
                await self._handle_quest_abandon_callback(update, context, callback_data)
            elif action == "quest_continue":
                await self._handle_quest_continue_callback(update, context, callback_data)
            elif action == "craft_check":
                await self._handle_craft_check_callback(update, context, callback_data)
            elif action == "craft_confirm":
                await self._handle_craft_confirm_callback(update, context, callback_data)
            elif action == "inventory_details":
                await self._handle_inventory_details_callback(update, context, callback_data)
            elif action == "inventory_craft":
                await self._handle_inventory_craft_callback(update, context, callback_data)
            elif action == "inventory_back":
                await self._handle_inventory_back_callback(update, context)
            elif action == "interact_char":
                await self._handle_interact_char_callback(update, context, callback_data)
            elif action == "interact_topic":
                await self._handle_interact_topic_callback(update, context, callback_data)
            elif action == "quests_back":
                await self._handle_quests_back_callback(update, context)
            elif action == "active_quests":
                await self._handle_active_quests_callback(update, context)
            elif action == "characters_menu":
                await self._handle_characters_menu_callback(update, context)
            elif action == "inventory_menu":
                await self._handle_inventory_menu_callback(update, context)
            elif action == "quests_menu":
                await self._handle_quests_menu_callback(update, context)
            else:
                logger.warning(f"Unknown quest callback action: {action}")
                await query.edit_message_text(
                    "I'm not sure how to handle that request.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Main Menu", callback_data='{"action":"main_menu"}')
                    ]])
                )
        except Exception as e:
            logger.error(f"Error handling callback {action}: {e}")
            # Try to provide a graceful fallback
            try:
                await query.edit_message_text(
                    "Sorry, I encountered an error processing your request.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔄 Try Again", callback_data='{"action":"retry"}'),
                        InlineKeyboardButton("🏠 Main Menu", callback_data='{"action":"main_menu"}')
                    ]])
                )
            except Exception as inner_e:
                logger.error(f"Failed to send error message: {inner_e}")
    
    # Helper methods for handling specific callback types
    # These methods would be implemented here...
    # For brevity, I'm not including all of them in this example

    async def _handle_quest_view_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: Dict[str, Any]) -> None:
        """Handle callback for viewing quest details."""
        if not update or not update.callback_query or not update.effective_user:
            logger.error("Update, callback_query, or effective_user is None in _handle_quest_view_callback")
            return
            
        query = update.callback_query
        
        # Get quest ID or name
        quest_id = callback_data.get("id")
        quest_name = callback_data.get("name")
        
        if not quest_id and not quest_name:
            await query.edit_message_text("Invalid quest selection.")
            return
        
        try:
            # Find quest by ID or name
            if quest_id:
                quest = self.quest_manager.get_quest_by_id(quest_id)
            else:
                quest = self.quest_manager.find_quest_by_name(quest_name)
            
            if not quest:
                await query.edit_message_text(
                    f"Quest not found.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quests_back"}')
                    ]])
                )
                return
            
            # Display quest details
            await self._display_quest_details(update, context, quest)
        except Exception as e:
            logger.error(f"Error in _handle_quest_view_callback: {e}")
            await query.edit_message_text(
                f"I encountered an error loading the quest details. Please try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quests_back"}')
                ]])
            )

    async def active_quests_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /active command to view active quests."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in active_quests_command")
            return
            
        user_id = update.effective_user.id
        
        # Get active quests
        try:
            active_quests = self.quest_manager.get_active_quests(user_id)
        except Exception as e:
            logger.error(f"Error getting active quests: {e}")
            active_quests = []
        
        if not active_quests:
            await update.message.reply_text(
                "You don't have any active quests.\n\n"
                "Use /quests to browse available quests.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Browse Quests", callback_data='{"action":"quests_menu"}')
                ]])
            )
            return
        
        # Create menu items for quests
        menu_items = []
        for quest in active_quests:
            quest_id = quest.get("quest_id")
            quest_name = quest.get("title", "Unnamed Quest")
            callback_data = create_callback_data("quest_continue", id=quest_id)
            menu_items.append((quest_name, callback_data, "secondary"))
        
        # Create keyboard with optimized layout
        keyboard = create_menu_keyboard(menu_items)
        
        # Add browse quests button
        browse_button = create_styled_button(
            "Browse Available Quests", 
            create_callback_data("quests_menu"), 
            "primary"
        )
        keyboard.inline_keyboard.append([browse_button])
        
        # Add main menu button
        menu_button = create_styled_button(
            "🏠 Main Menu", 
            create_callback_data("main_menu"), 
            "back"
        )
        keyboard.inline_keyboard.append([menu_button])
        
        await update.message.reply_text(
            "📜 *Your Active Quests* 📜\n\n"
            f"You have {len(active_quests)} active quest(s).\n\n"
            "Select a quest to continue:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def inventory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /inventory command to view inventory."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in inventory_command")
            return
            
        user_id = update.effective_user.id
        
        # Get inventory items
        try:
            inventory = self.quest_manager.get_inventory(user_id)
        except Exception as e:
            logger.error(f"Error getting inventory: {e}")
            inventory = []
        
        if not inventory:
            await update.message.reply_text(
                "Your inventory is empty.\n\n"
                "Complete quests to earn items.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Browse Quests", callback_data='{"action":"quests_menu"}')
                ]])
            )
            return
        
        # Create menu items for items
        menu_items = []
        for item in inventory:
            item_name = item.get("item_name", "Unknown Item")
            quantity = item.get("quantity", 1)
            display_name = f"{item_name} (x{quantity})"
            callback_data = create_callback_data("inventory_details", name=item_name)
            menu_items.append((display_name, callback_data, "secondary"))
        
        # Create keyboard with optimized layout
        keyboard = create_menu_keyboard(menu_items)
        
        # Add craft button
        craft_button = create_styled_button(
            "Craft Items", 
            create_callback_data("inventory_craft"), 
            "primary"
        )
        keyboard.inline_keyboard.append([craft_button])
        
        # Add main menu button
        menu_button = create_styled_button(
            "🏠 Main Menu", 
            create_callback_data("main_menu"), 
            "back"
        )
        keyboard.inline_keyboard.append([menu_button])
        
        await update.message.reply_text(
            "🎒 *Your Inventory* 🎒\n\n"
            f"You have {len(inventory)} different item(s) in your inventory.\n\n"
            "Select an item to view details:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def craft_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /craft command to craft items."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in craft_command")
            return
            
        user_id = update.effective_user.id
        
        # Get available recipes
        try:
            recipes = self.quest_manager.get_available_recipes(user_id)
        except Exception as e:
            logger.error(f"Error getting recipes: {e}")
            recipes = []
        
        if not recipes:
            await update.message.reply_text(
                "You don't have any available recipes.\n\n"
                "Discover recipes by completing quests and exploring the world.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("View Inventory", callback_data='{"action":"inventory_menu"}')
                ]])
            )
            return
        
        # Create menu items for recipes
        menu_items = []
        for recipe in recipes:
            recipe_name = recipe.get("name", "Unknown Recipe")
            callback_data = create_callback_data("craft_check", name=recipe_name)
            menu_items.append((recipe_name, callback_data, "secondary"))
        
        # Create keyboard with optimized layout
        keyboard = create_menu_keyboard(menu_items)
        
        # Add inventory button
        inventory_button = create_styled_button(
            "View Inventory", 
            create_callback_data("inventory_menu"), 
            "primary"
        )
        keyboard.inline_keyboard.append([inventory_button])
        
        # Add main menu button
        menu_button = create_styled_button(
            "🏠 Main Menu", 
            create_callback_data("main_menu"), 
            "back"
        )
        keyboard.inline_keyboard.append([menu_button])
        
        await update.message.reply_text(
            "⚒️ *Crafting* ⚒️\n\n"
            f"You have {len(recipes)} available recipe(s).\n\n"
            "Select a recipe to craft:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def characters_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /characters command to view characters."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in characters_command")
            return
            
        user_id = update.effective_user.id
        
        # Get available characters
        try:
            characters = self.quest_manager.get_available_characters(user_id)
        except Exception as e:
            logger.error(f"Error getting characters: {e}")
            characters = []
        
        if not characters:
            await update.message.reply_text(
                "No characters are currently available to interact with.\n\n"
                "Progress through quests to meet characters.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Browse Quests", callback_data='{"action":"quests_menu"}')
                ]])
            )
            return
        
        # Create menu items for characters
        menu_items = []
        for character in characters:
            character_name = character.get("name", "Unknown Character")
            callback_data = create_callback_data("interact_char", name=character_name)
            menu_items.append((character_name, callback_data, "secondary"))
        
        # Create keyboard with optimized layout
        keyboard = create_menu_keyboard(menu_items)
        
        # Add main menu button
        menu_button = create_styled_button(
            "🏠 Main Menu", 
            create_callback_data("main_menu"), 
            "back"
        )
        keyboard.inline_keyboard.append([menu_button])
        
        await update.message.reply_text(
            "👥 *Characters* 👥\n\n"
            f"There are {len(characters)} character(s) available to interact with.\n\n"
            "Select a character to interact with:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def interact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /interact command to interact with a character."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in interact_command")
            return
            
        user_id = update.effective_user.id
        character_name = ' '.join(context.args) if context.args else None
        
        if not character_name:
            await update.message.reply_text(
                "Please provide a character name after the command.\n"
                "Example: `/interact Eldrin`",
                parse_mode='Markdown'
            )
            return
        
        # Find character by name
        try:
            character = self.quest_manager.find_character_by_name(character_name)
        except Exception as e:
            logger.error(f"Error finding character: {e}")
            character = None
        
        if not character:
            await update.message.reply_text(
                f"No character found with the name '{character_name}'.\n\n"
                f"Use /characters to see available characters."
            )
            return
        
        # Display character interaction
        await self._display_character_interaction(update, context, character)
    
    async def _display_character_interaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE, character: Dict[str, Any]) -> None:
        """Display character interaction options."""
        if not update or not update.effective_user:
            logger.error("Update or effective_user is None in _display_character_interaction")
            return
            
        user_id = update.effective_user.id
        character_name = character.get("name", "Unknown Character")
        
        # Get relationship level
        try:
            relationship = self.quest_manager.get_character_relationship(user_id, character_name)
            relationship_level = relationship.get("level", 0)
            relationship_name = self.quest_manager.get_relationship_level_name(relationship_level)
        except Exception as e:
            logger.error(f"Error getting relationship: {e}")
            relationship_level = 0
            relationship_name = "Stranger"
        
        # Get interaction topics
        try:
            topics = self.quest_manager.get_interaction_topics(user_id, character_name)
        except Exception as e:
            logger.error(f"Error getting topics: {e}")
            topics = []
        
        # Format character details
        description = character.get("description", "No description available.")
        
        message = (
            f"👤 *{character_name}* 👤\n\n"
            f"*Relationship:* {relationship_name} ({relationship_level}/100)\n\n"
            f"{description}\n\n"
            f"What would you like to talk about?"
        )
        
        # Create buttons for topics
        keyboard = []
        for topic in topics:
            topic_id = topic.get("id")
            topic_name = topic.get("name", "Unknown Topic")
            keyboard.append([
                create_styled_button(
                    topic_name, 
                    create_callback_data("interact_topic", id=topic_id, char=character_name), 
                    "secondary"
                )
            ])
        
        # Add back button
        keyboard.append([
            create_styled_button(
                "« Back to Characters", 
                create_callback_data("characters_menu"), 
                "back"
            )
        ])
        
        # Send or edit message
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            elif update.message:
                await update.message.reply_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error sending character interaction: {e}")
            # Try to send a simple message as fallback
            if update.effective_chat:
                try:
                    await update.effective_chat.send_message(
                        text=f"Error displaying interaction with {character_name}. Please try again.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔄 Try Again", callback_data='{"action":"retry"}'),
                            InlineKeyboardButton("🏠 Main Menu", callback_data='{"action":"main_menu"}')
                        ]])
                    )
                except Exception as inner_e:
                    logger.error(f"Failed to send fallback message: {inner_e}")
