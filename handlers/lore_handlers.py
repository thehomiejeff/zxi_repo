#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lore command handlers for ZXI Bot
Handles lore browsing, searching, and discovery
"""

import logging
import json
import random
from typing import Dict, List, Any, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.callback_utils import create_callback_data, parse_callback_data
from utils.error_handler import error_handler
from utils.ui_utils import create_styled_button, create_menu_keyboard, create_paginated_keyboard

# Set up logging
logger = logging.getLogger(__name__)

# Helper functions for callback data creation
def create_lore_category_callback(category: str) -> str:
    """Create callback data for a lore category."""
    return create_callback_data("lore_category", {"name": category})

def create_lore_entry_callback(entry_name: str) -> str:
    """Create callback data for a lore entry."""
    return create_callback_data("lore_entry", {"name": entry_name})

class LoreCommandHandlers:
    """Handlers for lore-related commands."""
    
    def __init__(self, db, lore_manager):
        """Initialize the lore command handlers.
        
        Args:
            db: Database instance
            lore_manager: FangenLoreManager instance
        """
        self.db = db
        self.lore_manager = lore_manager
    
    @error_handler(error_type="command", custom_message="I couldn't access the lore. Please try again.")
    async def lore_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /lore command to browse lore categories.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        if not update or not update.message:
            logger.error("Update or message is None in lore_command")
            return
            
        # Get lore categories
        try:
            categories = self.lore_manager.get_categories()
            
            if not categories:
                await update.message.reply_text("No lore categories found.")
                return
            
            # Create buttons for categories
            category_items = []
            for category in categories:
                callback_data = create_lore_category_callback(category)
                category_items.append((category.capitalize(), callback_data, "primary"))
            
            # Create keyboard with optimized layout
            keyboard = create_menu_keyboard(category_items)
            
            # Send message with category menu
            await update.message.reply_text(
                "📚 *Explore the Lore of Fangen* 📚\n\n"
                "Select a category to browse:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error getting lore categories: {e}")
            await update.message.reply_text("I encountered an error accessing the lore. Please try again.")
    
    @error_handler(error_type="command", custom_message="I couldn't search the lore. Please try again.")
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /search command to search for lore entries.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        if not update or not update.message:
            logger.error("Update or message is None in search_command")
            return
            
        # Check if a search term was provided
        if context.args and len(context.args) > 0:
            # Join all arguments into a single search term
            search_term = " ".join(context.args).lower()
            
            # Perform search
            try:
                results = self.lore_manager.search_lore(search_term)
                
                # Check if any results were found
                total_results = sum(len(category_results) for category_results in results.values())
                
                if total_results == 0:
                    await update.message.reply_text(
                        f"No results found for '{search_term}'.\n\n"
                        "Try a different search term or browse the lore categories with /lore."
                    )
                    return
                
                # Create message with search results
                message_text = f"🔍 *Search Results for '{search_term}'* 🔍\n\n"
                
                # Create buttons for results
                result_items = []
                
                # Add results from each category
                for category, category_results in results.items():
                    if category_results:
                        for name, snippet in category_results:
                            callback_data = create_callback_data("lore_entry", {"name": name, "category": category})
                            result_items.append((f"{name} ({category.capitalize()})", callback_data, "secondary"))
                
                # Create paginated keyboard
                keyboard, total_pages, current_page = create_paginated_keyboard(
                    result_items,
                    page=0,
                    items_per_page=10,
                    show_pagination=True
                )
                
                # Add back button
                back_button = create_styled_button("« Back to Lore", create_callback_data("lore_back"), "back")
                keyboard.inline_keyboard.append([back_button])
                
                # Add result count to message
                message_text += f"Found {total_results} results across {len([c for c, r in results.items() if r])} categories.\n\n"
                message_text += "Select an entry to view details:"
                
                # Send message with results
                await update.message.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error searching lore: {e}")
                await update.message.reply_text("I encountered an error searching the lore. Please try again.")
        else:
            # No search term provided, show search menu
            await self.search_menu(update, context)
    
    @error_handler(error_type="command", custom_message="I couldn't discover new lore. Please try again.")
    async def discover_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /discover command to find random lore entries.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        if not update or not update.message or not update.effective_user:
            logger.error("Update, message, or effective_user is None in discover_command")
            return
            
        user_id = update.effective_user.id
        
        try:
            # Get a random lore entry
            category, name, content = self.lore_manager.get_random_lore()
            
            if not name:
                await update.message.reply_text("No lore entries available for discovery.")
                return
            
            # Record discovery in database
            try:
                # Check if already discovered
                discovered = self.db.execute_query(
                    "SELECT * FROM user_progress WHERE user_id = ? AND category = ? AND item_name = ?",
                    (user_id, category, name)
                )
                
                is_new_discovery = not discovered
                
                if is_new_discovery:
                    # Record new discovery
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.db.execute_query(
                        "INSERT INTO user_progress (user_id, category, item_name, discovered, discovery_date) "
                        "VALUES (?, ?, ?, TRUE, ?)",
                        (user_id, category, name, current_time)
                    )
                
                # Create message
                message_text = f"📜 *{name}* 📜\n\n{content}\n\n"
                message_text += f"*Category:* {category.capitalize()}"
                
                if is_new_discovery:
                    message_text += "\n\n✨ *New Discovery!* ✨\nThis entry has been added to your collection."
                
                # Create keyboard
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔄 Discover More", callback_data=create_callback_data("lore_discover")),
                        InlineKeyboardButton("📚 View Collection", callback_data=create_callback_data("lore_collection"))
                    ],
                    [
                        InlineKeyboardButton("« Back to Lore", callback_data=create_callback_data("lore_back"))
                    ]
                ])
                
                # Send message
                await update.message.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            except Exception as db_error:
                logger.error(f"Database error in discover_command: {db_error}")
                
                # Send message without recording discovery
                message_text = f"📜 *{name}* 📜\n\n{content}\n\n"
                message_text += f"*Category:* {category.capitalize()}"
                
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔄 Discover More", callback_data=create_callback_data("lore_discover")),
                        InlineKeyboardButton("« Back to Lore", callback_data=create_callback_data("lore_back"))
                    ]
                ])
                
                await update.message.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error discovering lore: {e}")
            await update.message.reply_text("I encountered an error discovering lore. Please try again.")
    
    @error_handler(error_type="command", custom_message="I couldn't access your lore collection. Please try again.")
    async def collection_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /collection command to view discovered lore."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in collection_command")
            return
            
        user_id = update.effective_user.id
        
        # Get discovered lore entries
        try:
            discovered = self.db.execute_query(
                "SELECT category, item_name FROM user_progress "
                "WHERE user_id = ? AND discovered = TRUE "
                "ORDER BY category, item_name",
                (user_id,)
            )
        except Exception as e:
            logger.error(f"Database error in collection_command: {e}")
            discovered = []
        
        if not discovered:
            await update.message.reply_text(
                "You haven't discovered any lore entries yet.\n\n"
                "Use /discover to find random lore entries, or /lore to browse categories."
            )
            return
        
        # Group by category
        categories = {}
        for row in discovered:
            category, item_name = row
            if category not in categories:
                categories[category] = []
            categories[category].append(item_name)
        
        # Create menu items for categories
        menu_items = []
        for category, entries in categories.items():
            callback_data = create_callback_data("collection_cat", name=category)
            menu_items.append((f"{category.capitalize()} ({len(entries)})", callback_data, "secondary"))
        
        # Create keyboard with optimized layout
        keyboard = create_menu_keyboard(menu_items)
        
        # Add back button
        back_button = create_styled_button("« Back to Lore", create_callback_data("lore_back"), "back")
        keyboard.inline_keyboard.append([back_button])
        
        await update.message.reply_text(
            "📚 *Your Lore Collection* 📚\n\n"
            f"You have discovered {len(discovered)} lore entries across {len(categories)} categories.\n\n"
            "Select a category to view your discoveries:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @error_handler(error_type="callback", custom_message="I couldn't process that button press. Please try again.")
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: Dict[str, Any]) -> None:
        """Handle callback queries for lore-related features.
        
        Args:
            update: The update containing the callback query
            context: The context object for the bot
            callback_data: The parsed callback data
        """
        if not update or not update.callback_query or not update.effective_user:
            logger.error("Update, callback_query, or effective_user is None in handle_callback")
            return
            
        query = update.callback_query
        
        # Get the action
        action = callback_data.get("action", "")
        
        # Answer callback query with appropriate message
        if action == "lore_back":
            await query.answer("Returning to lore menu")
            # Create a fake update to reuse the lore_command
            await self.lore_command(update, context)
        elif action == "lore_category":
            await query.answer("Loading category")
            await self._handle_category_callback(update, context, callback_data)
        elif action == "lore_entry":
            await query.answer("Loading entry")
            await self._handle_entry_callback(update, context, callback_data)
        elif action == "lore_discover":
            await query.answer("Finding random lore")
            # Create a fake update to reuse the discover_command
            await self.discover_command(update, context)
        elif action == "lore_collection":
            await query.answer("Loading your collection")
            # Create a fake update to reuse the collection_command
            await self.collection_command(update, context)
        elif action == "collection_cat":
            await query.answer("Loading category")
            await self._handle_collection_category_callback(update, context, callback_data)
        else:
            await query.answer("Unknown action")
            logger.warning(f"Unknown lore callback action: {action}")
    
    @error_handler(error_type="callback", custom_message="I couldn't open the search menu. Please try again.")
    async def search_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display the search menu for lore entries.
        
        Args:
            update: The update containing the command or callback query
            context: The context object for the bot
        """
        # Determine if this is from a command or callback
        if update.callback_query:
            message_func = update.callback_query.edit_message_text
            await update.callback_query.answer("Opening search menu")
        elif update.message:
            message_func = update.message.reply_text
        else:
            logger.error("Neither callback_query nor message in search_menu")
            return
        
        # Create search instructions
        message_text = (
            "🔍 *Search the Lore of Fangen* 🔍\n\n"
            "To search for lore entries, use the /search command followed by your search terms.\n\n"
            "For example:\n"
            "• /search ancient magic\n"
            "• /search dragons\n"
            "• /search elemental powers\n\n"
            "You can also browse categories or discover random lore entries."
        )
        
        # Create keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📚 Browse Categories", callback_data=create_callback_data("lore_back")),
                InlineKeyboardButton("🎲 Random Discovery", callback_data=create_callback_data("lore_discover"))
            ],
            [
                InlineKeyboardButton("📋 View Collection", callback_data=create_callback_data("lore_collection")),
                InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
            ]
        ])
        
        # Send or edit message
        await message_func(
            message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # If this is from a message, update user state
        if update.message and update.effective_user and self.db:
            try:
                user_id = update.effective_user.id
                self.db.update_user_state(user_id, "search_active", True)
            except Exception as e:
                logger.error(f"Error updating user state in search_menu: {e}")
    
    # Helper methods for handling specific callbacks
    # For brevity, I'm not including all of them in this example
    async def _handle_category_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: Dict[str, Any]) -> None:
        """Handle callback for selecting a lore category."""
        if not update or not update.callback_query:
            logger.error("Update or callback_query is None in _handle_category_callback")
            return
            
        query = update.callback_query
        category = callback_data.get("name", "")
        
        if not category:
            await query.edit_message_text("Invalid category selection.")
            return
        
        try:
            # Get entries for the selected category
            entries = self.lore_manager.get_entries_by_category(category)
            
            if not entries:
                await query.edit_message_text(
                    f"No entries found in the {category} category.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back to Lore", callback_data='{"action":"lore_back"}')
                    ]])
                )
                return
            
            # Create buttons for entries
            entry_items = []
            for entry in entries:
                callback_data = create_lore_entry_callback(entry)
                entry_items.append((entry, callback_data, "secondary"))
            
            # Create paginated keyboard
            keyboard, total_pages, current_page = create_paginated_keyboard(
                entry_items,
                page=0,
                items_per_page=10,
                show_pagination=True
            )
            
            # Add back button
            back_button = create_styled_button("« Back to Lore", create_callback_data("lore_back"), "back")
            keyboard.inline_keyboard.append([back_button])
            
            # Send message
            await query.edit_message_text(
                f"📚 *{category.capitalize()} Lore* 📚\n\n"
                f"Select an entry to learn more:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error in _handle_category_callback: {e}")
            await query.edit_message_text(
                f"I encountered an error loading the {category} category. Please try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to Lore", callback_data='{"action":"lore_back"}')
                ]])
            )
            