# -*- coding: utf-8 -*-

"""
Quest Manager for ChuzoBot
Handles quest progression, dialogue choices, and inventory integration
"""

import json
import random
from typing import Dict, List, Optional, Any, Tuple

from utils.logger import get_logger
from utils.database import Database
from utils.fangen_lore_manager import FangenLoreManager

logger = get_logger(__name__)

class QuestManager:
    """Manages quests, dialogues, and player progression."""
    
    def __init__(self, db: Database, lore_manager: FangenLoreManager):
        """Initialize the QuestManager."""
        self.db = db
        self.lore_manager = lore_manager
        self.active_quests = {}  # user_id -> active_quest_info
    
    def get_available_quests(self, user_id: int) -> List[Dict]:
        """Get available quests for a user."""
        # Get user progress data
        user_progress = self.db.execute_query(
            "SELECT * FROM user_progress WHERE user_id = ?",
            (user_id,)
        )
        
        completed_quests = [
            item['item_name'] for item in user_progress 
            if item['category'] == 'quests' and item['discovered']
        ]
        
        # Get all quests from lore manager
        all_quests = []
        for quest_name in self.lore_manager.get_quests():
            quest_info = self.lore_manager.get_quest_info(quest_name)
            if quest_info:
                quest = {
                    "name": quest_name,
                    "description": quest_info.get("description", ""),
                    "completed": quest_name in completed_quests
                }
                all_quests.append(quest)
        
        return all_quests
    
    def get_available_recipes(self, user_id: int) -> List[Dict]:
        """Get available crafting recipes for a user.
        
        Args:
            user_id: The user ID to check recipes for
            
        Returns:
            List of available recipe dictionaries with name, requirements, and rarity
        """
        # Get all recipes from database
        recipes = self.db.execute_query(
            "SELECT * FROM crafting_recipes"
        )
        
        if not recipes:
            return []
            
        # Get user's quest progress to check quest requirements
        user_progress = self.db.execute_query(
            "SELECT * FROM user_progress WHERE user_id = ? AND category = 'quests'",
            (user_id,)
        )
        
        completed_quests = [
            item['item_name'] for item in user_progress if item['discovered']
        ]
        
        # Get user's inventory to show available materials
        user_inventory = self.db.execute_query(
            "SELECT item_name, quantity FROM user_inventory WHERE user_id = ?",
            (user_id,)
        )
        
        inventory_dict = {item["item_name"]: item["quantity"] for item in user_inventory}
        
        # Filter recipes based on quest requirements
        available_recipes = []
        for recipe in recipes:
            quest_requirements = json.loads(recipe["quest_requirements"])
            
            # Check if all required quests are completed
            requirements_met = True
            for quest_name in quest_requirements:
                if quest_name not in completed_quests:
                    requirements_met = False
                    break
                    
            if requirements_met:
                # Add recipe with material availability info
                material_requirements = json.loads(recipe["requirements"])
                materials_status = {}
                
                for item_name, required_qty in material_requirements.items():
                    available_qty = inventory_dict.get(item_name, 0)
                    materials_status[item_name] = {
                        "required": required_qty,
                        "available": available_qty,
                        "sufficient": available_qty >= required_qty
                    }
                
                available_recipes.append({
                    "name": recipe["result_item"],
                    "rarity": recipe["result_rarity"],
                    "requirements": material_requirements,
                    "materials_status": materials_status,
                    "can_craft": all(status["sufficient"] for status in materials_status.values())
                })
                
        return available_recipes
    
    def start_quest(self, user_id: int, quest_name: str) -> Tuple[bool, str, Dict]:
        """Start a quest for a user.
        
        Initializes a new quest for the user if they are not already on one,
        and returns the first scene of the quest.
        
        Args:
            user_id: The user ID to start the quest for
            quest_name: The name of the quest to start
            
        Returns:
            Tuple containing (success, message, scene_data)
        """
        # Check if user is already on a quest
        if user_id in self.active_quests:
            return False, "You are already on a quest. Use /active to see your current quest or /abandon to quit it.", {}
        
        # Check if quest exists
        quest_info = self.lore_manager.get_quest_info(quest_name)
        if not quest_info:
            return False, f"Quest '{quest_name}' not found.", {}
        
        # Initialize quest state
        self.active_quests[user_id] = {
            "quest_name": quest_name,
            "current_scene": 1,
            "inventory": {},
            "state": {}
        }
        
        # Record in database
        current_time = self.db.execute_query("SELECT datetime('now') as time")[0]["time"]
        self.db.execute_query(
            "INSERT OR REPLACE INTO user_quests (user_id, quest_name, status, current_scene, started_date) VALUES (?, ?, ?, ?, ?)",
            (user_id, quest_name, "active", 1, current_time)
        )
        
        # Get first scene
        return self._get_scene_data(user_id)
    
    def _get_scene_data(self, user_id: int) -> Tuple[bool, str, Dict]:
        """Get the current scene data for a user's active quest.
        
        Args:
            user_id: The user ID to get scene data for
            
        Returns:
            Tuple containing (success, message, scene_data)
        """
        if user_id not in self.active_quests:
            return False, "You are not currently on a quest.", {}
        
        quest_state = self.active_quests[user_id]
        quest_name = quest_state["quest_name"]
        current_scene = quest_state["current_scene"]
        
        # Get quest info
        quest_info = self.lore_manager.get_quest_info(quest_name)
        if not quest_info:
            return False, f"Quest '{quest_name}' not found.", {}
        
        # Get scene data
        scenes = quest_info.get("scenes", {})
        scene_key = f"scene_{current_scene}"
        
        if scene_key not in scenes:
            return False, f"Scene {current_scene} not found for quest '{quest_name}'.", {}
        
        scene_data = scenes[scene_key]
        
        # Process any dynamic content in the scene
        scene_data = self._process_dynamic_content(scene_data, quest_state)
        
        return True, "", scene_data
    
    def _process_dynamic_content(self, scene_data: Dict, quest_state: Dict) -> Dict:
        """Process any dynamic content in the scene data.
        
        Handles variable substitution, conditional content, etc.
        
        Args:
            scene_data: The scene data to process
            quest_state: The current quest state
            
        Returns:
            Processed scene data
        """
        # Make a copy to avoid modifying the original
        processed_data = dict(scene_data)
        
        # Process narrative text
        if "narrative" in processed_data:
            narrative = processed_data["narrative"]
            
            # Replace variables
            for key, value in quest_state["state"].items():
                placeholder = f"{{{key}}}"
                if placeholder in narrative:
                    narrative = narrative.replace(placeholder, str(value))
            
            processed_data["narrative"] = narrative
        
        # Process choices
        if "choices" in processed_data:
            processed_choices = []
            
            for choice in processed_data["choices"]:
                # Check if choice has conditions
                if "conditions" in choice:
                    conditions_met = True
                    
                    for condition_key, condition_value in choice["conditions"].items():
                        if quest_state["state"].get(condition_key) != condition_value:
                            conditions_met = False
                            break
                    
                    if not conditions_met:
                        continue
                
                # Process choice text
                choice_text = choice["text"]
                for key, value in quest_state["state"].items():
                    placeholder = f"{{{key}}}"
                    if placeholder in choice_text:
                        choice_text = choice_text.replace(placeholder, str(value))
                
                processed_choice = dict(choice)
                processed_choice["text"] = choice_text
                processed_choices.append(processed_choice)
            
            processed_data["choices"] = processed_choices
        
        return processed_data
    
    def make_choice(self, user_id: int, choice_id: str) -> Tuple[bool, str, Dict]:
        """Make a choice in the current quest scene.
        
        Args:
            user_id: The user ID making the choice
            choice_id: The ID of the choice being made
            
        Returns:
            Tuple containing (success, message, next_scene_data)
        """
        if user_id not in self.active_quests:
            return False, "You are not currently on a quest.", {}
        
        quest_state = self.active_quests[user_id]
        quest_name = quest_state["quest_name"]
        current_scene = quest_state["current_scene"]
        
        # Get quest info
        quest_info = self.lore_manager.get_quest_info(quest_name)
        if not quest_info:
            return False, f"Quest '{quest_name}' not found.", {}
        
        # Get scene data
        scenes = quest_info.get("scenes", {})
        scene_key = f"scene_{current_scene}"
        
        if scene_key not in scenes:
            return False, f"Scene {current_scene} not found for quest '{quest_name}'.", {}
        
        scene_data = scenes[scene_key]
        
        # Find the chosen choice
        chosen_choice = None
        for choice in scene_data.get("choices", []):
            if choice.get("id") == choice_id:
                chosen_choice = choice
                break
        
        if not chosen_choice:
            return False, f"Choice '{choice_id}' not found in current scene.", {}
        
        # Record the decision
        self.db.execute_query(
            "INSERT OR REPLACE INTO decision_logs (user_id, quest_name, scene_id, choice_id, decision_date) VALUES (?, ?, ?, ?, datetime('now'))",
            (user_id, quest_name, scene_key, choice_id)
        )
        
        # Process choice outcomes
        if "outcomes" in chosen_choice:
            outcomes = chosen_choice["outcomes"]
            
            # Update state variables
            if "state_changes" in outcomes:
                for key, value in outcomes["state_changes"].items():
                    quest_state["state"][key] = value
            
            # Add items to inventory
            if "items_gained" in outcomes:
                for item_name, quantity in outcomes["items_gained"].items():
                    if item_name in quest_state["inventory"]:
                        quest_state["inventory"][item_name] += quantity
                    else:
                        quest_state["inventory"][item_name] = quantity
            
            # Remove items from inventory
            if "items_lost" in outcomes:
                for item_name, quantity in outcomes["items_lost"].items():
                    if item_name in quest_state["inventory"]:
                        quest_state["inventory"][item_name] -= quantity
                        if quest_state["inventory"][item_name] <= 0:
                            del quest_state["inventory"][item_name]
        
        # Move to next scene
        next_scene = chosen_choice.get("next_scene")
        if next_scene:
            quest_state["current_scene"] = next_scene
            
            # Update database
            self.db.execute_query(
                "UPDATE user_quests SET current_scene = ? WHERE user_id = ? AND quest_name = ?",
                (next_scene, user_id, quest_name)
            )
            
            # Check if this is the final scene
            if next_scene == "complete":
                return self._complete_quest(user_id)
            
            # Get next scene data
            return self._get_scene_data(user_id)
        
        return False, "No next scene specified for this choice.", {}
    
    def _complete_quest(self, user_id: int) -> Tuple[bool, str, Dict]:
        """Complete a quest for a user.
        
        Args:
            user_id: The user ID completing the quest
            
        Returns:
            Tuple containing (success, message, completion_data)
        """
        if user_id not in self.active_quests:
            return False, "You are not currently on a quest.", {}
        
        quest_state = self.active_quests[user_id]
        quest_name = quest_state["quest_name"]
        
        # Get quest info
        quest_info = self.lore_manager.get_quest_info(quest_name)
        if not quest_info:
            return False, f"Quest '{quest_name}' not found.", {}
        
        # Update database
        current_time = self.db.execute_query("SELECT datetime('now') as time")[0]["time"]
        self.db.execute_query(
            "UPDATE user_quests SET status = ?, completed_date = ? WHERE user_id = ? AND quest_name = ?",
            ("completed", current_time, user_id, quest_name)
        )
        
        # Record discovery
        self.db.record_discovery(user_id, "quests", quest_name)
        
        # Process rewards
        rewards = quest_info.get("rewards", {})
        reward_text = "Quest completed! You've earned:\n"
        
        # XP rewards
        if "xp" in rewards:
            xp = rewards["xp"]
            reward_text += f"• {xp} XP\n"
            # TODO: Implement XP system
        
        # Item rewards
        if "items" in rewards:
            for item_name, quantity in rewards["items"].items():
                reward_text += f"• {quantity}x {item_name}\n"
                
                # Add to user inventory
                item_info = self.lore_manager.get_item(item_name)
                rarity = "common"
                if item_info and isinstance(item_info, dict):
                    rarity = item_info.get("rarity", "common")
                
                # Check if item already exists in inventory
                existing_item = self.db.execute_query(
                    "SELECT quantity FROM user_inventory WHERE user_id = ? AND item_name = ?",
                    (user_id, item_name)
                )
                
                if existing_item:
                    self.db.execute_query(
                        "UPDATE user_inventory SET quantity = quantity + ? WHERE user_id = ? AND item_name = ?",
                        (quantity, user_id, item_name)
                    )
                else:
                    self.db.execute_query(
                        "INSERT INTO user_inventory (user_id, item_name, rarity, quantity) VALUES (?, ?, ?, ?)",
                        (user_id, item_name, rarity, quantity)
                    )
        
        # Lore discoveries
        if "discoveries" in rewards:
            for category, items in rewards["discoveries"].items():
                for item_name in items:
                    reward_text += f"• Discovered: {item_name} ({category})\n"
                    self.db.record_discovery(user_id, category, item_name)
        
        # Clean up active quest
        del self.active_quests[user_id]
        
        completion_data = {
            "quest_name": quest_name,
            "rewards": rewards,
            "message": reward_text
        }
        
        return True, reward_text, completion_data
    
    def get_current_quest(self, user_id: int) -> Tuple[bool, str, Dict]:
        """Get the current quest state for a user.
        
        Retrieves the active quest information for a user, including
        the current scene and available choices.
        
        Args:
            user_id: The user ID to check for active quests
            
        Returns:
            Tuple containing (success, message, scene_data)
        """
        if user_id not in self.active_quests:
            return False, "You are not currently on a quest.", {}
        
        quest_state = self.active_quests[user_id]
        quest_name = quest_state["quest_name"]
        quest_info = self.lore_manager.get_quest_info(quest_name)
        
        if not quest_info:
            return False, f"Quest '{quest_name}' not found.", {}
        
        # Get current scene data
        return self._get_scene_data(user_id)
    
    def abandon_quest(self, user_id: int) -> Tuple[bool, str]:
        """Abandon the current quest for a user.
        
        Args:
            user_id: The user ID abandoning the quest
            
        Returns:
            Tuple containing (success, message)
        """
        if user_id not in self.active_quests:
            return False, "You are not currently on a quest."
        
        quest_state = self.active_quests[user_id]
        quest_name = quest_state["quest_name"]
        
        # Update database
        self.db.execute_query(
            "UPDATE user_quests SET status = ? WHERE user_id = ? AND quest_name = ?",
            ("abandoned", user_id, quest_name)
        )
        
        # Clean up active quest
        del self.active_quests[user_id]
        
        return True, f"You have abandoned the quest '{quest_name}'."
    
    def interact_with_character(self, user_id: int, character_name: str, message: str) -> Tuple[bool, str, Dict]:
        """Interact with a character by sending them a message.
        
        Args:
            user_id: The user ID interacting with the character
            character_name: The name of the character to interact with
            message: The message to send to the character
            
        Returns:
            Tuple containing (success, response, character_info)
        """
        # Get character info
        character_info = self.lore_manager.get_character(character_name)
        if not character_info:
            return False, f"Character '{character_name}' not found.", {}
        
        # Generate response based on character traits and message content
        response = self._generate_character_response(character_name, character_info, message)
        
        # Record interaction
        current_time = self.db.execute_query("SELECT datetime('now') as time")[0]["time"]
        
        # Check if relationship exists
        existing = self.db.execute_query(
            "SELECT 1 FROM user_relationships WHERE user_id = ? AND character_name = ?",
            (user_id, character_name)
        )
        
        if existing:
            self.db.execute_query(
                "UPDATE user_relationships SET last_interaction = ? WHERE user_id = ? AND character_name = ?",
                (current_time, user_id, character_name)
            )
        else:
            self.db.execute_query(
                "INSERT INTO user_relationships (user_id, character_name, affinity, first_met, last_interaction) VALUES (?, ?, ?, ?, ?)",
                (user_id, character_name, 0, current_time, current_time)
            )
        
        # Return response and character info
        return True, response, character_info
    
    def _generate_character_response(self, character_name: str, character_info: Dict, message: str) -> str:
        """Generate a character response based on their traits and the message.
        
        Args:
            character_name: The name of the character
            character_info: The character's information
            message: The message sent to the character
            
        Returns:
            The character's response
        """
        # Check for specific keywords in the message
        lower_message = message.lower()
        
        # Check for greetings
        if any(greeting in lower_message for greeting in ["hello", "hi", "hey", "greetings"]):
            return self._generate_greeting(character_name, character_info)
        
        # Check for questions about the character
        if "who are you" in lower_message or "about you" in lower_message:
            return self._generate_self_introduction(character_name, character_info)
        
        # Check for questions about the world
        if any(keyword in lower_message for keyword in ["world", "fangen", "history", "lore"]):
            return self._generate_lore_response(character_name, character_info, "world")
        
        # Check for questions about items
        if any(keyword in lower_message for keyword in ["item", "weapon", "artifact", "craft"]):
            return self._generate_lore_response(character_name, character_info, "items")
        
        # Check for questions about quests
        if any(keyword in lower_message for keyword in ["quest", "mission", "task", "adventure"]):
            return self._generate_lore_response(character_name, character_info, "quests")
        
        # Generate a generic response if no specific patterns match
        return self._generate_generic_response(character_name, character_info, message)
    
    def _generate_greeting(self, character_name: str, character_info: Dict) -> str:
        """Generate a greeting response from a character."""
        personality = character_info.get("personality", "").lower()
        
        # Character-specific greetings
        if character_name == "Hand of Diamond":
            return "The light of Diamond shines upon you. What guidance do you seek from the elements?"
        
        elif character_name == "Zero":
            return "The threads of fate intertwine in curious ways. I've been expecting you, though perhaps not in this timeline."
        
        elif character_name == "Wagami":
            return "*looks up from a complex device* Oh! Hello there! Caught me in the middle of a fascinating experiment. How can I help you today?"
        
        elif character_name == "Anko":
            return "*sharpens kunai* Well, well... look who's here. Got something interesting for me, or just wasting my time?"
        
        # Generic greetings based on personality types
        elif "arrogant" in personality or "cunning" in personality:
            return "Ah, you've sought me out. A wise decision, though I wonder if you truly comprehend what you're asking for."
        
        elif "stoic" in personality or "cold" in personality:
            return "You have my attention, for now. State your purpose clearly."
        
        elif "playful" in personality or "eccentric" in personality:
            return "*eyes light up* Oh hello there! What a delightful surprise! What brings you to my little corner of Fangen today?"
        
        elif "fierce" in personality or "protective" in personality:
            return "*assesses you carefully* Stand your ground and speak plainly. What do you seek from me?"
        
        # Default greeting
        return f"Greetings, traveler. I am {character_name}. What brings you to me today?"
    
    def _generate_self_introduction(self, character_name: str, character_info: Dict) -> str:
        """Generate a self-introduction from a character."""
        backstory = character_info.get("backstory", "")
        role = character_info.get("role", "")
        personality = character_info.get("personality", "")
        
        # Truncate long text
        if len(backstory) > 150:
            backstory = backstory[:147] + "..."
        
        # Character-specific introductions
        if character_name == "Hand of Diamond":
            return "I am the Hand of Diamond, emissary of the elemental forces that shape our world. I guide those who would maintain balance and protect the realm from those who would upset it."
        
        elif character_name == "Zero":
            return "I am called Zero, though names are but temporary labels in the grand tapestry of existence. I see the threads of possibility, the paths not taken, and occasionally, I intervene when catastrophe looms."
        
        elif character_name == "Wagami":
            return "*adjusts glasses excitedly* I'm Wagami! Chief researcher of anomalous phenomena and quantum irregularities! Some call my methods unorthodox, but that's how breakthroughs happen! Currently working on harnessing wormhole energy for practical applications!"
        
        elif character_name == "Anko":
            return "*twirls kunai knife* The name's Anko. I get things done that others can't—or won't. Not all heroes wear their intentions on their sleeves, you know? Let's just say I keep the shadows in check."
        
        # Generic introduction combining role and backstory
        if role and backstory:
            return f"I am {character_name}, {role}. {backstory}"
        elif role:
            return f"I am {character_name}, {role}."
        elif backstory:
            return f"I am {character_name}. {backstory}"
        else:
            return f"I am {character_name}. My story is my own, and not all tales are meant to be shared freely."
    
    def _generate_lore_response(self, character_name: str, character_info: Dict, category: str) -> str:
        """Generate a lore-related response from a character."""
        # Get a random piece of lore from the specified category
        category_name, lore_name, lore_content = self.lore_manager.get_random_lore(category)
        
        if not lore_content or lore_content == "No lore entries available":
            return f"There are mysteries about {category} that even I do not fully comprehend."
        
        # Get character-specific introduction phrases
        intros = self._get_character_intros(character_name, character_info)
        intro = random.choice(intros)
        
        # Format the response
        return f"{intro} {lore_content}"
    
    def _get_character_intros(self, character_name: str, character_info: Dict) -> List[str]:
        """Get character-specific introduction phrases."""
        # Default introduction phrases
        default_intros = [
            "Let me tell you about",
            "I know something of",
            "Indeed,",
            "As you may know,",
            "I must tell you that",
            "It is known that",
            "Let me share with you,"
        ]
        
        # Check personality traits for character-specific intros
        personality = character_info.get("personality", "").lower()
        
        if "arrogant" in personality or "cunning" in personality:
            return [
                "Obviously, for one of my standing,",
                "Few would understand this, but",
                "Let me enlighten you with this knowledge:",
                "I suppose I can share this with you:",
                "How interesting that you should ask about that."
            ]
        elif "stoic" in personality or "cold" in personality:
            return [
                "Consider this information carefully:",
                "These are the facts:",
                "Without embellishment, I will tell you:",
                "It is simply thus:",
                "The truth of the matter is"
            ]
        elif "playful" in personality or "eccentric" in personality:
            return [
                "Ooh! That's a good question!",
                "Isn't it fascinating that",
                "Well, here's something delightful:",
                "Ha! You're curious about that?",
                "Oh, I've got a story about that!"
            ]
        elif "fierce" in personality or "protective" in personality:
            return [
                "Listen well, for this is important:",
                "I will tell you this only once:",
                "Stand firm as I reveal that",
                "This knowledge is worth defending:",
                "As one who has fought for this truth:"
            ]
        
        return default_intros
    
    def _generate_generic_response(self, character_name: str, character_info: Dict, message: str) -> str:
        """Generate a generic response based on character traits."""
        personality = character_info.get("personality", "").lower()
        role = character_info.get("role", "").lower()
        
        # Character-specific generic responses
        if character_name == "Hand of Diamond":
            return f"The Element of Diamond resonates with courage and unity. Your question about '{message}' touches on matters of great importance to the balance of power."
        
        elif character_name == "Zero":
            return f"My visions show many possible futures. The path you seek regarding '{message}' is but one of many, yet it could be crucial to preventing catastrophe."
        
        elif character_name == "Wagami":
            return f"*adjusts glasses excitedly* Oh! That's an interesting query about '{message}'! It reminds me of an experiment I was conducting just last week with the wormhole dynamics!"
        
        elif character_name == "Anko":
            return f"*flips kunai knife casually* You want to know about '{message}'? Well, I could tell you... but then I'd have to... you know the rest. *smirks*"
        
        # Generic responses based on personality types
        elif "arrogant" in personality or "cunning" in personality:
            return f"Your curiosity about '{message}' is... quaint. Perhaps someday you'll understand the true significance of what you ask."
        
        elif "stoic" in personality or "cold" in personality:
            return f"I have witnessed much regarding '{message}'. Whether you are ready for such knowledge remains to be seen."
        
        elif "playful" in personality or "eccentric" in personality:
            return f"*eyes light up* '{message}'? Now that's a topic full of surprises! Just when you think you understand it, everything turns upside down!"
        
        elif "fierce" in personality or "protective" in personality:
            return f"I would guard the truth about '{message}' with my life. It is not knowledge to be taken lightly."
        
        # Default response if no specific patterns match
        return f"You ask about '{message}'? That is a matter that intersects with my experiences in ways you might not expect."
    
    def get_inventory(self, user_id: int) -> List[Dict]:
        """Get the user's inventory."""
        items = self.db.execute_query(
            "SELECT item_name, rarity, quantity FROM user_inventory WHERE user_id = ? AND quantity > 0",
            (user_id,)
        )
        
        inventory = []
        for item in items:
            item_info = self.lore_manager.get_item(item['item_name'])
            description = ""
            if item_info and isinstance(item_info, dict):
                description = item_info.get("description", "")
            
            inventory.append({
                "name": item['item_name'],
                "rarity": item['rarity'],
                "quantity": item['quantity'],
                "description": description
            })
        
        return inventory
