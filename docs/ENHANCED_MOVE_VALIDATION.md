# Enhanced Move Validation System

## Overview

The move validation system has been significantly enhanced to use item types and their capabilities for rigid validation during combat. This system ensures that players can only perform actions that are supported by their current inventory and equipment.

## Key Features

### 1. Rigid Equipment Validation
- **Item Type Integration**: Moves are validated against the actual item types in the player's inventory
- **Capability Checking**: Each item type has specific capabilities (e.g., Sword: ["slash", "stab", "cut", "defend"])
- **Special Effects Support**: Items with special effects can enable additional actions
- **Missing Equipment Detection**: Clear feedback when required equipment is not available

### 2. Basic Combat Actions
The following actions are always valid and don't require equipment:
- **Physical Combat**: punch, kick, tackle, grapple, wrestle
- **Defensive Maneuvers**: dodge, block, parry, sidestep, duck
- **Movement**: jump, roll, crawl, climb, run, walk, sneak, hide
- **Basic Actions**: headbutt, elbow, knee, shoulder, charge

### 3. Equipment-Requiring Actions
Actions that require specific equipment are validated against the player's inventory:

#### Weapon Actions
- **Slashing**: slash, cut, hack, chop (requires sword, axe, etc.)
- **Stabbing**: stab, thrust, pierce (requires dagger, spear, etc.)
- **Ranged**: shoot, fire, aim, launch (requires bow, gun, etc.)
- **Throwing**: throw, toss, hurl (requires throwable items)

#### Magic Actions
- **Spellcasting**: cast, spell, magic, enchant (requires magical items)
- **Summoning**: summon, teleport, levitate (requires magical items)

#### Healing Actions
- **Healing**: heal, restore, cure, boost (requires potions, magical items)

#### Technology Actions
- **Hacking**: hack, access, control, analyze (requires cyberdecks, computers)
- **Scanning**: scan, detect, identify (requires scanners, sensors)

### 4. Smart Capability Mapping
The system includes intelligent mappings between actions and capabilities:
- `slash` → `["slash", "cut", "hack", "chop"]`
- `stab` → `["stab", "thrust", "pierce"]`
- `shoot` → `["shoot", "fire", "aim", "launch"]`
- `cast` → `["cast", "spell", "magic", "enchant"]`
- `heal` → `["heal", "restore", "cure"]`
- `protect` → `["protect", "defend", "guard", "shield"]`

## Implementation Details

### Core Components

#### 1. MoveValidator Class (`server/app/move_validator.py`)
```python
class MoveValidator:
    # Basic combat actions that don't require equipment
    BASIC_COMBAT_ACTIONS = {'punch', 'kick', 'tackle', 'dodge', ...}
    
    # Equipment-related action keywords
    EQUIPMENT_ACTIONS = {'slash', 'stab', 'shoot', 'cast', 'heal', ...}
    
    @staticmethod
    async def validate_move(player_id: str, move: str, game_manager) -> Tuple[bool, str, Optional[str]]:
        # Main validation logic
```

#### 2. Enhanced Equipment Validation (`server/app/main.py`)
```python
async def validate_equipment(player1_name: str, player1_move: str, player1_inventory: List[str], 
                           player2_name: str, player2_move: str, player2_inventory: List[str], 
                           game_manager: GameManager) -> Dict[str, Any]:
    # Uses MoveValidator for both players
    player1_valid, player1_reason, player1_suggestion = await MoveValidator.validate_move(player1_id, player1_move, game_manager)
    player2_valid, player2_reason, player2_suggestion = await MoveValidator.validate_move(player2_id, player2_move, game_manager)
```

#### 3. GameManager Integration (`server/app/game_manager.py`)
```python
async def get_player(self, player_id: str) -> Optional[Player]:
    """Get a player by ID for validation"""
    player_data = await self.db.get_player(player_id)
    if player_data:
        return Player(**player_data)
    return None
```

### Validation Process

1. **Player Lookup**: Get player data and inventory
2. **Inventory Analysis**: Load all items with their types and capabilities
3. **Action Classification**: Determine if action requires equipment
4. **Capability Matching**: Check if player's items support the action
5. **Special Effects Check**: Consider special effects for additional capabilities
6. **Feedback Generation**: Provide clear reasons and suggestions

### Example Validation Scenarios

#### ✅ Valid Actions
- `"punch the enemy"` → Valid (basic combat)
- `"slash with my sword"` → Valid (sword has "slash" capability)
- `"shoot my bow"` → Valid (bow has "shoot" capability)
- `"heal with my potion"` → Valid (potion has "heal" capability)

#### ❌ Invalid Actions
- `"shoot with my sword"` → Invalid (sword doesn't have "shoot" capability)
- `"cast fireball"` → Invalid (no magical items in inventory)
- `"hack the system"` → Invalid (no technology items in inventory)
- `"stab with my bow"` → Invalid (bow doesn't have "stab" capability)

## Benefits

### 1. Realistic Combat
- Players can only use equipment they actually possess
- Actions are limited by item capabilities
- No more "magic sword shooting" or impossible actions

### 2. Strategic Depth
- Players must think about their equipment choices
- Different item combinations enable different strategies
- Inventory management becomes more important

### 3. Clear Feedback
- Players get specific reasons why actions fail
- Helpful suggestions about available actions
- Better understanding of item capabilities

### 4. Extensible System
- Easy to add new item types and capabilities
- Support for special effects and unique items
- Flexible action-capability mappings

## Testing

The system includes comprehensive tests (`server/test_enhanced_move_validation.py`) that verify:

- ✅ Basic combat actions are always valid
- ✅ Valid equipment usage is properly recognized
- ✅ Invalid equipment usage is correctly rejected
- ✅ Missing equipment is properly identified
- ✅ Special effects are correctly applied
- ✅ Capability mappings work as expected

## Future Enhancements

### 1. Advanced Capabilities
- **Combo Actions**: Multiple items working together
- **Conditional Capabilities**: Items that work differently in certain situations
- **Skill Requirements**: Actions that require specific player skills

### 2. Context Awareness
- **Environmental Factors**: Actions that depend on the current room/environment
- **Time-based Capabilities**: Items that work differently at different times
- **Weather Effects**: Environmental conditions affecting item capabilities

### 3. Enhanced Feedback
- **Visual Indicators**: UI showing available actions based on inventory
- **Action Suggestions**: AI-powered recommendations for optimal equipment usage
- **Tutorial Integration**: Guided learning of item capabilities

## Integration with Combat System

The enhanced move validation integrates seamlessly with the existing combat system:

1. **Duel Validation**: Both players' moves are validated before combat resolution
2. **Invalid Move Handling**: Invalid moves are clearly communicated to players
3. **Narrative Integration**: Combat narratives reflect equipment limitations
4. **Balance Considerations**: Equipment validation helps maintain game balance

This system ensures that combat is both realistic and strategic, requiring players to think carefully about their equipment choices and how to use them effectively in battle. 