#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Callback Utilities for ZXI Telegram Bot

This module provides utilities for handling callback data in a structured way,
including serialization, deserialization, validation, and ID-based reference.
"""

import json
import logging
from typing import Dict, Any, Optional, Union, List, Tuple

# Set up logging
logger = logging.getLogger(__name__)

# Maximum callback data length allowed by Telegram
MAX_CALLBACK_DATA_LENGTH = 64

class CallbackDataError(Exception):
    """Exception raised for callback data errors."""
    pass

def create_callback_data(action: str, **kwargs) -> str:
    """
    Create structured callback data using JSON serialization.
    
    Args:
        action: The action identifier (e.g., "quest_view", "lore_entry")
        **kwargs: Additional data to include in the callback
        
    Returns:
        A JSON string containing the callback data
        
    Raises:
        CallbackDataError: If the resulting callback data exceeds Telegram's limit
    """
    # Create data dictionary with action and additional parameters
    data = {"action": action, **kwargs}
    
    # Serialize to JSON
    callback_data = json.dumps(data)
    
    # Check length
    if len(callback_data) > MAX_CALLBACK_DATA_LENGTH:
        # Try to use shorter IDs instead of full names if available
        if "name" in kwargs and len(kwargs["name"]) > 10:
            # Log the issue
            logger.warning(f"Callback data too long: {callback_data}")
            
            # Use a shorter representation
            if "id" in kwargs:
                # If ID is already provided, use it directly
                data = {"action": action, "id": kwargs["id"]}
            else:
                # Otherwise, use a hash or first few characters as a shorter identifier
                short_id = str(hash(kwargs["name"]) % 10000)  # Simple hash to get a 4-digit number
                data = {"action": action, "short_id": short_id, "name_prefix": kwargs["name"][:5]}
            
            # Re-serialize with shorter data
            callback_data = json.dumps(data)
            
            # Check length again
            if len(callback_data) > MAX_CALLBACK_DATA_LENGTH:
                # If still too long, use minimal data
                data = {"action": action, "id": short_id}
                callback_data = json.dumps(data)
                
                # Final check
                if len(callback_data) > MAX_CALLBACK_DATA_LENGTH:
                    logger.error(f"Unable to shorten callback data sufficiently: {len(callback_data)} bytes")
                    # Return a minimal valid callback as fallback
                    return json.dumps({"action": action})
        else:
            logger.warning(f"Callback data too long: {callback_data}")
            # Return a minimal valid callback as fallback
            return json.dumps({"action": action})
    
    return callback_data

def parse_callback_data(callback_data: str) -> Dict[str, Any]:
    """
    Parse JSON-serialized callback data.
    
    Args:
        callback_data: The callback data string to parse
        
    Returns:
        A dictionary containing the parsed callback data
        
    Raises:
        CallbackDataError: If the callback data cannot be parsed
    """
    try:
        # For backward compatibility, check if it's using the old format
        if "_" in callback_data and not callback_data.startswith("{"):
            # Old format: prefix_value
            parts = callback_data.split("_", 1)
            if len(parts) == 2:
                prefix, value = parts
                return {"action": prefix, "name": value}
            else:
                return {"action": callback_data}
        
        # New format: JSON
        return json.loads(callback_data)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse callback data: {callback_data}")
        raise CallbackDataError(f"Invalid callback data format: {e}")

def validate_callback_data(data: Dict[str, Any], expected_action: Optional[str] = None) -> bool:
    """
    Validate parsed callback data.
    
    Args:
        data: The parsed callback data dictionary
        expected_action: Optional action to validate against
        
    Returns:
        True if the data is valid, False otherwise
    """
    # Check if action is present
    if "action" not in data:
        logger.warning("Callback data missing 'action' field")
        return False
    
    # Check if action matches expected action
    if expected_action and data["action"] != expected_action:
        logger.warning(f"Expected action '{expected_action}', got '{data['action']}'")
        return False
    
    return True

def get_action_from_callback(callback_data: str) -> str:
    """
    Extract the action from callback data.
    
    Args:
        callback_data: The callback data string
        
    Returns:
        The action string
        
    Raises:
        CallbackDataError: If the callback data cannot be parsed
    """
    try:
        data = parse_callback_data(callback_data)
        return data.get("action", "")
    except CallbackDataError:
        # For backward compatibility
        if "_" in callback_data:
            return callback_data.split("_")[0]
        return ""

# Convenience functions for common callback types

def create_quest_view_callback(quest_name: str, quest_id: Optional[int] = None) -> str:
    """Create callback data for viewing a quest."""
    kwargs = {"name": quest_name}
    if quest_id is not None:
        kwargs["id"] = quest_id
    return create_callback_data("quest_view", **kwargs)

def create_quest_start_callback(quest_name: str, quest_id: Optional[int] = None) -> str:
    """Create callback data for starting a quest."""
    kwargs = {"name": quest_name}
    if quest_id is not None:
        kwargs["id"] = quest_id
    return create_callback_data("quest_start", **kwargs)

def create_quest_choice_callback(choice_id: Union[str, int]) -> str:
    """Create callback data for selecting a quest choice."""
    return create_callback_data("quest_choice", id=choice_id)

def create_lore_category_callback(category: str) -> str:
    """Create callback data for selecting a lore category."""
    return create_callback_data("lore_cat", name=category)

def create_lore_entry_callback(entry_name: str, entry_id: Optional[int] = None) -> str:
    """Create callback data for viewing a lore entry."""
    kwargs = {"name": entry_name}
    if entry_id is not None:
        kwargs["id"] = entry_id
    return create_callback_data("lore_entry", **kwargs)

def create_navigation_callback(action: str, page: int = 0) -> str:
    """Create callback data for navigation actions."""
    return create_callback_data(action, page=page)

# ID-based reference system for long names

class IdReferenceManager:
    """
    Manages ID-based references for long names to keep callback data short.
    """
    
    def __init__(self):
        self._name_to_id: Dict[str, int] = {}
        self._id_to_name: Dict[int, str] = {}
        self._next_id: int = 1
    
    def get_id(self, name: str) -> int:
        """
        Get the ID for a name, creating a new one if it doesn't exist.
        
        Args:
            name: The name to get an ID for
            
        Returns:
            The ID for the name
        """
        if name not in self._name_to_id:
            self._name_to_id[name] = self._next_id
            self._id_to_name[self._next_id] = name
            self._next_id += 1
        
        return self._name_to_id[name]
    
    def get_name(self, id_: int) -> Optional[str]:
        """
        Get the name for an ID.
        
        Args:
            id_: The ID to get the name for
            
        Returns:
            The name for the ID, or None if the ID doesn't exist
        """
        return self._id_to_name.get(id_)
    
    def clear(self):
        """Clear all references."""
        self._name_to_id.clear()
        self._id_to_name.clear()
        self._next_id = 1

# Create global reference managers for different types
quest_reference_manager = IdReferenceManager()
lore_reference_manager = IdReferenceManager()
character_reference_manager = IdReferenceManager()
