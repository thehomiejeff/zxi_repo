#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced database utility for ChuzoBot
Supporting quests, inventory, and character interactions
"""

import os
import sqlite3
import json
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

from utils.logger import get_logger
from config import DB_TYPE, DB_NAME, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD

logger = get_logger(__name__)

class Database:
    """Database handler for ChuzoBot."""
    
    def __init__(self):
        """Initialize the database connection.
        
        Sets up the database connection based on configuration settings.
        Supports SQLite and PostgreSQL database types.
        """
        self.conn = None
        self.db_type = DB_TYPE
        self.db_name = DB_NAME
        
        if self.db_type == "sqlite":
            self._connect_sqlite()
        elif self.db_type == "postgres":
            self._connect_postgres()
        else:
            logger.error(f"Unsupported database type: {self.db_type}")
    
    def _connect_sqlite(self):
        """Connect to SQLite database."""
        try:
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)
            
            db_path = os.path.join('data', self.db_name)
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to SQLite database: {db_path}")
            
            # Initialize tables if they don't exist
            self._initialize_tables()
        except Exception as e:
            logger.error(f"Error connecting to SQLite database: {e}", exc_info=True)
    
    def _connect_postgres(self):
        """Connect to PostgreSQL database."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            self.conn = psycopg2.connect(
                dbname=self.db_name,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            logger.info(f"Connected to PostgreSQL database: {self.db_name} on {DB_HOST}:{DB_PORT}")
            
            # Initialize tables if they don't exist
            self._initialize_tables()
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL database: {e}", exc_info=True)
    
    def _initialize_tables(self):
        """Initialize database tables if they don't exist."""
        try:
            cursor = self.conn.cursor()
            
            # Create users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                discovered_lore TEXT DEFAULT '[]',
                state TEXT DEFAULT '{}'
            )
            ''')
            
            # Create user_inventory table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_inventory (
                user_id INTEGER,
                item_name TEXT,
                quantity INTEGER DEFAULT 1,
                acquired_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, item_name),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            ''')
            
            # Create user_quests table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_quests (
                user_id INTEGER,
                quest_name TEXT,
                status TEXT DEFAULT 'active',
                current_scene INTEGER DEFAULT 1,
                started_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_date TIMESTAMP,
                PRIMARY KEY (user_id, quest_name),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            ''')
            
            # Create user_progress table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_progress (
                user_id INTEGER,
                category TEXT,
                item_name TEXT,
                discovered BOOLEAN DEFAULT FALSE,
                discovery_date TIMESTAMP,
                PRIMARY KEY (user_id, category, item_name),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            ''')
            
            # Create user_relationships table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_relationships (
                user_id INTEGER,
                character_name TEXT,
                affinity INTEGER DEFAULT 0,
                first_met TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, character_name),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            ''')
            
            # Create decision_logs table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS decision_logs (
                user_id INTEGER,
                quest_name TEXT,
                scene_id TEXT,
                choice_id TEXT,
                decision_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, quest_name, scene_id, choice_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            ''')
            
            # Create crafting_recipes table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS crafting_recipes (
                result_item TEXT PRIMARY KEY,
                result_rarity TEXT DEFAULT 'common',
                requirements TEXT DEFAULT '{}',
                quest_requirements TEXT DEFAULT '{}'
            )
            ''')
            
            self.conn.commit()
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database tables: {e}", exc_info=True)
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("Database connection closed successfully")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}", exc_info=True)
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a database query.
        
        Args:
            query: SQL query to execute
            params: Parameters for the query
            
        Returns:
            List of dictionaries containing query results
        """
        if not self.conn:
            logger.error("No database connection available")
            return []
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            
            # Check if this is a SELECT query
            if query.strip().upper().startswith("SELECT"):
                if self.db_type == "sqlite":
                    # For SQLite, convert Row objects to dictionaries
                    results = [dict(row) for row in cursor.fetchall()]
                else:
                    # For PostgreSQL, results are already dictionaries
                    results = cursor.fetchall()
                
                return results
            else:
                # For non-SELECT queries, commit and return empty list
                self.conn.commit()
                return []
        except Exception as e:
            logger.error(f"Database error executing query: {e}", exc_info=True)
            return []
    
    def user_exists(self, user_id: int) -> bool:
        """Check if a user exists in the database.
        
        Args:
            user_id: The user ID to check
            
        Returns:
            True if the user exists, False otherwise
        """
        try:
            result = self.execute_query(
                "SELECT 1 FROM users WHERE user_id = ?",
                (user_id,)
            )
            return len(result) > 0
        except Exception as e:
            logger.error(f"Error checking if user exists: {e}", exc_info=True)
            return False
    
    def register_user(self, user_id: int, username: str) -> bool:
        """Register a new user in the database.
        
        Args:
            user_id: The user ID to register
            username: The username to register
            
        Returns:
            True if registration was successful, False otherwise
        """
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.execute_query(
                "INSERT INTO users (user_id, username, first_seen, last_active) VALUES (?, ?, ?, ?)",
                (user_id, username, current_time, current_time)
            )
            logger.info(f"Registered new user: {username} ({user_id})")
            return True
        except Exception as e:
            logger.error(f"Error registering user: {e}", exc_info=True)
            return False
    
    def update_user_activity(self, user_id: int) -> bool:
        """Update the last_active timestamp for a user.
        
        Args:
            user_id: The user ID to update
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.execute_query(
                "UPDATE users SET last_active = ? WHERE user_id = ?",
                (current_time, user_id)
            )
            return True
        except Exception as e:
            logger.error(f"Error updating user activity: {e}", exc_info=True)
            return False
    
    def get_user_state(self, user_id: int) -> Dict:
        """Get the current state for a user.
        
        Args:
            user_id: The user ID to get state for
            
        Returns:
            Dictionary containing user state
        """
        try:
            result = self.execute_query(
                "SELECT state FROM users WHERE user_id = ?",
                (user_id,)
            )
            
            if result and 'state' in result[0]:
                state_str = result[0]['state']
                if state_str:
                    return json.loads(state_str)
            
            return {}
        except Exception as e:
            logger.error(f"Error getting user state: {e}", exc_info=True)
            return {}
    
    def set_user_state(self, user_id: int, state: Dict) -> bool:
        """Set the state for a user.
        
        Args:
            user_id: The user ID to set state for
            state: Dictionary containing user state
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            state_str = json.dumps(state)
            self.execute_query(
                "UPDATE users SET state = ? WHERE user_id = ?",
                (state_str, user_id)
            )
            return True
        except Exception as e:
            logger.error(f"Error setting user state: {e}", exc_info=True)
            return False
    
    def update_user_state(self, user_id: int, key: str, value: Any) -> bool:
        """Update a specific key in the user's state.
        
        Args:
            user_id: The user ID to update state for
            key: The state key to update
            value: The new value for the key
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Get current state
            current_state = self.get_user_state(user_id)
            
            # Update the key
            current_state[key] = value
            
            # Save updated state
            return self.set_user_state(user_id, current_state)
        except Exception as e:
            logger.error(f"Error updating user state: {e}", exc_info=True)
            return False
    
    def can_craft_item(self, user_id: int, item_name: str) -> Tuple[bool, str, Dict]:
        """Check if a user can craft a specific item.
        
        Verifies if the user has the required components in their inventory
        to craft the specified item according to its recipe.
        
        Args:
            user_id: The user ID to check inventory for
            item_name: The name of the item to craft
            
        Returns:
            Tuple containing (can_craft, message, recipe_info)
        """
        # Get recipe
        recipe = self.execute_query(
            "SELECT * FROM crafting_recipes WHERE result_item = ?",
            (item_name,)
        )
        
        if not recipe:
            return False, f"No recipe found for {item_name}.", {}
        
        recipe = recipe[0]
        
        # Check inventory requirements
        requirements = json.loads(recipe["requirements"])
        user_inventory = self.execute_query(
            "SELECT item_name, quantity FROM user_inventory WHERE user_id = ?",
            (user_id,)
        )
        
        if not user_inventory:
            user_inventory = []
        
        # Convert to dict for easier lookup
        inventory_dict = {item["item_name"]: item["quantity"] for item in user_inventory}
        
        missing_items = []
        for req_item, req_quantity in requirements.items():
            if req_item not in inventory_dict or inventory_dict[req_item] < req_quantity:
                missing_items.append(f"{req_item} x{req_quantity}")
        
        # Check quest requirements
        quest_requirements = json.loads(recipe["quest_requirements"])
        
        for quest_name, scene_choices in quest_requirements.items():
            # Check if quest is completed
            quest_completed = self.execute_query(
                "SELECT * FROM user_progress WHERE user_id = ? AND category = 'quests' AND item_name = ? AND discovered = TRUE",
                (user_id, quest_name)
            )
            
            if not quest_completed:
                missing_items.append(f"Quest: {quest_name}")
                continue
            
            # Check specific choices if needed
            for scene, choice in scene_choices.items():
                choice_made = self.execute_query(
                    "SELECT * FROM decision_logs WHERE user_id = ? AND quest_name = ? AND scene_id = ? AND choice_id = ?",
                    (user_id, quest_name, scene, choice)
                )
                
                if not choice_made:
                    missing_items.append(f"Choice: {scene}-{choice} in {quest_name}")
        
        if missing_items:
            return False, f"You are missing the following requirements to craft {item_name}:", {
                "missing": missing_items,
                "recipe": recipe
            }
        
        return True, f"You can craft {item_name}!", {
            "recipe": recipe,
            "inventory": inventory_dict
        }
    
    def craft_item(self, user_id: int, item_name: str) -> Tuple[bool, str]:
        """Craft an item for a user."""
        can_craft, message, details = self.can_craft_item(user_id, item_name)
        
        if not can_craft:
            return False, message
        
        try:
            # Consume required items
            recipe = details["recipe"]
            requirements = json.loads(recipe["requirements"])
            
            for req_item, req_quantity in requirements.items():
                self.execute_query(
                    "UPDATE user_inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?",
                    (req_quantity, user_id, req_item)
                )
            
            # Add crafted item
            result_rarity = recipe["result_rarity"]
            
            # Check if item already exists in inventory
            existing_item = self.execute_query(
                "SELECT * FROM user_inventory WHERE user_id = ? AND item_name = ?",
                (user_id, item_name)
            )
            
            if existing_item:
                self.execute_query(
                    "UPDATE user_inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_name = ?",
                    (user_id, item_name)
                )
            else:
                self.execute_query(
                    "INSERT INTO user_inventory (user_id, item_name, rarity, quantity) VALUES (?, ?, ?, 1)",
                    (user_id, item_name, result_rarity)
                )
            
            return True, f"Successfully crafted {item_name} ({result_rarity})!"
        except Exception as e:
            logger.error(f"Error crafting item: {e}", exc_info=True)
            return False, f"Error crafting item: {str(e)}"
