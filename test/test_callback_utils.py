#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for callback handling in ZXI bot
"""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.callback_utils import (
    create_callback_data,
    parse_callback_data,
    validate_callback_data,
    MAX_CALLBACK_DATA_LENGTH
)

class TestCallbackUtils(unittest.TestCase):
    """Test cases for callback utilities."""
    
    def test_create_callback_data(self):
        """Test creating callback data."""
        # Test basic callback data
        callback_data = create_callback_data("test_action")
        self.assertEqual(json.loads(callback_data), {"action": "test_action"})
        
        # Test with additional parameters
        callback_data = create_callback_data("test_action", id=123, name="Test")
        parsed = json.loads(callback_data)
        self.assertEqual(parsed["action"], "test_action")
        self.assertEqual(parsed["id"], 123)
        self.assertEqual(parsed["name"], "Test")
        
        # Test length handling with long name
        long_name = "A" * 100  # Very long name
        callback_data = create_callback_data("test_action", name=long_name)
        parsed = json.loads(callback_data)
        self.assertEqual(parsed["action"], "test_action")
        self.assertLess(len(callback_data), MAX_CALLBACK_DATA_LENGTH)
    
    def test_parse_callback_data(self):
        """Test parsing callback data."""
        # Test parsing JSON callback data
        callback_data = '{"action": "test_action", "id": 123}'
        parsed = parse_callback_data(callback_data)
        self.assertEqual(parsed["action"], "test_action")
        self.assertEqual(parsed["id"], 123)
        
        # Test backward compatibility with old format
        callback_data = "old_value"
        parsed = parse_callback_data(callback_data)
        self.assertEqual(parsed["action"], "old")
        self.assertEqual(parsed["name"], "value")
    
    def test_validate_callback_data(self):
        """Test validating callback data."""
        # Test valid data
        data = {"action": "test_action"}
        self.assertTrue(validate_callback_data(data))
        
        # Test valid data with expected action
        self.assertTrue(validate_callback_data(data, "test_action"))
        
        # Test invalid action
        self.assertFalse(validate_callback_data(data, "wrong_action"))
        
        # Test missing action
        data = {"id": 123}
        self.assertFalse(validate_callback_data(data))

if __name__ == "__main__":
    unittest.main()
