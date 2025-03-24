#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for UI utilities in ZXI bot
"""

import unittest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ui_utils import (
    create_styled_button,
    optimize_button_layout,
    create_paginated_keyboard,
    create_menu_keyboard,
    create_action_keyboard,
    create_confirmation_keyboard,
    create_choice_keyboard
)

class TestUiUtils(unittest.TestCase):
    """Test cases for UI utilities."""
    
    def test_create_styled_button(self):
        """Test creating styled buttons."""
        # Test primary button
        button = create_styled_button("Test", "test_callback", "primary")
        self.assertEqual(button.text, "🔵 Test")
        self.assertEqual(button.callback_data, "test_callback")
        
        # Test forward button
        button = create_styled_button("Test", "test_callback", "forward")
        self.assertEqual(button.text, "Test »")
        self.assertEqual(button.callback_data, "test_callback")
        
        # Test disabled button
        button = create_styled_button("Test", "test_callback", disabled=True)
        self.assertTrue(button.text.startswith("⚫"))
        self.assertNotEqual(button.callback_data, "test_callback")  # Should be changed for disabled
    
    def test_optimize_button_layout(self):
        """Test optimizing button layout."""
        buttons = [
            ("Short", "short"),
            ("Medium Length", "medium"),
            ("Very Long Button Text", "long"),
            ("Another Short", "short2")
        ]
        
        # Test with default parameters
        layout = optimize_button_layout(buttons)
        self.assertEqual(len(layout), 3)  # Should create 3 rows
        
        # Test with custom parameters
        layout = optimize_button_layout(buttons, max_buttons_per_row=1)
        self.assertEqual(len(layout), 4)  # Should create 4 rows, one for each button
    
    def test_create_menu_keyboard(self):
        """Test creating menu keyboard."""
        # Test with 3-tuple items
        menu_items = [
            ("Item 1", "callback1", "primary"),
            ("Item 2", "callback2", "secondary"),
            ("Item 3", "callback3", "danger")
        ]
        
        keyboard = create_menu_keyboard(menu_items)
        self.assertEqual(len(keyboard.inline_keyboard), 3)
        
        # Test with 2-tuple items for backward compatibility
        menu_items = [
            ("Item 1", "callback1"),
            ("Item 2", "callback2")
        ]
        
        keyboard = create_menu_keyboard(menu_items)
        self.assertEqual(len(keyboard.inline_keyboard), 2)
        
        # Test with back button
        back_button = ("Back", "back_callback")
        keyboard = create_menu_keyboard(menu_items, back_button)
        self.assertEqual(len(keyboard.inline_keyboard), 3)  # 2 items + back button

if __name__ == "__main__":
    unittest.main()
