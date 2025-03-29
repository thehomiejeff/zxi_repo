#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Quest command handlers for ZXI Bot
Handles quest browsing, starting, and progression
"""

import logging
import json
import random
from typing import Dict, List, Any, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.callback_utils import (
    create_callback_data, 
    parse_callback_data, 
    validate_callback_data,
    create_quest_view_callback,
    create_quest_start_callback,
    create_quest_choice_callback
)
from utils.error_handler import error_handler
from utils.ui_utils import create_styled_button, create_menu_keyboard, create_paginated_keyboard
from utils.database import Database
from utils.quest_manager import QuestManager
from utils.fangen_lore_manager import FangenLoreManager

# Set up logging
logger = logging.getLogger(__name__)

class QuestCommandHandlers:
    """Handlers for quest-related commands."""
    
    def __init__(self, db: Database, quest_manager: QuestManager, lore_manager: FangenLoreManager):
        """Initialize the quest command handlers.
        
        Args:
            db: Database instance
            quest_manager: QuestManager instance
            lore_manager: FangenLoreManager instance
        """
        self.db = db
        self.quest_manager = quest_manager
        self.lore_manager = lore_manager
    
    @error_handler(error_type="command", custom_message="I couldn't retrieve the quests. Please try again.")
    async def quests_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /quests command to browse available quests.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        if not update or not update.message or not update.effective_user:
            logger.error("Update, message, or effective_user is None in quests_command")
            return
            
        user_id = update.effective_user.id
        
        # Get available quests
        try:
            available_quests = self.quest_manager.get_available_quests(user_id)
            
            if not available_quests:
                # No quests available
                message_text = (
                    "⚔️ *Available Quests* ⚔️\n\n"
                    "No quests are currently available to you.\n\n"
                    "Explore the world of Fangen to unlock new quests by:\n"
                    "• Discovering lore with /discover\n"
                    "• Interacting with characters using /interact\n"
                    "• Building your inventory with items"
                )
                
                # Create keyboard with alternative options
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📚 Explore Lore", callback_data=create_callback_data("lore_menu")),
                        InlineKeyboardButton("👥 Meet Characters", callback_data=create_callback_data("characters_menu"))
                    ],
                    [
                        InlineKeyboardButton("🔍 Discover", callback_data=create_callback_data("lore_discover")),
                        InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
                    ]
                ])
                
                await update.message.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                return
            
            # Create quest menu items
            quest_items = []
            for quest in available_quests:
                quest_id = quest.get("id", "")
                title = quest.get("title", "Unknown Quest")
                difficulty = quest.get("difficulty", "Normal")
                
                # Create callback data for viewing quest details
                callback_data = create_quest_view_callback(quest_id)
                
                # Determine button style based on difficulty
                style = "primary"
                if difficulty.lower() == "easy":
                    style = "secondary"
                elif difficulty.lower() == "hard":
                    style = "danger"
                
                quest_items.append((f"{title} ({difficulty})", callback_data, style))
            
            # Create keyboard with optimized layout
            keyboard = create_menu_keyboard(quest_items)
            
            # Add navigation buttons
            keyboard.inline_keyboard.append([
                InlineKeyboardButton("📚 Explore Lore", callback_data=create_callback_data("lore_menu")),
                InlineKeyboardButton("⬅️ Back to Main Menu", callback_data=create_callback_data("main_menu"))
            ])
            
            # Send message with quest menu
            await update.message.reply_text(
                "⚔️ *Available Quests* ⚔️\n\n"
                "Select a quest to view details:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error getting available quests: {e}")
            await update.message.reply_text("I encountered an error retrieving quests. Please try again.")
    
    @error_handler(error_type="command", custom_message="I couldn't start that quest. Please try again.")
    async def quest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /quest command to start or continue a specific quest.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        if not update or not update.message or not update.effective_user:
            logger.error("Update, message, or effective_user is None in quest_command")
            return
            
        # Check if a quest name was provided
        if context.args and len(context.args) > 0:
            # Join all arguments into a single quest name
            quest_name = " ".join(context.args).lower()
            
            # Find quest by name
            try:
                user_id = update.effective_user.id
                available_quests = self.quest_manager.get_available_quests(user_id)
                
                # Find quest with matching name
                quest_id = None
                for quest in available_quests:
                    if quest.get("title", "").lower() == quest_name:
                        quest_id = quest.get("id", "")
                        break
                
                if quest_id:
                    # Display quest details
                    await self._display_quest_details(update, context, quest_id)
                else:
                    await update.message.reply_text(
                        f"I couldn't find a quest named '{quest_name}'.\n\n"
                        "Use /quests to see available quests."
                    )
            except Exception as e:
                logger.error(f"Error finding quest by name: {e}")
                await update.message.reply_text("I encountered an error finding that quest. Please try again.")
        else:
            # No quest name provided, show active quests
            await self.active_quests_command(update, context)
    
    async def _display_quest_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quest_id: str) -> None:
        """Display details for a specific quest.
        
        Args:
            update: The update containing the command or callback query
            context: The context object for the bot
            quest_id: The ID of the quest to display
        """
        if not update or not update.effective_user:
            logger.error("Update or effective_user is None in _display_quest_details")
            return
            
        user_id = update.effective_user.id
        
        # Get quest details
        try:
            quest = self.quest_manager.get_quest_details(quest_id)
            
            if not quest:
                # Quest not found
                if update.callback_query:
                    await update.callback_query.answer("Error retrieving quest details. Please try again.")
                    return
                else:
                    await update.message.reply_text("Error retrieving quest details. Please try again.")
                    return
        except Exception as e:
            logger.error(f"Error getting quest details: {e}")
            
            if update.callback_query:
                await update.callback_query.answer("Quest not found. Please try another quest.")
                return
            else:
                await update.message.reply_text("Quest not found. Please try another quest.")
                return
        
        # Check if user is already on this quest
        active_quest = self.quest_manager.get_active_quest(user_id, quest_id)
        is_active = active_quest is not None
        
        # Create message text
        title = quest.get("title", "Unknown Quest")
        description = quest.get("description", "No description available.")
        difficulty = quest.get("difficulty", "Normal")
        rewards = quest.get("rewards", {})
        
        message_text = f"⚔️ *{title}* ⚔️\n\n{description}\n\n"
        
        # Add difficulty
        message_text += f"*Difficulty:* {difficulty}\n\n"
        
        # Add rewards if any
        if rewards:
            message_text += "*Rewards:*\n"
            
            if "items" in rewards:
                items = rewards["items"]
                if isinstance(items, list):
                    for item in items:
                        message_text += f"• {item}\n"
                else:
                    message_text += f"• {items}\n"
            
            if "experience" in rewards:
                message_text += f"• {rewards['experience']} experience\n"
                
            if "lore" in rewards:
                message_text += f"• New lore discoveries\n"
                
            message_text += "\n"
        
        # Add status
        if is_active:
            current_scene = active_quest.get("current_scene", 1)
            total_scenes = len(quest.get("scenes", []))
            
            message_text += f"*Status:* In Progress ({current_scene}/{total_scenes})\n\n"
            
            # Create keyboard with continue/abandon options
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "▶️ Continue Quest", 
                        callback_data=create_callback_data("quest_continue", id=quest_id), 
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Abandon Quest", 
                        callback_data=create_callback_data("quest_abandon", id=quest_id), 
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅️ Back to Quests", 
                        callback_data=create_quest_start_callback(quest_id), 
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 Main Menu", 
                        callback_data=create_callback_data("quest_menu"), 
                    )
                ]
            ])
        else:
            message_text += "*Status:* Not Started\n\n"
            
            # Check prerequisites
            prerequisites = quest.get("prerequisites", {})
            missing_prereqs = []
            
            if "items" in prerequisites:
                required_items = prerequisites["items"]
                if isinstance(required_items, list):
                    for item in required_items:
                        if not self.quest_manager.has_item(user_id, item):
                            missing_prereqs.append(f"Item: {item}")
                else:
                    if not self.quest_manager.has_item(user_id, required_items):
                        missing_prereqs.append(f"Item: {required_items}")
            
            if "quests" in prerequisites:
                required_quests = prerequisites["quests"]
                if isinstance(required_quests, list):
                    for req_quest in required_quests:
                        if not self.quest_manager.has_completed_quest(user_id, req_quest):
                            quest_details = self.quest_manager.get_quest_details(req_quest)
                            quest_title = quest_details.get("title", req_quest) if quest_details else req_quest
                            missing_prereqs.append(f"Quest: {quest_title}")
                else:
                    if not self.quest_manager.has_completed_quest(user_id, required_quests):
                        quest_details = self.quest_manager.get_quest_details(required_quests)
                        quest_title = quest_details.get("title", required_quests) if quest_details else required_quests
                        missing_prereqs.append(f"Quest: {quest_title}")
            
            if "lore" in prerequisites:
                required_lore = prerequisites["lore"]
                if isinstance(required_lore, list):
                    for lore_entry in required_lore:
                        if not self.quest_manager.has_discovered_lore(user_id, lore_entry):
                            missing_prereqs.append(f"Lore: {lore_entry}")
                else:
                    if not self.quest_manager.has_discovered_lore(user_id, required_lore):
                        missing_prereqs.append(f"Lore: {required_lore}")
            
            if missing_prereqs:
                message_text += "*Prerequisites:*\n"
                for prereq in missing_prereqs:
                    message_text += f"• {prereq}\n"
                message_text += "\nYou must fulfill these prerequisites before starting this quest.\n\n"
                
                # Create keyboard with back options only
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "⬅️ Back to Quests", 
                            callback_data=create_callback_data("quest_menu")
                        ),
                        InlineKeyboardButton(
                            "🏠 Main Menu", 
                            callback_data=create_callback_data("main_menu")
                        )
                    ]
                ])
            else:
                # Create keyboard with start option
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "▶️ Start Quest", 
                            callback_data=create_callback_data("quest_start", id=quest_id)
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅️ Back to Quests", 
                            callback_data=create_callback_data("quest_menu")
                        ),
                        InlineKeyboardButton(
                            "🏠 Main Menu", 
                            callback_data=create_callback_data("main_menu")
                        )
                    ]
                ])
        
        # Send or edit message
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
    
    @error_handler(error_type="callback", custom_message="I couldn't process that button press. Please try again.")
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: Dict) -> None:
        """Handle callback queries for quest-related features.
        
        Args:
            update: The update containing the callback query
            context: The context object for the bot
            callback_data: The parsed callback data
        """
        if not update or not update.callback_query or not update.effective_user:
            logger.error("Update, callback_query, or effective_user is None in handle_callback")
            return
            
        query = update.callback_query
        user_id = update.effective_user.id
        
        # Get the action
        action = callback_data.get("action", "")
        
        # Handle different actions
        try:
            if action == "quest_menu":
                await query.answer("Opening quest menu")
                # Create a fake update to reuse the quests_command
                await self.quests_command(update, context)
            elif action == "quest_view":
                await query.answer("Loading quest details")
                quest_id = callback_data.get("id", "")
                if quest_id:
                    await self._display_quest_details(update, context, quest_id)
                else:
                    logger.error("No quest ID provided in quest_view callback")
                    await query.answer("Invalid quest ID")
            elif action == "quest_start":
                await query.answer("Starting quest")
                quest_id = callback_data.get("id", "")
                if quest_id:
                    # Start the quest
                    try:
                        success = self.quest_manager.start_quest(user_id, quest_id)
                        if success:
                            # Get the first scene
                            quest = self.quest_manager.get_quest_details(quest_id)
                            scenes = quest.get("scenes", [])
                            if scenes:
                                first_scene = scenes[0]
                                await self._display_quest_scene(update, context, quest_id, first_scene)
                            else:
                                logger.error(f"No scenes found for quest {quest_id}")
                                await query.edit_message_text(
                                    "This quest has no scenes. Please try another quest.",
                                    reply_markup=InlineKeyboardMarkup([[
                                        InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quest_menu"}')
                                    ]])
                                )
                        else:
                            logger.error(f"Failed to start quest {quest_id} for user {user_id}")
                            await query.edit_message_text(
                                "I couldn't start this quest. You may not meet the prerequisites or it may already be in progress.",
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quest_menu"}')
                                ]])
                            )
                    except Exception as e:
                        logger.error(f"Error starting quest: {e}")
                        await query.edit_message_text(
                            "I encountered an error starting this quest. Please try again.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quest_menu"}')
                            ]])
                        )
                else:
                    logger.error("No quest ID provided in quest_start callback")
                    await query.answer("Invalid quest ID")
            elif action == "quest_continue":
                await query.answer("Continuing quest")
                quest_id = callback_data.get("id", "")
                if quest_id:
                    # Get the current scene
                    active_quest = self.quest_manager.get_active_quest(user_id, quest_id)
                    if active_quest:
                        current_scene_index = active_quest.get("current_scene", 1) - 1  # Convert to 0-based index
                        quest = self.quest_manager.get_quest_details(quest_id)
                        scenes = quest.get("scenes", [])
                        if 0 <= current_scene_index < len(scenes):
                            current_scene = scenes[current_scene_index]
                            await self._display_quest_scene(update, context, quest_id, current_scene)
                        else:
                            logger.error(f"Invalid scene index {current_scene_index} for quest {quest_id}")
                            await query.edit_message_text(
                                "I couldn't find the current scene for this quest. Please try again.",
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quest_menu"}')
                                ]])
                            )
                    else:
                        logger.error(f"No active quest found for user {user_id} and quest {quest_id}")
                        await query.edit_message_text(
                            "This quest is not currently active. You may need to start it first.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quest_menu"}')
                            ]])
                        )
                else:
                    logger.error("No quest ID provided in quest_continue callback")
                    await query.answer("Invalid quest ID")
            elif action == "quest_choice":
                await query.answer("Processing your choice")
                quest_id = callback_data.get("id", "")
                choice_id = callback_data.get("choice", "")
                if quest_id and choice_id:
                    # Process the choice
                    try:
                        next_scene = self.quest_manager.make_choice(user_id, quest_id, choice_id)
                        if next_scene:
                            if next_scene == "complete":
                                # Quest completed
                                await self._display_quest_completion(update, context, quest_id)
                            else:
                                # Display next scene
                                await self._display_quest_scene(update, context, quest_id, next_scene)
                        else:
                            logger.error(f"No next scene found for choice {choice_id} in quest {quest_id}")
                            await query.edit_message_text(
                                "I couldn't process your choice. Please try again.",
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quest_menu"}')
                                ]])
                            )
                    except Exception as e:
                        logger.error(f"Error processing choice: {e}")
                        await query.edit_message_text(
                            "I encountered an error processing your choice. Please try again.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quest_menu"}')
                            ]])
                        )
                else:
                    logger.error(f"Missing quest ID or choice ID in quest_choice callback: {callback_data}")
                    await query.answer("Invalid choice data")
            elif action == "quest_abandon":
                await query.answer("Abandoning quest")
                quest_id = callback_data.get("id", "")
                if quest_id:
                    # Confirm abandonment
                    quest = self.quest_manager.get_quest_details(quest_id)
                    title = quest.get("title", "this quest") if quest else "this quest"
                    
                    await query.edit_message_text(
                        f"Are you sure you want to abandon *{title}*?\n\n"
                        "Your progress will be lost and you'll need to start over.",
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(
                                    "✓ Yes, Abandon", 
                                    callback_data=create_callback_data("quest_abandon_confirm", id=quest_id)
                                ),
                                InlineKeyboardButton(
                                    "✗ No, Keep", 
                                    callback_data=create_callback_data("quest_view", id=quest_id)
                                )
                            ]
                        ]),
                        parse_mode='Markdown'
                    )
                else:
                    logger.error("No quest ID provided in quest_abandon callback")
                    await query.answer("Invalid quest ID")
            elif action == "quest_abandon_confirm":
                await query.answer("Confirming abandonment")
                quest_id = callback_data.get("id", "")
                if quest_id:
                    # Abandon the quest
                    try:
                        success = self.quest_manager.abandon_quest(user_id, quest_id)
                        if success:
                            quest = self.quest_manager.get_quest_details(quest_id)
                            title = quest.get("title", "Quest") if quest else "Quest"
                            
                            await query.edit_message_text(
                                f"You have abandoned *{title}*.\n\n"
                                "You can start it again at any time.",
                                reply_markup=InlineKeyboardMarkup([
                                    [
                                        InlineKeyboardButton(
                                            "« Back to Quests", 
                                            callback_data=create_callback_data("quest_menu")
                                        ),
                                        InlineKeyboardButton(
                                            "🏠 Main Menu", 
                                            callback_data=create_callback_data("main_menu")
                                        )
                                    ]
                                ]),
                                parse_mode='Markdown'
                            )
                        else:
                            logger.error(f"Failed to abandon quest {quest_id} for user {user_id}")
                            await query.edit_message_text(
                                "I couldn't abandon this quest. Please try again.",
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quest_menu"}')
                                ]])
                            )
                    except Exception as e:
                        logger.error(f"Error abandoning quest: {e}")
                        await query.edit_message_text(
                            "I encountered an error abandoning this quest. Please try again.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("« Back to Quests", callback_data='{"action":"quest_menu"}')
                            ]])
                        )
                else:
                    logger.error("No quest ID provided in quest_abandon_confirm callback")
                    await query.answer("Invalid quest ID")
            elif action == "characters_menu":
                await query.answer("Opening character menu")
                await self.characters_menu(update, context)
            else:
                logger.warning(f"Unknown quest callback action: {action}")
                await query.answer("Unknown action")
        except Exception as e:
            logger.error(f"Error handling quest callback: {e}")
            await query.answer("Error processing your request")
    
    async def _display_quest_scene(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quest_id: str, scene: Dict) -> None:
        """Display a quest scene with choices.
        
        Args:
            update: The update containing the callback query
            context: The context object for the bot
            quest_id: The ID of the quest
            scene: The scene data to display
        """
        if not update or not update.callback_query:
            logger.error("Update or callback_query is None in _display_quest_scene")
            return
            
        callback_query = update.callback_query
        
        # Extract scene data
        scene_id = scene.get("id", "")
        title = scene.get("title", "")
        description = scene.get("description", "")
        choices = scene.get("choices", [])
        
        # Create message text
        message_text = f"*{title}*\n\n{description}\n\n"
        
        if choices:
            message_text += "*What will you do?*"
            
            # Create keyboard with choices
            keyboard_buttons = []
            for choice in choices:
                choice_id = choice.get("id", "")
                choice_text = choice.get("text", "")
                
                if choice_id and choice_text:
                    callback_data = create_quest_choice_callback(quest_id, choice_id)
                    keyboard_buttons.append([InlineKeyboardButton(choice_text, callback_data=callback_data)])
            
            # Add back button
            keyboard_buttons.append([
                InlineKeyboardButton(
                    "⬅️ Back to Quests", 
                    callback_data=create_callback_data("quest_menu")
                )
            ])
            
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        else:
            # No choices, just a continue button
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "▶️ Continue", 
                        callback_data=create_quest_choice_callback(quest_id, "continue")
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅️ Back to Quests", 
                        callback_data=create_callback_data("quest_menu")
                    )
                ]
            ])
        
        # Edit message
        try:
            await callback_query.edit_message_text(
                message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending quest scene: {e}")
            await callback_query.answer("Error displaying quest scene. Please try again.")
    
    async def _display_quest_completion(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quest_id: str) -> None:
        """Display quest completion message and rewards.
        
        Args:
            update: The update containing the callback query
            context: The context object for the bot
            quest_id: The ID of the completed quest
        """
        if not update or not update.callback_query or not update.effective_user:
            logger.error("Update, callback_query, or effective_user is None in _display_quest_completion")
            return
            
        callback_query = update.callback_query
        user_id = update.effective_user.id
        
        # Get quest details
        try:
            quest = self.quest_manager.get_quest_details(quest_id)
            title = quest.get("title", "Quest") if quest else "Quest"
            rewards = quest.get("rewards", {}) if quest else {}
            
            # Create message text
            message_text = f"🎉 *{title} Completed!* 🎉\n\n"
            message_text += "Congratulations! You have successfully completed this quest.\n\n"
            
            # Add rewards if any
            if rewards:
                message_text += "*Rewards:*\n"
                
                if "items" in rewards:
                    items = rewards["items"]
                    if isinstance(items, list):
                        for item in items:
                            message_text += f"• {item}\n"
                            # Add item to inventory
                            self.quest_manager.add_item(user_id, item)
                    else:
                        message_text += f"• {items}\n"
                        # Add item to inventory
                        self.quest_manager.add_item(user_id, items)
                
                if "experience" in rewards:
                    message_text += f"• {rewards['experience']} experience\n"
                    # Add experience
                    self.quest_manager.add_experience(user_id, rewards['experience'])
                    
                if "lore" in rewards:
                    lore_entries = rewards["lore"]
                    if isinstance(lore_entries, list):
                        for entry in lore_entries:
                            message_text += f"• New lore: {entry}\n"
                            # Discover lore
                            self.quest_manager.discover_lore(user_id, entry)
                    else:
                        message_text += f"• New lore: {lore_entries}\n"
                        # Discover lore
                        self.quest_manager.discover_lore(user_id, lore_entries)
                
                message_text += "\n"
            
            # Create keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "📋 View Inventory", 
                        callback_data=create_callback_data("inventory_menu")
                    ),
                    InlineKeyboardButton(
                        "📚 View Collection", 
                        callback_data=create_callback_data("lore_collection")
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⚔️ More Quests", 
                        callback_data=create_callback_data("quest_menu")
                    ),
                    InlineKeyboardButton(
                        "🏠 Main Menu", 
                        callback_data=create_callback_data("main_menu")
                    )
                ]
            ])
            
            # Edit message
            await callback_query.edit_message_text(
                message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending quest completion: {e}")
            await callback_query.answer("Error displaying quest completion. Please try again.")
    
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
            # No active quests
            message_text = (
                "⚔️ *Active Quests* ⚔️\n\n"
                "You don't have any active quests.\n\n"
                "Use /quests to browse available quests and start a new adventure!"
            )
            
            # Create keyboard with alternative options
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⚔️ Browse Quests", callback_data=create_callback_data("quest_menu")),
                    InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
                ]
            ])
            
            await update.message.reply_text(
                message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            return
        
        # Create message text
        message_text = "⚔️ *Your Active Quests* ⚔️\n\n"
        
        # Create quest menu items
        quest_items = []
        for active_quest in active_quests:
            quest_id = active_quest.get("quest_id", "")
            quest = self.quest_manager.get_quest_details(quest_id)
            
            if quest:
                title = quest.get("title", "Unknown Quest")
                current_scene = active_quest.get("current_scene", 1)
                total_scenes = len(quest.get("scenes", []))
                
                # Create callback data for continuing quest
                callback_data = create_callback_data("quest_continue", id=quest_id)
                
                quest_items.append((f"{title} ({current_scene}/{total_scenes})", callback_data, "primary"))
        
        # Create keyboard with optimized layout
        keyboard = create_menu_keyboard(quest_items)
        
        # Add navigation buttons
        keyboard.inline_keyboard.append([
            InlineKeyboardButton("⚔️ Browse Quests", callback_data=create_callback_data("quest_menu")),
            InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
        ])
        
        # Send message
        await update.message.reply_text(
            message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    # Alias for active_quests_command to match main.py reference
    async def active_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Alias for active_quests_command to match main.py reference."""
        await self.active_quests_command(update, context)
    
    @error_handler(error_type="command", custom_message="I couldn't retrieve your inventory. Please try again.")
    async def inventory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /inventory command to view collected items.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in inventory_command")
            return
            
        user_id = update.effective_user.id
        
        # Get inventory
        try:
            inventory = self.quest_manager.get_inventory(user_id)
        except Exception as e:
            logger.error(f"Error getting inventory: {e}")
            inventory = []
        
        if not inventory:
            # Empty inventory
            message_text = (
                "🎒 *Your Inventory* 🎒\n\n"
                "Your inventory is empty.\n\n"
                "Complete quests and explore the world to find items!"
            )
            
            # Create keyboard with alternative options
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⚔️ Browse Quests", callback_data=create_callback_data("quest_menu")),
                    InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
                ]
            ])
            
            await update.message.reply_text(
                message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            return
        
        # Group items by rarity
        items_by_rarity = {}
        for item in inventory:
            item_name = item.get("item_name", "Unknown Item")
            quantity = item.get("quantity", 1)
            rarity = item.get("rarity", "common")
            
            if rarity not in items_by_rarity:
                items_by_rarity[rarity] = []
            
            items_by_rarity[rarity].append((item_name, quantity))
        
        # Create message text
        message_text = "🎒 *Your Inventory* 🎒\n\n"
        
        # Order rarities
        rarity_order = ["legendary", "epic", "rare", "uncommon", "common"]
        
        # Add items by rarity
        for rarity in rarity_order:
            if rarity in items_by_rarity:
                # Capitalize rarity
                rarity_display = rarity.capitalize()
                
                message_text += f"*{rarity_display} Items:*\n"
                
                for item_name, quantity in items_by_rarity[rarity]:
                    message_text += f"• {item_name} (x{quantity})\n"
                
                message_text += "\n"
        
        # Create keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔨 Craft Items", callback_data=create_callback_data("craft_menu")),
                InlineKeyboardButton("⚔️ Quests", callback_data=create_callback_data("quest_menu"))
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
            ]
        ])
        
        # Send message
        await update.message.reply_text(
            message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @error_handler(error_type="command", custom_message="I couldn't retrieve crafting recipes. Please try again.")
    async def craft_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /craft command to view and use crafting recipes.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in craft_command")
            return
            
        user_id = update.effective_user.id
        
        # Check if a specific item was requested
        if context.args and len(context.args) > 0:
            # Join all arguments into a single item name
            item_name = " ".join(context.args).lower()
            
            # Try to craft the item
            try:
                result = self.quest_manager.craft_item(user_id, item_name)
                
                if result.get("success", False):
                    # Item crafted successfully
                    message_text = (
                        f"✅ *{item_name.capitalize()} Crafted!* ✅\n\n"
                        "You have successfully crafted this item.\n\n"
                        "*Components Used:*\n"
                    )
                    
                    # Add components
                    components = result.get("components", {})
                    for component, quantity in components.items():
                        message_text += f"• {component} (x{quantity})\n"
                    
                    # Create keyboard
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("📋 View Inventory", callback_data=create_callback_data("inventory_menu")),
                            InlineKeyboardButton("🔨 Craft More", callback_data=create_callback_data("craft_menu"))
                        ],
                        [
                            InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
                        ]
                    ])
                else:
                    # Crafting failed
                    reason = result.get("reason", "Unknown error")
                    
                    message_text = (
                        f"❌ *Crafting Failed* ❌\n\n"
                        f"I couldn't craft {item_name}.\n\n"
                        f"*Reason:* {reason}\n\n"
                    )
                    
                    # Add missing components if applicable
                    missing = result.get("missing", {})
                    if missing:
                        message_text += "*Missing Components:*\n"
                        for component, quantity in missing.items():
                            message_text += f"• {component} (x{quantity})\n"
                    
                    # Create keyboard
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("📋 View Inventory", callback_data=create_callback_data("inventory_menu")),
                            InlineKeyboardButton("🔨 View Recipes", callback_data=create_callback_data("craft_menu"))
                        ],
                        [
                            InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
                        ]
                    ])
                
                await update.message.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error crafting item: {e}")
                await update.message.reply_text(
                    f"I encountered an error trying to craft {item_name}. Please try again."
                )
        else:
            # No specific item requested, show crafting menu
            try:
                # Get available recipes
                recipes = self.quest_manager.get_available_recipes(user_id)
                
                if not recipes:
                    # No recipes available
                    message_text = (
                        "🔨 *Crafting* 🔨\n\n"
                        "You don't have any crafting recipes available.\n\n"
                        "Complete quests and explore the world to discover recipes!"
                    )
                    
                    # Create keyboard with alternative options
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("⚔️ Browse Quests", callback_data=create_callback_data("quest_menu")),
                            InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
                        ]
                    ])
                    
                    await update.message.reply_text(
                        message_text,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                    return
                
                # Create message text
                message_text = (
                    "🔨 *Available Crafting Recipes* 🔨\n\n"
                    "Select a recipe to view details and craft:\n\n"
                )
                
                # Create recipe menu items
                recipe_items = []
                for recipe in recipes:
                    result_item = recipe.get("result_item", "Unknown Item")
                    result_rarity = recipe.get("result_rarity", "common")
                    
                    # Create callback data for viewing recipe
                    callback_data = create_callback_data("craft_view", name=result_item)
                    
                    # Determine button style based on rarity
                    style = "secondary"
                    if result_rarity == "uncommon":
                        style = "primary"
                    elif result_rarity == "rare":
                        style = "info"
                    elif result_rarity == "epic":
                        style = "warning"
                    elif result_rarity == "legendary":
                        style = "danger"
                    
                    recipe_items.append((result_item, callback_data, style))
                
                # Create keyboard with optimized layout
                keyboard = create_menu_keyboard(recipe_items)
                
                # Add navigation buttons
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton("📋 View Inventory", callback_data=create_callback_data("inventory_menu")),
                    InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
                ])
                
                # Send message
                await update.message.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error getting crafting recipes: {e}")
                await update.message.reply_text(
                    "I encountered an error retrieving crafting recipes. Please try again."
                )
    
    @error_handler(error_type="command", custom_message="I couldn't process that command. Please try again.")
    async def interact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /interact command to speak with characters.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in interact_command")
            return
            
        user_id = update.effective_user.id
        
        # Check if a specific character was requested
        if context.args and len(context.args) > 0:
            # Join all arguments into a single character name
            character_name = " ".join(context.args).lower()
            
            # Try to find the character
            try:
                character = self.lore_manager.get_character(character_name)
                
                if character:
                    # Display character interaction
                    await self._display_character_interaction(update, context, character)
                else:
                    await update.message.reply_text(
                        f"I couldn't find a character named '{character_name}'.\n\n"
                        "Use /characters to see characters you've met."
                    )
            except Exception as e:
                logger.error(f"Error finding character: {e}")
                await update.message.reply_text(
                    f"I encountered an error finding that character. Please try again."
                )
        else:
            # No specific character requested, show character menu
            try:
                # Create a fake callback query to reuse the characters_menu method
                class FakeCallbackQuery:
                    def __init__(self, message):
                        self.message = message
                    
                    async def edit_message_text(self, text, reply_markup, parse_mode):
                        await self.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
                    
                    async def answer(self, text):
                        pass
                
                class FakeUpdate:
                    def __init__(self, update):
                        self.effective_user = update.effective_user
                        self.callback_query = FakeCallbackQuery(update.message)
                
                # Create fake update
                fake_update = FakeUpdate(update)
                
                # Call the characters_menu method
                await self.characters_menu(fake_update, context)
            except Exception as e:
                logger.error(f"Error showing character menu: {e}")
                await update.message.reply_text(
                    "I encountered an error showing the character menu. Please try again."
                )
    
    async def _display_character_interaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE, character: Dict[str, Any]) -> None:
        """Display character interaction interface.
        
        Args:
            update: The update containing the command or callback query
            context: The context object for the bot
            character: The character data
        """
        # Implementation details omitted for brevity
        pass
    
    @error_handler(error_type="callback", custom_message="I couldn't open the character menu. Please try again.")
    async def characters_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display the menu of characters the user has met.
        
        Args:
            update: The update containing the command or callback query
            context: The context object for the bot
        """
        if not update or not update.effective_user:
            logger.error("Update or effective_user is None in characters_menu")
            return
            
        user_id = update.effective_user.id
        
        # Determine if this is from a command or callback
        if update.callback_query:
            message_func = update.callback_query.edit_message_text
            await update.callback_query.answer("Opening character menu")
        elif hasattr(update, 'message') and update.message:
            message_func = update.message.reply_text
        else:
            logger.error("Neither callback_query nor message in characters_menu")
            return
        
        # Get characters the user has met
        try:
            relationships = self.db.execute_query(
                "SELECT character_name, affinity FROM user_relationships "
                "WHERE user_id = ? ORDER BY affinity DESC",
                (user_id,)
            )
        except Exception as e:
            logger.error(f"Database error in characters_menu: {e}")
            relationships = []
        
        if not relationships:
            # No characters met
            message_text = (
                "👥 *Characters* 👥\n\n"
                "You haven't met any characters yet.\n\n"
                "Complete quests and explore the world to meet characters!"
            )
            
            # Create keyboard with alternative options
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⚔️ Browse Quests", callback_data=create_callback_data("quest_menu")),
                    InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
                ]
            ])
            
            await message_func(
                message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            return
        
        # Create message text
        message_text = (
            "👥 *Characters You've Met* 👥\n\n"
            "Select a character to interact with:\n\n"
        )
        
        # Create character menu items
        character_items = []
        for row in relationships:
            character_name, affinity = row
            
            # Get character details
            character = self.lore_manager.get_character(character_name)
            if not character:
                continue
            
            # Create callback data for interacting with character
            callback_data = create_callback_data("character_interact", name=character_name)
            
            # Determine button style based on affinity
            style = "secondary"
            if affinity >= 75:
                style = "success"
            elif affinity >= 50:
                style = "primary"
            elif affinity >= 25:
                style = "info"
            elif affinity < 0:
                style = "danger"
            
            # Add affinity indicator
            display_name = f"{character_name} ({affinity})"
            
            character_items.append((display_name, callback_data, style))
        
        # Create keyboard with optimized layout
        keyboard = create_menu_keyboard(character_items)
        
        # Add navigation buttons
        keyboard.inline_keyboard.append([
            InlineKeyboardButton("⚔️ Quests", callback_data=create_callback_data("quest_menu")),
            InlineKeyboardButton("🏠 Main Menu", callback_data=create_callback_data("main_menu"))
        ])
        
        # Send or edit message
        await message_func(
            message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @error_handler(error_type="command", custom_message="I couldn't retrieve the character list. Please try again.")
    async def characters_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /characters command to view characters the user has met.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        await self.characters_menu(update, context)
