#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UI Utilities for ZXI Telegram Bot

This module provides utilities for creating consistent UI elements,
optimizing button layouts, implementing pagination, and managing button states.
"""

import logging
import math
from typing import List, Dict, Any, Optional, Union, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from utils.callback_utils import create_callback_data

# Set up logging
logger = logging.getLogger(__name__)

# Button style definitions
BUTTON_STYLES = {
    "primary": "🔵 ",    # Main actions
    "secondary": "⚪ ",  # Alternative actions
    "danger": "🔴 ",     # Destructive actions
    "success": "✅ ",    # Completion actions
    "info": "ℹ️ ",       # Informational actions
    "back": "« ",        # Navigation back
    "forward": " »",     # Navigation forward
    "disabled": "⚫ "    # Disabled actions
}

def create_styled_button(
    text: str,
    callback_data: str,
    style: str = "secondary",
    disabled: bool = False
) -> InlineKeyboardButton:
    """
    Create a styled button with consistent formatting.
    
    Args:
        text: The button text
        callback_data: The callback data for the button
        style: The button style (primary, secondary, danger, etc.)
        disabled: Whether the button is disabled
        
    Returns:
        An InlineKeyboardButton with styled text
    """
    # If disabled, override style
    if disabled:
        style = "disabled"
        # For disabled buttons, use a special callback that does nothing
        callback_data = create_callback_data("disabled")
    
    # Get style prefix and suffix
    prefix = BUTTON_STYLES.get(style, "")
    suffix = BUTTON_STYLES.get("forward", "") if style == "forward" else ""
    
    # Create the button with styled text
    return InlineKeyboardButton(
        f"{prefix}{text}{suffix}",
        callback_data=callback_data
    )

def optimize_button_layout(
    buttons: List[Tuple[str, str]],
    max_buttons_per_row: int = 2,
    max_text_length_per_row: int = 30,
    style: str = "secondary"
) -> List[List[InlineKeyboardButton]]:
    """
    Optimize button layout based on text length and screen size.
    
    Args:
        buttons: List of (text, callback_data) tuples
        max_buttons_per_row: Maximum number of buttons per row
        max_text_length_per_row: Maximum combined text length per row
        style: Default button style
        
    Returns:
        A list of rows, where each row is a list of InlineKeyboardButton objects
    """
    rows = []
    current_row = []
    current_row_length = 0
    
    for text, callback_data in buttons:
        # If adding this button would make the row too long, start a new row
        if (current_row_length + len(text) > max_text_length_per_row and current_row) or \
           (len(current_row) >= max_buttons_per_row):
            rows.append(current_row)
            current_row = []
            current_row_length = 0
        
        # Add button to current row
        current_row.append(create_styled_button(text, callback_data, style))
        current_row_length += len(text)
    
    # Add any remaining buttons
    if current_row:
        rows.append(current_row)
    
    return rows

def create_paginated_keyboard(
    items: Union[List[Dict[str, Any]], List[Tuple[str, str, Optional[str]]]],
    page: int = 0,
    items_per_page: int = 6,
    id_key: str = "id",
    name_key: str = "name",
    callback_prefix: str = "item",
    show_pagination: bool = True
) -> Tuple[InlineKeyboardMarkup, int, int]:
    """
    Create a paginated keyboard for a list of items.
    
    Args:
        items: List of item dictionaries or (text, callback_data, style) tuples
        page: Current page number (0-based)
        items_per_page: Number of items to show per page
        id_key: Key for item ID in the dictionaries (used only for dict items)
        name_key: Key for item name in the dictionaries (used only for dict items)
        callback_prefix: Prefix for callback data (used only for dict items)
        show_pagination: Whether to show pagination controls
        
    Returns:
        A tuple of (InlineKeyboardMarkup, total_pages, current_page)
    """
    # Calculate pagination
    total_items = len(items)
    total_pages = math.ceil(total_items / items_per_page) if total_items > 0 else 1
    
    # Ensure page is within bounds
    page = max(0, min(page, total_pages - 1))
    
    # Get items for current page
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    page_items = items[start_idx:end_idx]
    
    # Create buttons for items
    item_buttons = []
    
    # Check if items are dictionaries or tuples
    if page_items and isinstance(page_items[0], dict):
        # Items are dictionaries
        for item in page_items:
            item_id = item.get(id_key, "")
            item_name = item.get(name_key, "Unknown")
            callback_data = create_callback_data(callback_prefix, id=item_id, name=item_name)
            item_buttons.append((item_name, callback_data))
    else:
        # Items are already (text, callback_data, style) tuples
        for item in page_items:
            if len(item) >= 2:  # Ensure tuple has at least text and callback_data
                text, callback_data = item[0], item[1]
                item_buttons.append((text, callback_data))
    
    # Optimize layout for item buttons
    keyboard = optimize_button_layout(item_buttons)
    
    # Add pagination controls if needed
    if show_pagination and total_pages > 1:
        pagination_row = []
        
        # Previous page button
        if page > 0:
            prev_callback = create_callback_data("page", action=callback_prefix, page=page-1)
            pagination_row.append(create_styled_button("Previous", prev_callback, "back"))
        
        # Page indicator
        page_indicator = f"Page {page+1}/{total_pages}"
        page_info_callback = create_callback_data("page_info")
        pagination_row.append(create_styled_button(page_indicator, page_info_callback, "info"))
        
        # Next page button
        if page < total_pages - 1:
            next_callback = create_callback_data("page", action=callback_prefix, page=page+1)
            pagination_row.append(create_styled_button("Next", next_callback, "forward"))
        
        keyboard.append(pagination_row)
    
    return InlineKeyboardMarkup(keyboard), total_pages, page

def create_menu_keyboard(
    menu_items: List[Tuple[str, str, Optional[str]]],
    back_button: Optional[Tuple[str, str]] = None
) -> InlineKeyboardMarkup:
    """
    Create a menu keyboard with styled buttons.
    
    Args:
        menu_items: List of (text, callback_data, style) tuples
        back_button: Optional (text, callback_data) tuple for a back button
        
    Returns:
        An InlineKeyboardMarkup for the menu
    """
    keyboard = []
    
    # Add menu items
    for item in menu_items:
        # Handle both 2-tuple and 3-tuple formats for backward compatibility
        if len(item) == 3:
            text, callback_data, style = item
            style = style or "secondary"
        elif len(item) == 2:
            text, callback_data = item
            style = "secondary"
        else:
            logger.warning(f"Invalid menu item format: {item}")
            continue
            
        keyboard.append([create_styled_button(text, callback_data, style)])
    
    # Add back button if provided
    if back_button:
        text, callback_data = back_button
        keyboard.append([create_styled_button(text, callback_data, "back")])
    
    return InlineKeyboardMarkup(keyboard)

def create_action_keyboard(
    primary_action: Optional[Tuple[str, str]] = None,
    secondary_actions: Optional[List[Tuple[str, str]]] = None,
    back_action: Optional[Tuple[str, str]] = None
) -> InlineKeyboardMarkup:
    """
    Create an action keyboard with primary, secondary, and back actions.
    
    Args:
        primary_action: Optional (text, callback_data) tuple for primary action
        secondary_actions: List of (text, callback_data) tuples for secondary actions
        back_action: Optional (text, callback_data) tuple for back action
        
    Returns:
        An InlineKeyboardMarkup for the actions
    """
    keyboard = []
    
    # Add primary action
    if primary_action:
        text, callback_data = primary_action
        keyboard.append([create_styled_button(text, callback_data, "primary")])
    
    # Add secondary actions
    if secondary_actions:
        for text, callback_data in secondary_actions:
            keyboard.append([create_styled_button(text, callback_data, "secondary")])
    
    # Add back action
    if back_action:
        text, callback_data = back_action
        keyboard.append([create_styled_button(text, callback_data, "back")])
    
    return InlineKeyboardMarkup(keyboard)

def create_confirmation_keyboard(
    confirm_text: str = "Confirm",
    cancel_text: str = "Cancel",
    confirm_callback: Optional[str] = None,
    cancel_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Create a confirmation keyboard with confirm and cancel buttons.
    
    Args:
        confirm_text: Text for confirm button
        cancel_text: Text for cancel button
        confirm_callback: Callback data for confirm button
        cancel_callback: Callback data for cancel button
        
    Returns:
        An InlineKeyboardMarkup for confirmation
    """
    confirm_callback = confirm_callback or create_callback_data("confirm")
    cancel_callback = cancel_callback or create_callback_data("cancel")
    
    keyboard = [
        [
            create_styled_button(confirm_text, confirm_callback, "primary"),
            create_styled_button(cancel_text, cancel_callback, "danger")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def create_choice_keyboard(
    choices: List[Dict[str, Any]],
    choice_id_key: str = "id",
    choice_text_key: str = "text",
    abandon_text: Optional[str] = "Abandon",
    abandon_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Create a keyboard for quest choices or similar selection scenarios.
    
    Args:
        choices: List of choice dictionaries
        choice_id_key: Key for choice ID in the dictionaries
        choice_text_key: Key for choice text in the dictionaries
        abandon_text: Text for abandon button, or None to omit
        abandon_callback: Callback data for abandon button
        
    Returns:
        An InlineKeyboardMarkup for choices
    """
    keyboard = []
    
    # Add choice buttons
    for choice in choices:
        choice_id = choice.get(choice_id_key, "")
        choice_text = choice.get(choice_text_key, "Unknown")
        callback_data = create_callback_data("quest_choice", id=choice_id)
        keyboard.append([create_styled_button(choice_text, callback_data, "secondary")])
    
    # Add abandon button if provided
    if abandon_text and abandon_callback:
        keyboard.append([create_styled_button(abandon_text, abandon_callback, "danger")])
    
    return InlineKeyboardMarkup(keyboard)
