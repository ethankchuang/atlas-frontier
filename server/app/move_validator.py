import asyncio
from typing import Tuple, List, Dict, Any, Optional, Set
import logging
import json

logger = logging.getLogger(__name__)

class DynamicMoveValidator:
    """Dynamic move validator that adapts to any world type and evolves over time."""
    
    def __init__(self, game_manager):
        self.game_manager = game_manager
        self.validation_cache = {}  # Cache for performance
        self.cache_ttl = 300  # 5 minutes cache TTL
        
    @staticmethod
    async def validate_move(player_id: str, move: str, game_manager) -> Tuple[bool, str, Optional[str]]:
        """
        Validate if a player can perform a move using dynamic, world-adaptive rules.
        
        Args:
            player_id: The player's ID
            move: The move text to validate
            game_manager: The game manager instance
            
        Returns:
            Tuple of (is_valid, reason, suggestion)
        """
        validator = DynamicMoveValidator(game_manager)
        return await validator._validate_move_dynamic(player_id, move)
    
    async def _validate_move_dynamic(self, player_id: str, move: str) -> Tuple[bool, str, Optional[str]]:
        """Dynamic validation that adapts to the current world and player context."""
        try:
            logger.info(f"[DynamicMoveValidator] Validating move for player {player_id}: '{move}'")
            
            # Get player and their inventory
            player = await self.game_manager.get_player(player_id)
            if not player:
                return False, "Player not found", None
            
            # Get world context for adaptive validation
            world_context = await self._get_world_context()
            
            # Get player's inventory items with their types and capabilities
            inventory_items = await self._get_player_inventory_with_types(player)
            
            # Check if it's a basic action (always valid in most contexts)
            if await self._is_basic_action(move, world_context):
                return True, "Basic action - no equipment required", None
            
            # Check if it's an equipment-requiring action
            if await self._requires_equipment_dynamic(move, world_context):
                # Validate against player's inventory capabilities
                return await self._validate_equipment_requirement_dynamic(move, inventory_items, world_context)
            
            # If unsure, use AI to determine if it's valid
            return await self._ai_validate_action(move, inventory_items, world_context)
            
        except Exception as e:
            logger.error(f"[DynamicMoveValidator] Error validating move: {str(e)}")
            return True, "Validation error - allowing move", None
    
    async def _get_world_context(self) -> Dict[str, Any]:
        """Get the current world context for adaptive validation."""
        try:
            game_state = await self.game_manager.db.get_game_state()
            world_seed = game_state.get('world_seed', 'default')
            
            # Get world-specific validation rules
            world_rules = await self._get_world_validation_rules(world_seed)
            
            # Get current world theme and biome information
            world_context = {
                'world_seed': world_seed,
                'main_quest': game_state.get('main_quest_summary', ''),
                'world_rules': world_rules,
                'world_theme': await self._infer_world_theme(world_seed, game_state),
                'validation_mode': world_rules.get('validation_mode', 'adaptive')
            }
            
            return world_context
            
        except Exception as e:
            logger.error(f"[DynamicMoveValidator] Error getting world context: {str(e)}")
            return {'world_seed': 'default', 'validation_mode': 'permissive'}
    
    async def _get_world_validation_rules(self, world_seed: str) -> Dict[str, Any]:
        """Get world-specific validation rules from database."""
        try:
            # Try to get cached rules
            cache_key = f"validation_rules_{world_seed}"
            if cache_key in self.validation_cache:
                return self.validation_cache[cache_key]
            
            # Get rules from database or generate them
            rules_data = await self.game_manager.db.get_world_validation_rules(world_seed)
            
            if not rules_data:
                # Generate new rules based on world context
                rules_data = await self._generate_world_validation_rules(world_seed)
                await self.game_manager.db.set_world_validation_rules(world_seed, rules_data)
            
            # Cache the rules
            self.validation_cache[cache_key] = rules_data
            return rules_data
            
        except Exception as e:
            logger.error(f"[DynamicMoveValidator] Error getting validation rules: {str(e)}")
            return self._get_default_validation_rules()
    
    async def _generate_world_validation_rules(self, world_seed: str) -> Dict[str, Any]:
        """Generate validation rules based on world context using AI."""
        try:
            game_state = await self.game_manager.db.get_game_state()
            world_context = f"World Seed: {world_seed}\nMain Quest: {game_state.get('main_quest_summary', '')}"
            
            prompt = f"""
Generate dynamic validation rules for this game world:

{world_context}

Create a JSON object with the following structure:
{{
    "validation_mode": "adaptive|strict|permissive",
    "basic_actions": ["list", "of", "basic", "actions", "that", "don't", "require", "equipment"],
    "equipment_actions": ["list", "of", "actions", "that", "require", "equipment"],
    "action_mappings": {{
        "action_type": ["capability1", "capability2", "capability3"]
    }},
    "world_specific_rules": {{
        "magic_allowed": true/false,
        "technology_allowed": true/false,
        "firearms_allowed": true/false,
        "special_restrictions": ["any", "special", "rules"]
    }}
}}

Make the rules appropriate for the world theme and context.
"""
            
            response = await self.game_manager.ai_handler.generate_text(prompt)
            
            # Parse AI response
            try:
                rules = json.loads(response)
                logger.info(f"[DynamicMoveValidator] Generated validation rules for world {world_seed}")
                return rules
            except json.JSONDecodeError:
                logger.warning(f"[DynamicMoveValidator] Failed to parse AI response, using defaults")
                return self._get_default_validation_rules()
                
        except Exception as e:
            logger.error(f"[DynamicMoveValidator] Error generating validation rules: {str(e)}")
            return self._get_default_validation_rules()
    
    def _get_default_validation_rules(self) -> Dict[str, Any]:
        """Get default validation rules for fallback."""
        return {
            "validation_mode": "adaptive",
            "basic_actions": ["punch", "kick", "tackle", "dodge", "block", "parry", "grapple", "wrestle", "headbutt", "elbow", "knee", "shoulder", "charge", "sidestep", "duck", "jump", "roll", "crawl", "climb", "run", "walk", "sneak", "hide"],
            "equipment_actions": ["slash", "stab", "cut", "thrust", "swing", "strike", "hack", "chop", "shoot", "fire", "aim", "draw", "release", "throw", "launch", "blast", "cast", "spell", "magic", "enchant", "summon", "teleport", "levitate", "heal", "restore", "boost", "enhance", "protect", "ward", "shield", "unlock", "pick", "break", "smash", "drill", "saw", "hammer", "repair", "craft", "build", "assemble", "disassemble", "modify", "hack", "access", "control", "analyze", "scan", "detect", "identify", "activate", "deactivate", "program", "interface", "connect", "disconnect"],
            "action_mappings": {
                "slash": ["slash", "cut", "hack", "chop"],
                "stab": ["stab", "thrust", "pierce"],
                "shoot": ["shoot", "fire", "aim", "launch"],
                "cast": ["cast", "spell", "magic", "enchant"],
                "heal": ["heal", "restore", "cure"],
                "protect": ["protect", "defend", "guard", "shield"],
                "unlock": ["unlock", "open", "access"],
                "hack": ["hack", "access", "control", "analyze"]
            },
            "world_specific_rules": {
                "magic_allowed": True,
                "technology_allowed": True,
                "firearms_allowed": True,
                "special_restrictions": []
            }
        }
    
    async def _infer_world_theme(self, world_seed: str, game_state: Dict[str, Any]) -> str:
        """Infer the world theme from context."""
        try:
            main_quest = game_state.get('main_quest_summary', '').lower()
            
            # Simple theme inference based on keywords
            if any(word in main_quest for word in ['magic', 'spell', 'wizard', 'dragon', 'fantasy']):
                return 'fantasy'
            elif any(word in main_quest for word in ['cyber', 'tech', 'digital', 'hack', 'neural']):
                return 'cyberpunk'
            elif any(word in main_quest for word in ['apocalypse', 'survival', 'wasteland', 'scavenge']):
                return 'post_apocalyptic'
            elif any(word in main_quest for word in ['steam', 'gear', 'mechanical', 'industrial']):
                return 'steampunk'
            elif any(word in main_quest for word in ['nature', 'forest', 'animals', 'plants']):
                return 'nature'
            else:
                return 'generic'
                
        except Exception as e:
            logger.error(f"[DynamicMoveValidator] Error inferring world theme: {str(e)}")
            return 'generic'
    
    
    async def _get_player_inventory_with_types(self, player) -> List[Dict[str, Any]]:
        """Get player's inventory items with their capabilities."""
        inventory_items = []
        
        for item_id in player.inventory:
            try:
                # Get item data
                item_data = await self.game_manager.db.get_item(item_id)
                if not item_data:
                    logger.warning(f"[DynamicMoveValidator] Item {item_id} not found in database")
                    continue
                
                # Extract item information from new AI-generated structure
                name = item_data.get('name', 'Unknown Item')
                description = item_data.get('description', 'No description')
                capabilities = item_data.get('capabilities', [])
                rarity = item_data.get('rarity', 1)
                
                inventory_items.append({
                    'id': item_id,
                    'name': name,
                    'description': description,
                    'capabilities': capabilities,
                    'rarity': rarity
                })
                
                logger.debug(f"[DynamicMoveValidator] Added inventory item: {name} with capabilities: {capabilities}")
                
            except Exception as e:
                logger.error(f"[DynamicMoveValidator] Error getting item {item_id}: {str(e)}")
                continue
        
        logger.info(f"[DynamicMoveValidator] Player has {len(inventory_items)} items in inventory")
        return inventory_items
    
    async def _is_basic_action(self, move: str, world_context: Dict[str, Any]) -> bool:
        """Check if the move is a basic action that doesn't require equipment."""
        move_lower = move.lower()
        basic_actions = world_context.get('world_rules', {}).get('basic_actions', [])
        
        # Check for exact matches
        for action in basic_actions:
            if action in move_lower:
                return True
        
        # Also check for common variations
        basic_patterns = ['punch', 'kick', 'tackle', 'dodge', 'block', 'parry', 'grapple', 'headbutt', 'elbow', 'knee', 'shoulder', 'charge', 'sidestep', 'duck', 'jump', 'roll', 'crawl', 'climb', 'run', 'walk', 'sneak']
        
        for pattern in basic_patterns:
            if pattern in move_lower:
                return True
        
        return False
    
    async def _requires_equipment_dynamic(self, move: str, world_context: Dict[str, Any]) -> bool:
        """Check if the move requires equipment based on world rules."""
        move_lower = move.lower()
        world_rules = world_context.get('world_rules', {})
        
        # Check for equipment-related keywords from world rules
        equipment_actions = world_rules.get('equipment_actions', [])
        for action in equipment_actions:
            if action in move_lower:
                return True
        
        # Check for specific item mentions
        
        # Check for common item keywords
        common_items = ['sword', 'knife', 'dagger', 'blade', 'axe', 'hammer', 'mace', 'bow', 'arrow', 'gun', 'pistol', 'rifle', 'staff', 'wand', 'shield', 'armor', 'helmet', 'gauntlets', 'boots', 'ring', 'amulet', 'potion', 'scroll', 'book', 'key', 'lockpick', 'tool', 'gear', 'device', 'machine', 'computer', 'hologram', 'implant', 'cyberdeck', 'drone', 'grenade', 'explosive']
        
        for keyword in common_items:
            if keyword in move_lower:
                return True
        
        return False
    
    async def _validate_equipment_requirement_dynamic(self, move: str, inventory_items: List[Dict[str, Any]], world_context: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """Validate if the player has the required equipment using dynamic rules."""
        move_lower = move.lower()
        world_rules = world_context.get('world_rules', {})
        action_mappings = world_rules.get('action_mappings', {})
        
        # Check each inventory item's capabilities
        for item in inventory_items:
            item_name = item['name'].lower()
            description = item['description'].lower()
            capabilities = [cap.lower() for cap in item['capabilities']]
            
            # Check if the move mentions this specific item
            if item_name in move_lower:
                # Check if the item's capabilities support the action
                if await self._capabilities_support_action_dynamic(move_lower, capabilities, description, action_mappings):
                    return True, f"Valid action using {item['name']}", None
                else:
                    return False, f"Item {item['name']} doesn't support this action", f"Try using {item['name']} for: {', '.join(capabilities)}"
            
            # Check if any capability matches the action
            for capability in capabilities:
                if capability in move_lower:
                    return True, f"Valid action using {item['name']} ({capability})", None
        
        # Check for high-rarity items with special capabilities
        for item in inventory_items:
            if item['rarity'] >= 3 and await self._item_description_supports_action_dynamic(move_lower, item['description'], world_context):
                return True, f"Valid action using {item['name']} special abilities", None
        
        # If we get here, the player doesn't have the required equipment
        missing_equipment = await self._identify_missing_equipment_dynamic(move_lower, world_context)
        suggestion = await self._generate_suggestion_dynamic(move_lower, inventory_items, world_context)
        
        return False, f"Missing required equipment: {missing_equipment}", suggestion
    
    async def _capabilities_support_action_dynamic(self, move: str, capabilities: List[str], special_effects: str, action_mappings: Dict[str, List[str]]) -> bool:
        """Check if item capabilities support the requested action using dynamic mappings."""
        # Check direct capability matches
        for capability in capabilities:
            if capability in move:
                return True
        
        # Check for action-capability mappings from world rules
        for action, valid_capabilities in action_mappings.items():
            if action in move:
                return any(cap in valid_capabilities for cap in capabilities)
        
        # Check for cutting actions (common pattern)
        cutting_actions = ['slash', 'cut', 'hack', 'chop']
        if any(action in move for action in cutting_actions):
            cutting_capabilities = ['slash', 'cut', 'hack', 'chop']
            return any(cap in cutting_capabilities for cap in capabilities)
        
        return False
    
    async def _special_effects_support_action_dynamic(self, move: str, special_effects: str, world_context: Dict[str, Any]) -> bool:
        """Check if special effects support the requested action based on world rules."""
        if not special_effects or special_effects == 'no special effects':
            return False
        
        world_rules = world_context.get('world_rules', {}).get('world_specific_rules', {})
        
        # Check for magic-related actions
        if world_rules.get('magic_allowed', True):
            magic_actions = ['cast', 'spell', 'magic', 'teleport', 'levitate', 'summon']
            if any(action in move for action in magic_actions):
                magic_effects = ['magic', 'spell', 'enchant', 'mystical', 'arcane', 'supernatural']
                return any(effect in special_effects for effect in magic_effects)
        
        # Check for technology-related actions
        if world_rules.get('technology_allowed', True):
            tech_actions = ['hack', 'access', 'control', 'analyze', 'scan', 'interface']
            if any(action in move for action in tech_actions):
                tech_effects = ['technology', 'digital', 'electronic', 'cybernetic', 'holographic']
                return any(effect in special_effects for effect in tech_effects)
        
        return False
    
    async def _identify_missing_equipment_dynamic(self, move: str, world_context: Dict[str, Any]) -> str:
        """Identify what equipment is missing based on world context."""
        move_lower = move.lower()
        
        # Fallback to common equipment keywords
        equipment_keywords = {
            'sword': 'sword or blade weapon',
            'knife': 'knife or dagger',
            'bow': 'bow or ranged weapon',
            'gun': 'firearm',
            'staff': 'magical staff or wand',
            'shield': 'shield or defensive item',
            'armor': 'armor or protective gear',
            'potion': 'healing potion or medicine',
            'key': 'key or lockpick',
            'tool': 'tool or utility item',
            'cyberdeck': 'cyberdeck or computer interface',
            'implant': 'cybernetic implant'
        }
        
        for keyword, description in equipment_keywords.items():
            if keyword in move_lower:
                return description
        
        return "appropriate equipment"
    
    async def _generate_suggestion_dynamic(self, move: str, inventory_items: List[Dict[str, Any]], world_context: Dict[str, Any]) -> Optional[str]:
        """Generate a helpful suggestion based on available inventory and world context."""
        if not inventory_items:
            basic_actions = world_context.get('world_rules', {}).get('basic_actions', ['punch', 'kick', 'dodge'])
            return f"Try basic actions like {', '.join(basic_actions[:3])}"
        
        # Get all available capabilities
        all_capabilities = []
        for item in inventory_items:
            all_capabilities.extend(item['capabilities'])
        
        if all_capabilities:
            unique_capabilities = list(set(all_capabilities))
            return f"Available actions: {', '.join(unique_capabilities[:5])}"
        
        basic_actions = world_context.get('world_rules', {}).get('basic_actions', ['punch', 'kick', 'dodge'])
        return f"Try basic actions like {', '.join(basic_actions[:3])}"
    
    async def _ai_validate_action(self, move: str, inventory_items: List[Dict[str, Any]], world_context: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """Use AI to validate ambiguous actions."""
        try:
            # Create context for AI
            inventory_summary = []
            for item in inventory_items:
                inventory_summary.append(f"{item['name']} (rarity {item['rarity']}): {item['description']} - capabilities: {', '.join(item['capabilities'])}")
            
            world_theme = world_context.get('world_theme', 'generic')
            validation_mode = world_context.get('world_rules', {}).get('validation_mode', 'adaptive')
            
            prompt = f"""
Validate if this action is possible in a {world_theme} world with {validation_mode} validation rules.

Player wants to: "{move}"

Player's inventory:
{chr(10).join(inventory_summary)}

World context: {world_context.get('main_quest', '')}

Rules:
- If the action requires equipment the player doesn't have = INVALID
- If the action is basic physical movement/interaction = VALID
- If the action matches the player's item capabilities = VALID
- If unsure and validation mode is permissive = VALID
- If unsure and validation mode is strict = INVALID

Return JSON:
{{
    "valid": true/false,
    "reason": "explanation",
    "suggestion": "helpful suggestion or null"
}}
"""
            
            response = await self.game_manager.ai_handler.generate_text(prompt)
            
            try:
                result = json.loads(response)
                is_valid = result.get('valid', True)
                reason = result.get('reason', 'AI validation')
                suggestion = result.get('suggestion')
                
                logger.info(f"[DynamicMoveValidator] AI validation result: {is_valid} - {reason}")
                return is_valid, reason, suggestion
                
            except json.JSONDecodeError:
                logger.warning(f"[DynamicMoveValidator] Failed to parse AI response, allowing move")
                return True, "AI validation failed - allowing move", None
                
        except Exception as e:
            logger.error(f"[DynamicMoveValidator] Error in AI validation: {str(e)}")
            return True, "AI validation error - allowing move", None
    
    async def _item_description_supports_action_dynamic(self, move: str, description: str, world_context: Dict[str, Any]) -> bool:
        """Check if item description suggests it can support the action using AI."""
        try:
            # Use AI to determine if the item description suggests it can perform the action
            prompt = f"""
            Can this item perform the requested action based on its description?
            
            Item description: "{description}"
            Player wants to: "{move}"
            
            Consider:
            - What the item is and what it's designed for
            - Whether the action matches the item's capabilities
            - If the item's description suggests it could enable this action
            
            Return JSON: {{"can_perform": true/false, "reason": "brief explanation"}}
            """
            
            response = await self.game_manager.ai_handler.generate_text(prompt)
            
            try:
                result = json.loads(response)
                can_perform = result.get('can_perform', False)
                logger.debug(f"[DynamicMoveValidator] AI item description check: {can_perform} - {result.get('reason', 'No reason')}")
                return can_perform
            except json.JSONDecodeError:
                logger.warning(f"[DynamicMoveValidator] Failed to parse AI item description response")
                return False
                
        except Exception as e:
            logger.error(f"[DynamicMoveValidator] Error in AI item description validation: {str(e)}")
            return False

# Backward compatibility - keep the old class name
class MoveValidator(DynamicMoveValidator):
    """Backward compatibility wrapper for the old MoveValidator interface."""
    pass 