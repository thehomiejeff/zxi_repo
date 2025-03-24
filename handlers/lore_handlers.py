#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command handlers for lore-related features
"""

import logging
import random
import json
from typing import Dict, List, Any, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.logger import get_logger
from utils.fangen_lore_manager import FangenLoreManager
from utils.database import Database
from utils.callback_utils import (
    create_callback_data, 
    parse_callback_data, 
    validate_callback_data,
    lore_reference_manager,
    create_lore_category_callback,
    create_lore_entry_callback,
    create_navigation_callback
)
from utils.error_handler import error_handler, ErrorContext
from utils.ui_utils import (
    create_styled_button,
    optimize_button_layout,
    create_paginated_keyboard,
    create_menu_keyboard
)
from config import BOT_NAME, MAX_SEARCH_RESULTS

logger = get_logger(__name__)

class LoreCommandHandlers:
    """Command handlers for lore-related features."""
    
    def __init__(self, lore_manager: FangenLoreManager, db: Database):
        """Initialize lore command handlers."""
        self.lore_manager = lore_manager
        self.db = db
    
    @error_handler(error_type="general", custom_message="I couldn't access the lore categories. Please try again.")
    async def lore_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /lore command to browse lore by category."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in lore_command")
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
            logger.error(f"Database error in lore_command: {e}")
        
        # Get available categories
        try:
            categories = self.lore_manager.get_categories()
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            categories = []
        
        # Create menu items for categories
        menu_items = []
        for category in categories:
            callback_data = create_lore_category_callback(category)
            menu_items.append((category.capitalize(), callback_data, "secondary"))
        
        # Add search button
        search_callback = create_callback_data("lore_search")
        menu_items.append(("🔍 Search", search_callback, "primary"))
        
        # Create keyboard with optimized layout
        keyboard = create_menu_keyboard(menu_items)
        
        await update.message.reply_text(
            "📚 *Explore the Lore of Fangen* 📚\n\n"
            "What aspect of this mystical world would you like to discover?",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @error_handler(error_type="general", custom_message="I couldn't perform that search. Please try again.")
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /search command to find specific lore entries."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in search_command")
            return
            
        user_id = update.effective_user.id
        query = ' '.join(context.args) if context.args else None
        
        if not query:
            await update.message.reply_text(
                "Please provide a search term after the command.\n"
                "Example: `/search Diamond`",
                parse_mode='Markdown'
            )
            return
        
        # Perform search
        try:
            results = self.lore_manager.search_lore(query)
        except Exception as e:
            logger.error(f"Error searching lore: {e}")
            results = {}
        
        if not results:
            await update.message.reply_text(
                f"No lore entries found for '{query}'.\n\n"
                f"Try a different search term or browse categories with /lore"
            )
            return
        
        await self._display_search_results(update, query, results)
    
    async def _display_search_results(
        self, 
        update: Update, 
        query: str, 
        results: Dict[str, List[str]], 
        page: int = 0
    ) -> None:
        """Display search results with pagination."""
        if not update:
            logger.error("Update is None in _display_search_results")
            return
            
        # Flatten results for pagination
        flat_results = []
        for category, entries in results.items():
            for entry in entries:
                flat_results.append({
                    "id": lore_reference_manager.get_id(entry),
                    "name": entry,
                    "category": category
                })
        
        # Create paginated keyboard
        max_results = 10  # Default if MAX_SEARCH_RESULTS is not properly defined
        if hasattr(MAX_SEARCH_RESULTS, '__int__'):
            try:
                max_results = int(MAX_SEARCH_RESULTS)
            except (ValueError, TypeError):
                logger.warning(f"Invalid MAX_SEARCH_RESULTS value: {MAX_SEARCH_RESULTS}, using default")
        
        try:
            keyboard, total_pages, current_page = create_paginated_keyboard(
                flat_results,
                page=page,
                items_per_page=max_results,
                callback_prefix="lore_entry",
                show_pagination=True
            )
        except Exception as e:
            logger.error(f"Error creating paginated keyboard: {e}")
            # Create a simple keyboard as fallback
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("« Back to Lore", callback_data='{"action":"lore_back"}')]
            ])
            total_pages = 1
            current_page = 0
        
        # Add back button if not already added
        if not any("lore_back" in str(button.callback_data) for row in keyboard.inline_keyboard for button in row):
            back_button = create_styled_button("« Back to Lore", create_callback_data("lore_back"), "back")
            keyboard.inline_keyboard.append([back_button])
        
        # Send or edit message
        message_text = (
            f"🔍 *Search Results for '{query}'* 🔍\n\n"
            f"Found {len(flat_results)} entries across {len(results)} categories."
        )
        
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            elif update.message:
                await update.message.reply_text(
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error sending search results: {e}")
            # Try to send a simple message as fallback
            if update.effective_chat:
                try:
                    await update.effective_chat.send_message(
                        text=f"Found {len(flat_results)} results for '{query}'. Please try viewing them again.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("Try Again", callback_data='{"action":"lore_search"}')
                        ]])
                    )
                except Exception as inner_e:
                    logger.error(f"Failed to send fallback message: {inner_e}")
    
    @error_handler(error_type="general", custom_message="I couldn't process that discovery. Please try again.")
    async def discover_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /discover command to find random lore entries."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in discover_command")
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
            logger.error(f"Database error in discover_command: {e}")
        
        # Get a random entry from the lore
        try:
            categories = self.lore_manager.get_categories()
            if not categories:
                await update.message.reply_text("No lore categories available.")
                return
            
            # Select random category and entry
            category = random.choice(categories)
            entries = self.lore_manager.get_entries_by_category(category)
            if not entries:
                await update.message.reply_text(f"No entries found in the {category} category.")
                return
            
            entry_name = random.choice(entries)
            entry_content = self.lore_manager.get_entry_content(entry_name)
            
            if not entry_content:
                await update.message.reply_text(f"Could not find content for {entry_name}.")
                return
        except Exception as e:
            logger.error(f"Error discovering lore: {e}")
            await update.message.reply_text("I encountered an issue while discovering lore. Please try again.")
            return
        
        # Mark as discovered
        try:
            async with ErrorContext(update, context, "database"):
                self.db.execute_query(
                    "INSERT OR IGNORE INTO user_progress (user_id, category, item_name, discovered, discovery_date) "
                    "VALUES (?, ?, ?, TRUE, CURRENT_TIMESTAMP)",
                    (user_id, category, entry_name)
                )
        except Exception as e:
            logger.error(f"Database error marking discovery: {e}")
        
        # Format content
        try:
            if isinstance(entry_content, dict):
                formatted_content = ""
                for key, value in entry_content.items():
                    if key not in ["name", "title", "rarity"] and value:
                        formatted_content += f"*{key.capitalize()}*: {value}\n\n"
            else:
                formatted_content = entry_content
        except Exception as e:
            logger.error(f"Error formatting content: {e}")
            formatted_content = "Error formatting content. Please try again."
        
        # Create keyboard
        keyboard = [
            [create_styled_button(
                "View Details", 
                create_lore_entry_callback(entry_name), 
                "primary"
            )],
            [create_styled_button(
                "Discover More", 
                create_callback_data("discover_more"), 
                "secondary"
            )],
            [create_styled_button(
                "« Back to Lore", 
                create_callback_data("lore_back"), 
                "back"
            )]
        ]
        
        # Send message
        message = (
            f"✨ *You discovered: {entry_name}* ✨\n\n"
            f"*Category*: {category.capitalize()}\n\n"
            f"{formatted_content}"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @error_handler(error_type="callback", custom_message="I couldn't process that button press. Please try again.")
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries for lore-related features."""
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
            "lore_cat": "Loading category...",
            "lore_entry": "Loading entry...",
            "lore_search": "Opening search...",
            "lore_back": "Going back...",
            "search_cat": "Loading category results...",
            "search_more": "Loading more results...",
            "discover_more": "Discovering more...",
            "collection_cat": "Loading collection category...",
            "page": "Changing page..."
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
            if action == "lore_cat":
                await self._handle_category_callback(update, context, callback_data)
            elif action == "lore_entry":
                await self._handle_entry_callback(update, context, callback_data)
            elif action == "lore_search":
                await self._handle_search_callback(update, context)
            elif action == "lore_back":
                await self._handle_back_callback(update, context)
            elif action == "search_cat":
                await self._handle_search_category_callback(update, context, callback_data)
            elif action == "search_more":
                await self._handle_search_more_callback(update, context, callback_data)
            elif action == "discover_more":
                await self._handle_discover_more_callback(update, context)
            elif action == "collection_cat":
                await self._handle_collection_category_callback(update, context, callback_data)
            elif action == "page":
                await self._handle_page_callback(update, context, callback_data)
            else:
                logger.warning(f"Unknown lore callback action: {action}")
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
