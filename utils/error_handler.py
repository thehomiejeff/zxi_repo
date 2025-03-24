#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Error Handling Utilities for ZXI Telegram Bot

This module provides utilities for standardized error handling and user-friendly error messages.
"""

import logging
import traceback
from typing import Tuple, Optional, Callable, Any, Dict, Union
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Set up logging
logger = logging.getLogger(__name__)

# Error message templates
ERROR_MESSAGES = {
    "general": "I encountered an issue while processing your request. Please try again later.",
    "callback": "I couldn't process that button press. Please try a different option.",
    "database": "There was a problem accessing your data. Please try again later.",
    "not_found": "I couldn't find what you were looking for.",
    "permission": "You don't have permission to perform this action.",
    "timeout": "The operation timed out. Please try again.",
    "validation": "The information provided is not valid.",
    "rate_limit": "You're doing that too often. Please wait a moment and try again."
}

async def handle_error(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    error_type: str = "general",
    exception: Optional[Exception] = None,
    custom_message: Optional[str] = None
) -> None:
    """
    Handle errors in a standardized way.
    
    Args:
        update: The update that caused the error
        context: The context object
        error_type: The type of error (used to select an appropriate message)
        exception: The exception that was raised, if any
        custom_message: A custom error message to display to the user
    """
    # Log the error
    if exception:
        logger.error(f"Error type: {error_type}, Exception: {str(exception)}")
        logger.debug(traceback.format_exc())
    else:
        logger.error(f"Error type: {error_type}")
    
    # Get appropriate error message
    message = custom_message or ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["general"])
    
    # Create error keyboard with helpful options
    keyboard = [
        [InlineKeyboardButton("🔄 Try Again", callback_data='{"action":"retry"}')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='{"action":"main_menu"}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send error message to user
    try:
        if update and update.callback_query:
            # If this was a callback query, edit the message
            try:
                await update.callback_query.edit_message_text(
                    text=f"⚠️ {message}",
                    reply_markup=reply_markup
                )
            except Exception as e:
                # If editing fails, answer the callback and send a new message
                logger.warning(f"Failed to edit message: {e}")
                await update.callback_query.answer("An error occurred")
                if update.effective_chat:
                    await update.effective_chat.send_message(
                        text=f"⚠️ {message}",
                        reply_markup=reply_markup
                    )
        elif update and update.message:
            # If this was a message, reply to it
            await update.message.reply_text(
                text=f"⚠️ {message}",
                reply_markup=reply_markup
            )
        elif update and update.effective_chat:
            # If we can't reply to anything specific, send a new message
            await update.effective_chat.send_message(
                text=f"⚠️ {message}",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")

def error_handler(error_type: str = "general", custom_message: Optional[str] = None):
    """
    Decorator for error handling in command and callback handlers.
    
    Args:
        error_type: The type of error (used to select an appropriate message)
        custom_message: A custom error message to display to the user
        
    Returns:
        A decorator function
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if this is a method (with self) or a standalone function
            if len(args) >= 1 and hasattr(args[0], '__class__') and not isinstance(args[0], Update):
                # This is a method call (with self)
                self, update, context, *rest_args = args
                try:
                    return await func(self, update, context, *rest_args, **kwargs)
                except Exception as e:
                    await handle_error(update, context, error_type, e, custom_message)
                    # Return None instead of re-raising to prevent global error handler from being triggered
                    return None
            else:
                # This is a standalone function call
                update, context, *rest_args = args
                try:
                    return await func(update, context, *rest_args, **kwargs)
                except Exception as e:
                    await handle_error(update, context, error_type, e, custom_message)
                    # Return None instead of re-raising to prevent global error handler from being triggered
                    return None
        return wrapper
    return decorator

class ErrorContext:
    """
    Context manager for error handling.
    
    Examples:
        # For handling errors in async functions with update and context
        async with ErrorContext(update, context, "database"):
            # Code that might raise an exception
            db.execute_query("SELECT * FROM users")
            
        # For handling errors with just a database object
        with ErrorContext(db, error_type="database"):
            # Code that might raise an exception
            db.execute_query("SELECT * FROM users")
    """
    
    def __init__(
        self,
        first_arg: Union[Update, Any],
        second_arg: Optional[Union[ContextTypes.DEFAULT_TYPE, str]] = None,
        error_type: str = "general",
        custom_message: Optional[str] = None
    ):
        # Check if this is being used with update and context
        if isinstance(first_arg, Update):
            self.update = first_arg
            self.context = second_arg
            self.error_type = error_type
            self.custom_message = custom_message
            self.db_only = False
        else:
            # This is being used with just a database object
            self.db = first_arg
            self.error_type = second_arg or "database"
            self.custom_message = error_type if isinstance(error_type, str) and error_type != "general" else custom_message
            self.db_only = True
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and not self.db_only:
            await handle_error(self.update, self.context, self.error_type, exc_val, self.custom_message)
            return True  # Suppress the exception
        return False
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and self.db_only:
            logger.error(f"Database error: {str(exc_val)}")
            return True  # Suppress the exception
        return False

# Global error handler for the application
async def global_error_handler(update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler for the application.
    
    Args:
        update: The update that caused the error
        context: The context object containing the error
    """
    # Extract the exception info
    error = context.error
    
    # Log the error
    logger.error(f"Global error handler caught: {str(error)}")
    logger.debug(traceback.format_exc())
    
    # Determine error type
    error_type = "general"
    error_str = str(error).lower()
    if "database" in error_str:
        error_type = "database"
    elif "not found" in error_str:
        error_type = "not_found"
    elif "timeout" in error_str:
        error_type = "timeout"
    elif "permission" in error_str:
        error_type = "permission"
    elif "rate limit" in error_str:
        error_type = "rate_limit"
    elif "validation" in error_str:
        error_type = "validation"
    
    # Handle the error
    if update:
        await handle_error(update, context, error_type, error)
