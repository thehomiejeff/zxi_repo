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
    
    def __init__(self, db: Database, quest_manager: QuestManager, lore_manager: FangenLoreManager):
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
        
        # Get available quests
        try:
            quests = self.quest_manager.get_available_quests(user_id)
        except Exception as e:
            logger.error(f"Error getting available quests: {e}")
            quests = []
        
        # Get active quests
        try:
            active_quests = self.quest_manager.get_active_quests(user_id)
        except Exception as e:
            logger.error(f"Error getting active quests: {e}")
            active_quests = []
        
        # Format message
        if quests or active_quests:
            message = "🗺️ *Available Quests* 🗺️\n\nSelect a quest to view details or begin your journey."
            
            # Create buttons for quests
            buttons = []
            
            # Add active quests first
            for quest in active_quests:
                quest_id = quest.get("id")
                quest_name = quest.get("name", "Unknown Quest")
                quest_progress = quest.get("progress", 0)
                
                # Format progress as percentage
                progress_text = f" ({quest_progress}%)" if quest_progress > 0 else ""
                
                buttons.append((
                    f"🔵 {quest_name}{progress_text}",
                    create_quest_view_callback(quest_id),
                    "primary"
                ))
            
            # Add available quests
            for quest in quests:
                quest_id = quest.get("id")
                quest_name = quest.get("name", "Unknown Quest")
                
                # Skip if already in active quests
                if any(active_quest.get("id") == quest_id for active_quest in active_quests):
                    continue
                
                buttons.append((
                    quest_name,
                    create_quest_view_callback(quest_id),
                    "secondary"
                ))
            
            # Add back button
            buttons.append((
                "⬅️ Back to Main Menu",
                create_callback_data("main_menu"),
                "neutral"
            ))
            
            # Create keyboard
            keyboard = create_menu_keyboard(buttons)
            
        else:
            message = (
                "🗺️ *Quests* 🗺️\n\n"
                "There are no quests available to you at this time. "
                "Explore the world of Fangen to unlock new opportunities!"
            )
            
            # Create keyboard with just back button
            keyboard = create_menu_keyboard([
                ("📚 Explore Lore", create_callback_data("lore_menu"), "primary"),
                ("⬅️ Back to Main Menu", create_callback_data("main_menu"), "neutral")
            ])
        
        # Send message
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @error_handler(error_type="general", custom_message="I couldn't access that quest. Please try again.")
    async def quest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /quest command to view or start a specific quest."""
        if not update or not update.effective_user or not update.message:
            logger.error("Update, effective_user, or message is None in quest_command")
            return
            
        user_id = update.effective_user.id
        quest_name = ' '.join(context.args) if context.args else None
        
        if not quest_name:
            await update.message.reply_text(
                "Please provide a quest name after the command.\n"
                "Example: `/quest The Lost Artifact`\n\n"
                "Or use /quests to see available quests.",
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
        quest_id = quest.get("id")
        await self._display_quest_details(update, context, quest_id)
    
    async def _display_quest_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quest_id: str) -> None:
        """Display quest details and options."""
        if not update or not update.effective_user:
            logger.error("Update or effective_user is None in _display_quest_details")
            return
            
        user_id = update.effective_user.id
        
        # Get quest details
        try:
            quest = self.quest_manager.get_quest_details(quest_id)
        except Exception as e:
            logger.error(f"Error getting quest details: {e}")
            
            # Send error message
            if update.callback_query:
                await update.callback_query.answer("Error retrieving quest details. Please try again.")
            elif update.message:
                await update.message.reply_text("Error retrieving quest details. Please try again.")
            return
        
        if not quest:
            # Send error message
            if update.callback_query:
                await update.callback_query.answer("Quest not found. Please try another quest.")
            elif update.message:
                await update.message.reply_text("Quest not found. Please try another quest.")
            return
        
        # Check if user has this quest active
        try:
            is_active = self.quest_manager.is_quest_active(user_id, quest_id)
            progress = self.quest_manager.get_quest_progress(user_id, quest_id) if is_active else 0
        except Exception as e:
            logger.error(f"Error checking quest status: {e}")
            is_active = False
            progress = 0
        
        # Format quest details
        quest_name = quest.get("name", "Unknown Quest")
        description = quest.get("description", "No description available.")
        difficulty = quest.get("difficulty", "Unknown")
        rewards = quest.get("rewards", {})
        
        # Format rewards text
        rewards_text = ""
        if rewards:
            rewards_text = "\n\n*Rewards:*\n"
            for reward_type, reward_value in rewards.items():
                if reward_type == "items":
                    for item, quantity in reward_value.items():
                        rewards_text += f"• {item} x{quantity}\n"
                elif reward_type == "lore":
                    rewards_text += f"• Lore: {', '.join(reward_value)}\n"
                elif reward_type == "characters":
                    rewards_text += f"• Meet: {', '.join(reward_value)}\n"
                else:
                    rewards_text += f"• {reward_type.capitalize()}: {reward_value}\n"
        
        # Format progress text
        progress_text = f"\n\n*Progress:* {progress}%" if is_active and progress > 0 else ""
        
        message = (
            f"🗺️ *{quest_name}* 🗺️\n\n"
            f"*Difficulty:* {difficulty}\n"
            f"{progress_text}\n\n"
            f"{description}"
            f"{rewards_text}"
        )
        
        # Create buttons
        keyboard = []
        
        if is_active:
            # Continue button
            keyboard.append([
                create_styled_button(
                    "▶️ Continue Quest", 
                    create_callback_data("quest_continue", id=quest_id), 
                    "primary"
                )
            ])
            
            # Abandon button
            keyboard.append([
                create_styled_button(
                    "❌ Abandon Quest", 
                    create_callback_data("quest_abandon", id=quest_id), 
                    "danger"
                )
            ])
        else:
            # Start button
            keyboard.append([
                create_styled_button(
                    "▶️ Start Quest", 
                    create_quest_start_callback(quest_id), 
                    "primary"
                )
            ])
        
        # Back button
        keyboard.append([
            create_styled_button(
                "« Back to Quests", 
                create_callback_data("quest_menu"), 
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
                        text=f"Error displaying quest details for {quest_name}. Please try again.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔄 Try Again", callback_data='{"action":"retry"}'),
                            InlineKeyboardButton("🏠 Main Menu", callback_data='{"action":"main_menu"}')
                        ]])
                    )
                except Exception as inner_e:
                    logger.error(f"Failed to send fallback message: {inner_e}")
    
    @error_handler(error_type="callback", custom_message="I couldn't process that button press. Please try again.")
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: Dict) -> None:
        """Handle callback queries for quest-related actions."""
        if not update or not update.callback_query or not update.effective_user:
            logger.error("Update, callback_query, or effective_user is None in handle_callback")
            return
            
        callback_query = update.callback_query
        user_id = update.effective_user.id
        action = callback_data.get("action", "")
        
        # Handle different actions
        if action == "quest_menu":
            # Create a fake message to reuse the quests_command method
            update.message = callback_query.message
            await self.quests_command(update, context)
            
        elif action == "quest_view":
            quest_id = callback_data.get("id")
            if quest_id:
                await self._display_quest_details(update, context, quest_id)
            else:
                await callback_query.answer("Invalid quest ID. Please try again.")
                
        elif action == "quest_start":
            quest_id = callback_data.get("id")
            if quest_id:
                try:
                    # Start the quest
                    success = await self.quest_manager.start_quest(user_id, quest_id)
                    
                    if success:
                        # Get the first scene
                        scene = await self.quest_manager.get_current_scene(user_id, quest_id)
                        
                        if scene:
                            # Display the scene
                            await self._display_quest_scene(update, context, quest_id, scene)
                        else:
                            await callback_query.answer("Error retrieving quest scene. Please try again.")
                    else:
                        await callback_query.answer("Failed to start quest. Please try again.")
                except Exception as e:
                    logger.error(f"Error starting quest: {e}")
                    await callback_query.answer("Error starting quest. Please try again.")
            else:
                await callback_query.answer("Invalid quest ID. Please try again.")
                
        elif action == "quest_continue":
            quest_id = callback_data.get("id")
            if quest_id:
                try:
                    # Get the current scene
                    scene = await self.quest_manager.get_current_scene(user_id, quest_id)
                    
                    if scene:
                        # Display the scene
                        await self._display_quest_scene(update, context, quest_id, scene)
                    else:
                        await callback_query.answer("Error retrieving quest scene. Please try again.")
                except Exception as e:
                    logger.error(f"Error continuing quest: {e}")
                    await callback_query.answer("Error continuing quest. Please try again.")
            else:
                await callback_query.answer("Invalid quest ID. Please try again.")
                
        elif action == "quest_choice":
            quest_id = callback_data.get("id")
            scene_id = callback_data.get("scene")
            choice_id = callback_data.get("choice")
            
            if quest_id and scene_id and choice_id:
                try:
                    # Make the choice
                    next_scene = await self.quest_manager.make_choice(user_id, quest_id, scene_id, choice_id)
                    
                    if next_scene:
                        # Display the next scene
                        await self._display_quest_scene(update, context, quest_id, next_scene)
                    else:
                        # Quest might be completed
                        completed = await self.quest_manager.is_quest_completed(user_id, quest_id)
                        
                        if completed:
                            # Display completion message
                            await self._display_quest_completion(update, context, quest_id)
                        else:
                            await callback_query.answer("Error advancing quest. Please try again.")
                except Exception as e:
                    logger.error(f"Error making quest choice: {e}")
                    await callback_query.answer("Error making quest choice. Please try again.")
            else:
                await callback_query.answer("Invalid quest choice. Please try again.")
                
        elif action == "quest_abandon":
            quest_id = callback_data.get("id")
            if quest_id:
                try:
                    # Confirm abandonment
                    keyboard = [
                        [
                            create_styled_button(
                                "Yes, Abandon Quest", 
                                create_callback_data("quest_abandon_confirm", id=quest_id), 
                                "danger"
                            )
                        ],
                        [
                            create_styled_button(
                                "No, Keep Quest", 
                                create_quest_view_callback(quest_id), 
                                "primary"
                            )
                        ]
                    ]
                    
                    await callback_query.edit_message_text(
                        "⚠️ *Are you sure you want to abandon this quest?* ⚠️\n\n"
                        "All progress will be lost and you'll need to start over if you want to attempt it again.",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Error displaying abandon confirmation: {e}")
                    await callback_query.answer("Error displaying abandon confirmation. Please try again.")
            else:
                await callback_query.answer("Invalid quest ID. Please try again.")
                
        elif action == "quest_abandon_confirm":
            quest_id = callback_data.get("id")
            if quest_id:
                try:
                    # Abandon the quest
                    success = await self.quest_manager.abandon_quest(user_id, quest_id)
                    
                    if success:
                        await callback_query.answer("Quest abandoned successfully.")
                        
                        # Return to quest menu
                        update.message = callback_query.message
                        await self.quests_command(update, context)
                    else:
                        await callback_query.answer("Failed to abandon quest. Please try again.")
                except Exception as e:
                    logger.error(f"Error abandoning quest: {e}")
                    await callback_query.answer("Error abandoning quest. Please try again.")
            else:
                await callback_query.answer("Invalid quest ID. Please try again.")
        
        else:
            await callback_query.answer("Unknown quest action. Please try again.")
    
    async def _display_quest_scene(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quest_id: str, scene: Dict) -> None:
        """Display a quest scene with choices."""
        if not update or not update.callback_query or not update.effective_user:
            logger.error("Update, callback_query, or effective_user is None in _display_quest_scene")
            return
            
        callback_query = update.callback_query
        
        # Extract scene details
        scene_id = scene.get("id")
        text = scene.get("text", "No scene text available.")
        choices = scene.get("choices", [])
        
        # Format message
        message = f"{text}"
        
        # Create buttons for choices
        keyboard = []
        for choice in choices:
            choice_id = choice.get("id")
            choice_text = choice.get("text", "No choice text available.")
            
            keyboard.append([
                create_styled_button(
                    choice_text, 
                    create_quest_choice_callback(quest_id, scene_id, choice_id), 
                    "primary"
                )
            ])
        
        # Add back button to view quest details
        keyboard.append([
            create_styled_button(
                "« Quest Details", 
                create_quest_view_callback(quest_id), 
                "back"
            )
        ])
        
        # Send or edit message
        try:
            await callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error sending quest scene: {e}")
            await callback_query.answer("Error displaying quest scene. Please try again.")
    
    async def _display_quest_completion(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quest_id: str) -> None:
        """Display quest completion message and rewards."""
        if not update or not update.callback_query or not update.effective_user:
            logger.error("Update, callback_query, or effective_user is None in _display_quest_completion")
            return
            
        callback_query = update.callback_query
        user_id = update.effective_user.id
        
        # Get quest details
        try:
            quest = self.quest_manager.get_quest_details(quest_id)
            rewards = quest.get("rewards", {})
        except Exception as e:
            logger.error(f"Error getting quest details: {e}")
            quest = None
            rewards = {}
        
        if not quest:
            await callback_query.answer("Error retrieving quest details. Please try again.")
            return
        
        quest_name = quest.get("name", "Unknown Quest")
        
        # Format rewards text
        rewards_text = ""
        if rewards:
            rewards_text = "\n\n*Rewards:*\n"
            for reward_type, reward_value in rewards.items():
                if reward_type == "items":
                    for item, quantity in reward_value.items():
                        rewards_text += f"• {item} x{quantity}\n"
                elif reward_type == "lore":
                    rewards_text += f"• Lore: {', '.join(reward_value)}\n"
                elif reward_type == "characters":
                    rewards_text += f"• Meet: {', '.join(reward_value)}\n"
                else:
                    rewards_text += f"• {reward_type.capitalize()}: {reward_value}\n"
        
        message = (
            f"🎉 *Quest Completed!* 🎉\n\n"
            f"Congratulations! You have successfully completed the quest:\n"
            f"*{quest_name}*"
            f"{rewards_text}\n\n"
            f"Your journey continues..."
        )
        
        # Create buttons
        keyboard = [
            [
                create_styled_button(
                    "🗺️ More Quests", 
                    create_callback_data("quest_menu"), 
                    "primary"
                )
            ],
            [
                create_styled_button(
                    "🏠 Main Menu", 
                    create_callback_data("main_menu"), 
                    "neutral"
                )
            ]
        ]
        
        # Send or edit message
        try:
            await callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
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
        
        # Format message
        if active_quests:
            message = "🔵 *Your Active Quests* 🔵\n\nSelect a quest to continue your journey."
            
            # Create buttons for quests
            buttons = []
            for quest in active_quests:
                quest_id = quest.get("id")
                quest_name = quest.get("name", "Unknown Quest")
                quest_progress = quest.get("progress", 0)
                
                # Format progress as percentage
                progress_text = f" ({quest_progress}%)" if quest_progress > 0 else ""
                
                buttons.append((
                    f"{quest_name}{progress_text}",
                    create_quest_view_callback(quest_id),
                    "primary"
                ))
            
            # Add back button
            buttons.append((
                "⬅️ Back to Main Menu",
                create_callback_data("main_menu"),
                "neutral"
            ))
            
            # Create keyboard
            keyboard = create_menu_keyboard(buttons)
            
        else:
            message = (
                "🔵 *Active Quests* 🔵\n\n"
                "You don't have any active quests at the moment. "
                "Use /quests to browse available quests and start a new adventure!"
            )
            
            # Create keyboard with just back button
            keyboard = create_menu_keyboard([
                ("🗺️ View Quests", create_callback_data("quest_menu"), "primary"),
                ("⬅️ Back to Main Menu", create_callback_data("main_menu"), "neutral")
            ])
        
        # Send message
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def inventory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /inventory command to view inventory."""
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
        
        # Format message
        if inventory:
            message = "🎒 *Your Inventory* 🎒\n\nHere are the items you've collected on your journeys:"
            
            # Group items by rarity
            items_by_rarity = {}
            for item in inventory:
                rarity = item.get("rarity", "Common")
                if rarity not in items_by_rarity:
                    items_by_rarity[rarity] = []
                items_by_rarity[rarity].append(item)
            
            # Order rarities
            rarity_order = ["Legendary", "Epic", "Rare", "Uncommon", "Common"]
            
            # Add items to message
            for rarity in rarity_order:
                if rarity in items_by_rarity:
                    message += f"\n\n*{rarity} Items:*\n"
                    for item in items_by_rarity[rarity]:
                        item_name = item.get("name", "Unknown Item")
                        quantity = item.get("quantity", 1)
                        message += f"• {item_name} x{quantity}\n"
            
        else:
            message = (
                "🎒 *Your Inventory* 🎒\n\n"
                "Your inventory is empty. Complete quests and explore the world "
                "to find valuable items and resources!"
            )
        
        # Create keyboard with back button
        keyboard = create_menu_keyboard([
            ("🔨 Craft Items", create_callback_data("craft_menu"), "primary"),
            ("⬅️ Back to Main Menu", create_callback_data("main_menu"), "neutral")
        ])
        
        # Send message
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @error_handler(error_type="general", custom_message="I couldn't access the crafting system. Please try again.")
    async def craft_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /craft command to craft items.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        if not update or not update.message:
            return
        
        user_id = update.effective_user.id
        
        # Get craftable items
        try:
            # Get recipes
            recipes = self.db.execute_query(
                "SELECT * FROM crafting_recipes ORDER BY result_rarity"
            )
            
            if not recipes:
                await update.message.reply_text(
                    "There are no items available to craft at this time. "
                    "Check back later or discover more recipes through quests."
                )
                return
            
            # Create message text
            message_text = (
                "🔨 *Crafting Workshop* 🔨\n\n"
                "Here you can craft items using materials you've collected on your journeys. "
                "Select an item to view its recipe and craft it if you have the required materials."
            )
            
            # Create buttons for each craftable item
            buttons = []
            for recipe in recipes:
                item_name = recipe["result_item"]
                rarity = recipe["result_rarity"]
                
                # Check if user can craft this item
                can_craft, _, _ = self.db.can_craft_item(user_id, item_name)
                
                # Add indicator if user can craft
                status = "✅ " if can_craft else ""
                
                buttons.append((
                    f"{status}{item_name} ({rarity})",
                    create_callback_data("craft_view", {"item": item_name}),
                    "primary" if can_craft else "secondary"
                ))
            
            # Add back button
            buttons.append((
                "⬅️ Back to Main Menu",
                create_callback_data("main_menu"),
                "neutral"
            ))
            
            # Create paginated keyboard if there are many items
            if len(buttons) > 8:
                keyboard = create_paginated_keyboard(
                    buttons, 
                    page=0, 
                    items_per_page=6,
                    callback_prefix="craft_page"
                )
            else:
                keyboard = create_menu_keyboard(buttons)
            
            # Send message with crafting menu
            await update.message.reply_text(
                text=message_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error displaying crafting menu: {e}", exc_info=True)
            await update.message.reply_text(
                "I encountered an error accessing the crafting system. Please try again later."
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
    
    async def characters_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display the characters menu when clicked from main menu.
        
        Args:
            update: The update containing the callback query
            context: The context object for the bot
        """
        if not update or not update.callback_query:
            return
        
        callback_query = update.callback_query
        user_id = update.effective_user.id
        
        # Get characters the user has met
        try:
            characters = self.db.execute_query(
                "SELECT * FROM user_progress WHERE user_id = ? AND category = 'characters' AND discovered = TRUE",
                (user_id,)
            )
            
            if not characters:
                characters = []
            
            # Create message text
            if characters:
                message_text = (
                    "🧙‍♂️ *Characters You've Met* 🧙‍♀️\n\n"
                    "Here are the characters you've encountered in your journey through Fangen. "
                    "Select a character to learn more about them or interact with them."
                )
                
                # Create buttons for each character
                buttons = []
                for character in characters:
                    character_name = character["item_name"]
                    buttons.append((
                        f"{character_name}",
                        create_callback_data("character_view", {"name": character_name}),
                        "primary"
                    ))
                
                # Add a button to search for characters
                buttons.append((
                    "🔍 Find Characters",
                    create_callback_data("character_search"),
                    "secondary"
                ))
                
                # Add back button
                buttons.append((
                    "⬅️ Back to Main Menu",
                    create_callback_data("main_menu"),
                    "neutral"
                ))
                
                # Create keyboard with optimized layout
                keyboard = create_menu_keyboard(buttons)
                
            else:
                message_text = (
                    "🧙‍♂️ *Characters of Fangen* 🧙‍♀️\n\n"
                    "You haven't met any characters yet! As you explore the world and "
                    "complete quests, you'll encounter various inhabitants of Fangen.\n\n"
                    "Start a quest to begin meeting characters."
                )
                
                # Create keyboard with quest and back buttons
                buttons = [
                    ("🗺️ View Quests", create_callback_data("quest_menu"), "primary"),
                    ("⬅️ Back to Main Menu", create_callback_data("main_menu"), "neutral")
                ]
                keyboard = create_menu_keyboard(buttons)
            
            # Edit the message with the characters menu
            await callback_query.edit_message_text(
                text=message_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error displaying characters menu: {e}", exc_info=True)
            await callback_query.answer("Error displaying characters menu. Please try again.")

    @error_handler(error_type="general", custom_message="I couldn't access the characters. Please try again.")
    async def characters_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /characters command to view characters the user has met.
        
        Args:
            update: The update containing the command
            context: The context object for the bot
        """
        if not update or not update.message:
            return
        
        user_id = update.effective_user.id
        
        # Create a fake callback query to reuse the characters_menu method
        class FakeCallbackQuery:
            async def edit_message_text(self, text, reply_markup, parse_mode):
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            
            async def answer(self, text):
                pass
        
        # Create a fake update with the callback query
        fake_update = Update.de_json(update.to_dict(), context.bot)
        fake_update.callback_query = FakeCallbackQuery()
        
        # Call the characters_menu method
        await self.characters_menu(fake_update, context)
