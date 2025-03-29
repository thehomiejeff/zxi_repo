#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fangen Lore Manager for ChuzoBot
Handles loading, parsing, and retrieving the rich world of Fangen
"""

import os
import re
import json
import sys
from typing import Dict, List, Optional, Tuple, Any

# Add the project root directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import get_logger
from config import LORE_FILE

logger = get_logger(__name__)

class FangenLoreManager:
    """Manages lore content for the Fangen universe."""
    
    def __init__(self, lore_file: str = LORE_FILE):
        """Initialize the LoreManager."""
        self.lore_file = lore_file
        self.lore_data = {
            "world": {},
            "events": {},
            "themes": {},
            "characters": {},
            "locations": {},
            "factions": {},
            "items": {},
            "quests": {}
        }
        self.characters = []
        self.items = []
        self.quests = []
        self.load_lore()
    
    def load_lore(self) -> None:
        """Load lore from the specified file."""
        try:
            if not os.path.exists(self.lore_file):
                logger.warning(f"Lore file not found: {self.lore_file}")
                return
            
            with open(self.lore_file, 'r', encoding='utf-8') as f:
                raw_content = f.read()
            
            # Parse the lore content
            self._parse_lore_content(raw_content)
            logger.info(f"Fangen lore loaded successfully from {self.lore_file}")
            
        except Exception as e:
            logger.error(f"Error loading lore: {e}", exc_info=True)
    
    def _parse_lore_content(self, content: str) -> None:
        """
        Parse the lore content into structured data.
        Handles hierarchical format with main categories and subcategories.
        """
        # Process character profiles
        self._parse_character_profiles(content)
        
        # Process world history and lore
        self._parse_world_history(content)
        
        # Process items and quests
        self._parse_items_and_quests(content)
    
    def _parse_character_profiles(self, content: str) -> None:
        """Parse character profiles from the content.
        
        Extracts character information including name, backstory, personality,
        and their connections to items and quests.
        
        Args:
            content: Raw lore text content to parse
        """
        # Look for character profile sections with more flexible pattern matching
        # This improved pattern handles both uppercase and mixed case character names
        # and accounts for variations in formatting
        character_pattern = r'([A-Z][A-Za-z, ]+)\n•\s*Backstory\s*&?\s*Role:\s*(.*?)•\s*Personality\s*&?\s*Motivations:\s*(.*?)(?:•\s*Item\s*&?\s*Quest Connections:|•\s*Relationships:)'
        character_sections = re.findall(character_pattern, content, re.DOTALL)
        
        for name, backstory, personality in character_sections:
            name = name.strip()
            backstory = backstory.strip()
            personality = personality.strip()
            
            # Extract item and quest connections if available
            # Improved pattern with more flexible matching for section headers
            item_quest_pattern = r'•\s*Item\s*&?\s*Quest Connections:(.*?)(?:_{10,}|$)'
            # Use a safer approach to find content after the character name
            name_pos = content.find(name)
            if name_pos >= 0:
                search_content = content[name_pos:]
                item_quest_match = re.search(item_quest_pattern, search_content, re.DOTALL)
            else:
                item_quest_match = None
            
            item_connections = ""
            quest_connections = ""
            if item_quest_match:
                item_quest_text = item_quest_match.group(1).strip()
                
                # Further parse items and quests
                item_pattern = r'•\s*Potential Items:(.*?)(?:•\s*Quests:|$)'
                item_match = re.search(item_pattern, item_quest_text, re.DOTALL)
                if item_match:
                    item_connections = item_match.group(1).strip()
                
                quest_pattern = r'•\s*Quests:(.*?)(?:$)'
                quest_match = re.search(quest_pattern, item_quest_text, re.DOTALL)
                if quest_match:
                    quest_connections = quest_match.group(1).strip()
            
            # Create character profile
            self.lore_data["characters"][name] = {
                "backstory": backstory,
                "personality": personality,
                "item_connections": item_connections,
                "quest_connections": quest_connections
            }
            
            self.characters.append(name)
        
        # Also look for more comprehensive character profiles
        expanded_char_pattern = r'([A-Za-z, ]+)\n•\s*Role:\s*(.*?)•\s*Backstory:\s*(.*?)•\s*Personality:\s*(.*?)•\s*Relationships:\s*(.*?)•\s*Significance in Lore:\s*(.*?)(?:_{10,}|$)'
        expanded_char_sections = re.findall(expanded_char_pattern, content, re.DOTALL)
        
        for name, role, backstory, personality, relationships, significance in expanded_char_sections:
            name = name.strip()
            
            # If character already exists from first pass, enhance it
            if name in self.lore_data["characters"]:
                self.lore_data["characters"][name].update({
                    "role": role.strip(),
                    "relationships": relationships.strip(),
                    "significance": significance.strip()
                })
            else:
                # Create new character entry
                self.lore_data["characters"][name] = {
                    "role": role.strip(),
                    "backstory": backstory.strip(),
                    "personality": personality.strip(),
                    "relationships": relationships.strip(),
                    "significance": significance.strip()
                }
                
                if name not in self.characters:
                    self.characters.append(name)
    
    def _parse_world_history(self, content: str) -> None:
        """Parse world history and lore from the content."""
        # Look for world overview
        world_pattern = r'The World of Fangen\n•\s*Overview:\s*(.*?)(?:Key Historical Events|\n\n)'
        world_match = re.search(world_pattern, content, re.DOTALL)
        if world_match:
            self.lore_data["world"]["Overview"] = world_match.group(1).strip()
        
        # Parse historical events
        events_pattern = r'Key Historical Events\n(•\s*[^•]+)'
        events_match = re.search(events_pattern, content, re.DOTALL)
        if events_match:
            events_text = events_match.group(1)
            event_items = re.findall(r'•\s*([^:]+):\s*([^•]+)', events_text, re.DOTALL)
            
            for event_name, event_desc in event_items:
                self.lore_data["events"][event_name.strip()] = event_desc.strip()
        
        # Parse elemental and mystical themes
        themes_pattern = r'Elemental and Mystical Themes\n(•\s*[^•]+)'
        themes_match = re.search(themes_pattern, content, re.DOTALL)
        if themes_match:
            themes_text = themes_match.group(1)
            theme_items = re.findall(r'•\s*([^:]+):\s*([^•]+)', themes_text, re.DOTALL)
            
            for theme_name, theme_desc in theme_items:
                self.lore_data["themes"][theme_name.strip()] = theme_desc.strip()
        
        # Parse cultural and social dynamics
        culture_pattern = r'Cultural and Social Dynamics\n(•\s*[^•]+)'
        culture_match = re.search(culture_pattern, content, re.DOTALL)
        if culture_match:
            culture_text = culture_match.group(1)
            culture_items = re.findall(r'•\s*([^:]+):\s*([^•]+)', culture_text, re.DOTALL)
            
            for faction_name, faction_desc in culture_items:
                self.lore_data["factions"][faction_name.strip()] = faction_desc.strip()
    
    def _parse_items_and_quests(self, content: str) -> None:
        """Parse items and quests from the content."""
        # Look for item crafting sections
        item_pattern = r'Item Crafting & Evolution:\s*(.*?)(?:\d\.\s*Quest Narratives:|$)'
        item_match = re.search(item_pattern, content, re.DOTALL)
        if item_match:
            item_text = item_match.group(1)
            
            # Parse item tiers
            tier_pattern = r'•\s*([^:]+):\s*([^•]+)'
            tier_items = re.findall(tier_pattern, item_text, re.DOTALL)
            
            for tier_name, tier_desc in tier_items:
                self.lore_data["items"][tier_name.strip()] = tier_desc.strip()
            
            # Extract specific item examples from the text
            item_examples = re.findall(r'((?:Ape\'s Wrath|Wagami\'s Catalyst|Shokei\'s Maw|Moon Blade|Seigo\'s Rampart|Miyou\'s Insight Amulet|Kagitada\'s Lock|Paper\'s Edge|Paper Reaver|Alpha Empress\'s Sigil|Voidforged Relic|Inferno Fang|Emberdust Vial|Solar Fang)[^,.]*)', content)
            
            for item in item_examples:
                if item.strip() not in self.items:
                    self.items.append(item.strip())
                    
                    # Try to determine rarity
                    rarity = "Normal"
                    if "Legendary" in content[content.find(item)-100:content.find(item)+100]:
                        rarity = "Legendary"
                    elif "Rare" in content[content.find(item)-100:content.find(item)+100]:
                        rarity = "Rare"
                    elif "Uncommon" in content[content.find(item)-100:content.find(item)+100]:
                        rarity = "Uncommon"
                    
                    # Add item to lore data if not already present
                    if item.strip() not in self.lore_data["items"]:
                        self.lore_data["items"][item.strip()] = {
                            "rarity": rarity,
                            "description": f"A {rarity.lower()} item from the world of Fangen."
                        }
        
        # Look for quest narratives
        quest_pattern = r'Quest Narratives:\s*(.*?)(?:$)'
        quest_match = re.search(quest_pattern, content, re.DOTALL)
        if quest_match:
            quest_text = quest_match.group(1)
            
            # Parse individual quests
            quest_sections = re.split(r'\d+\.\s+', quest_text)
            for section in quest_sections[1:]:  # Skip the first empty split
                # Extract quest title and description
                title_match = re.match(r'([^\n]+)', section)
                if title_match:
                    title = title_match.group(1).strip()
                    description = section[len(title):].strip()
                    
                    # Add to quests list if not already present
                    if title.strip() not in self.quests:
                        self.quests.append(title.strip())
                    
                    # Add to lore data
                    self.lore_data["quests"][title.strip()] = {
                        "description": description,
                        "requirements": [],
                        "rewards": []
                    }
                    
                    # Try to extract requirements and rewards
                    req_match = re.search(r'Requirements:\s*(.*?)(?:Rewards:|$)', description, re.DOTALL)
                    if req_match:
                        requirements = req_match.group(1).strip().split('\n')
                        self.lore_data["quests"][title.strip()]["requirements"] = [r.strip() for r in requirements if r.strip()]
                    
                    reward_match = re.search(r'Rewards:\s*(.*?)(?:$)', description, re.DOTALL)
                    if reward_match:
                        rewards = reward_match.group(1).strip().split('\n')
                        self.lore_data["quests"][title.strip()]["rewards"] = [r.strip() for r in rewards if r.strip()]
    
    def get_character(self, name: str) -> Optional[Dict]:
        """Get character information by name."""
        return self.lore_data["characters"].get(name)
    
    def get_item(self, name: str) -> Optional[Dict]:
        """Get item information by name."""
        return self.lore_data["items"].get(name)
    
    def get_quest(self, name: str) -> Optional[Dict]:
        """Get quest information by name."""
        return self.lore_data["quests"].get(name)
    
    def search_lore(self, query: str) -> Dict[str, List[Tuple[str, str]]]:
        """Search for lore entries containing the query.
        
        Args:
            query: Search term to look for
            
        Returns:
            Dictionary with category keys and lists of (name, snippet) tuples as values
        """
        results = {
            "characters": [],
            "items": [],
            "quests": [],
            "world": [],
            "events": [],
            "themes": [],
            "factions": []
        }
        
        query = query.lower()
        
        # Search characters
        for name, data in self.lore_data["characters"].items():
            # Combine all character data for searching
            char_text = name.lower()
            for key, value in data.items():
                if isinstance(value, str):
                    char_text += " " + value.lower()
            
            if query in char_text:
                # Create a snippet from the backstory or personality
                snippet = data.get("backstory", "") or data.get("personality", "")
                if len(snippet) > 100:
                    snippet = snippet[:97] + "..."
                results["characters"].append((name, snippet))
        
        # Search items
        for name, data in self.lore_data["items"].items():
            # Handle both string and dict item data
            if isinstance(data, dict):
                item_text = name.lower() + " " + " ".join(str(v).lower() for v in data.values())
                snippet = data.get("description", "")
            else:
                item_text = name.lower() + " " + data.lower()
                snippet = data
            
            if query in item_text:
                if len(snippet) > 100:
                    snippet = snippet[:97] + "..."
                results["items"].append((name, snippet))
        
        # Search quests
        for name, data in self.lore_data["quests"].items():
            # Handle both string and dict quest data
            if isinstance(data, dict):
                quest_text = name.lower() + " " + " ".join(str(v).lower() for v in data.values())
                snippet = data.get("description", "")
            else:
                quest_text = name.lower() + " " + data.lower()
                snippet = data
            
            if query in quest_text:
                if len(snippet) > 100:
                    snippet = snippet[:97] + "..."
                results["quests"].append((name, snippet))
        
        # Search world lore
        for name, data in self.lore_data["world"].items():
            if query in (name.lower() + " " + data.lower()):
                snippet = data
                if len(snippet) > 100:
                    snippet = snippet[:97] + "..."
                results["world"].append((name, snippet))
        
        # Search events
        for name, data in self.lore_data["events"].items():
            if query in (name.lower() + " " + data.lower()):
                snippet = data
                if len(snippet) > 100:
                    snippet = snippet[:97] + "..."
                results["events"].append((name, snippet))
        
        # Search themes
        for name, data in self.lore_data["themes"].items():
            if query in (name.lower() + " " + data.lower()):
                snippet = data
                if len(snippet) > 100:
                    snippet = snippet[:97] + "..."
                results["themes"].append((name, snippet))
        
        # Search factions
        for name, data in self.lore_data["factions"].items():
            if query in (name.lower() + " " + data.lower()):
                snippet = data
                if len(snippet) > 100:
                    snippet = snippet[:97] + "..."
                results["factions"].append((name, snippet))
        
        return results
    
    def get_categories(self) -> List[str]:
        """Get all available lore categories.
        
        Returns:
            List of category names
        """
        categories = [
            "characters",
            "items",
            "quests",
            "world",
            "events",
            "themes",
            "factions"
        ]
        return categories
    
    def get_quests(self) -> List[str]:
        """Get all available quests.
        
        Returns:
            List of quest names
        """
        return self.quests
    
    def get_quest_info(self, name: str) -> Optional[Dict]:
        """Get detailed information about a specific quest.
        
        Args:
            name: Name of the quest
            
        Returns:
            Dictionary containing quest information or None if not found
        """
        return self.lore_data["quests"].get(name)
    
    def get_random_lore(self, category: str = None) -> Tuple[str, str, str]:
        """Get a random lore entry.
        
        Args:
            category: Optional category to limit selection to
            
        Returns:
            Tuple of (category, name, content)
        """
        import random
        
        # Define available categories and their corresponding data
        categories = {
            "characters": self.lore_data["characters"],
            "items": self.lore_data["items"],
            "quests": self.lore_data["quests"],
            "world": self.lore_data["world"],
            "events": self.lore_data["events"],
            "themes": self.lore_data["themes"],
            "factions": self.lore_data["factions"]
        }
        
        # Filter to specified category if provided
        if category and category in categories:
            available_categories = {category: categories[category]}
        else:
            available_categories = categories
        
        # Filter out empty categories
        available_categories = {k: v for k, v in available_categories.items() if v}
        
        if not available_categories:
            return ("", "", "No lore entries available")
        
        # Select random category
        selected_category = random.choice(list(available_categories.keys()))
        category_data = available_categories[selected_category]
        
        # Select random entry from category
        if not category_data:
            return (selected_category, "", "No entries in this category")
        
        selected_name = random.choice(list(category_data.keys()))
        selected_data = category_data[selected_name]
        
        # Format the content based on data type
        if isinstance(selected_data, dict):
            if selected_category == "characters":
                content = f"*Backstory:* {selected_data.get('backstory', '')}\n\n"
                content += f"*Personality:* {selected_data.get('personality', '')}"
            elif selected_category == "quests":
                content = selected_data.get("description", "")
            elif selected_category == "items":
                content = f"*Rarity:* {selected_data.get('rarity', 'Normal')}\n\n"
                content += f"*Description:* {selected_data.get('description', '')}"
            else:
                content = str(selected_data)
        else:
            content = str(selected_data)
        
        return (selected_category, selected_name, content)
    
    def get_all_characters(self) -> List[str]:
        """Get a list of all character names."""
        return self.characters
    
    def get_all_items(self) -> List[str]:
        """Get a list of all item names."""
        return self.items
    
    def get_all_quests(self) -> List[str]:
        """Get a list of all quest names."""
        return self.quests
    
    def get_lore_stats(self) -> Dict[str, int]:
        """Get statistics about the loaded lore.
        
        Returns:
            Dictionary with counts for each category
        """
        return {
            "characters": len(self.lore_data["characters"]),
            "items": len(self.lore_data["items"]),
            "quests": len(self.lore_data["quests"]),
            "world": len(self.lore_data["world"]),
            "events": len(self.lore_data["events"]),
            "themes": len(self.lore_data["themes"]),
            "factions": len(self.lore_data["factions"])
        }
