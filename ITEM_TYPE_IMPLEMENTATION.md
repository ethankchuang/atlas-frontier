# Item Type System Implementation

## Overview

The item generation system has been updated to include item types with distinct capabilities and descriptions. Each world now generates 10 different item types at initialization, and new items are generated based on these types.

## Key Features

### 1. Item Types
Each item type includes:
- **Name**: The type name (e.g., "Sword", "Magic Staff", "Helmet")
- **Description**: Detailed description of what the item type is and does
- **Capabilities**: List of specific actions/abilities the item type enables
- **Category**: Classification (weapon, armor, magic)

### 2. Contextual Item Archetypes
The system analyzes each world's theme and generates appropriate item archetypes. Available themes include:

**Medieval Fantasy Worlds:**
- Sword, Bow, Shield, Staff, Armor, Ring, Amulet, Helmet, Gauntlets, Dagger
- Focus: royal authority, noble protection, castle magic, exceptional craftsmanship

**Cyberpunk Worlds:**
- Gun, Cyberdeck, Armor, Implant, Shield, Drone, Hologram, Exoskeleton, Nanites, Visor
- Focus: hacking, neural enhancement, tech protection, digital manipulation

**Post-Apocalyptic Worlds:**
- Gun, Tool, Armor, Medicine, Shield, Crossbow, Radio, Backpack, Knife, Mask
- Focus: survival utility, scavenged materials, rugged durability, communication

**Steampunk Worlds:**
- Gun, Gear, Armor, Cog, Shield, Crossbow, Lens, Gauntlets, Blade, Helmet
- Focus: steam power, mechanical precision, industrial utility, steam enhancement

**Dark Fantasy Worlds:**
- Blade, Armor, Staff, Ring, Shield, Bow, Amulet, Gauntlets, Dagger, Helmet
- Focus: shadow control, corruption, stealth, fear aura, dark magic

**Elemental Worlds:**
- Sword, Staff, Bow, Armor, Amulet, Dagger, Ring, Shield, Gauntlets, Helmet
- Focus: elemental control, fire/ice/lightning/earth/water magic

**Nature Worlds:**
- Bow, Staff, Armor, Amulet, Shield, Whip, Ring, Helmet, Dagger, Gauntlets
- Focus: nature magic, plant control, healing, animal communication

**Mountain Worlds:**
- Axe, Staff, Armor, Ring, Shield, Bow, Amulet, Gauntlets, Dagger, Helmet
- Focus: stone control, mountain strength, cold resistance, peak vision

**Maritime Worlds:**
- Sword, Staff, Armor, Ring, Shield, Bow, Amulet, Gauntlets, Dagger, Helmet
- Focus: water control, aquatic abilities, ocean magic, tidal force

**Magical Worlds:**
- Sword, Staff, Armor, Ring, Shield, Bow, Amulet, Gauntlets, Dagger, Helmet
- Focus: arcane magic, spell enhancement, magical energy, spell amplification

**Military Worlds:**
- Sword, Staff, Armor, Ring, Shield, Bow, Amulet, Gauntlets, Dagger, Helmet
- Focus: combat mastery, war tactics, military precision, battle enhancement

**Ancient Ruins Worlds:**
- Sword, Staff, Armor, Ring, Shield, Bow, Amulet, Gauntlets, Dagger, Helmet
- Focus: ancient magic, forgotten power, ruin control, time manipulation

**Artifact Hunter Worlds:**
- Sword, Shield, Artifact, Amulet, Staff, Armor, Map, Bow, Ring, Helmet
- Focus: artifact detection, magical protection, treasure hunting

### 3. World-Specific Item Types
- Each world generates exactly 10 item types at initialization
- Types are selected based on the world seed for consistency
- Ensures variety across categories (weapon, armor, magic)
- Types are stored in the database and persist for the world

#### Generation Process
The item type generation follows a contextual, two-step process:

**Theme Analysis**
- Analyzes world seed and main quest for thematic keywords
- Determines world theme (artifact_hunter, dark_fantasy, elemental, etc.)
- Selects appropriate item types for the world's theme

**Step 1: Category Representation**
- Ensures at least one item type from each major category (weapon, armor, magic)
- Randomly selects one type from each category to guarantee diversity
- This ensures every world has basic combat capabilities

**Step 2: Remaining Slot Filling**
- Fills the remaining 7 slots (10 total - 3 from step 1)
- Prioritizes types from categories not yet represented
- Once all categories are represented, selects randomly from remaining types
- Final list is shuffled for variety

**Consistency Guarantee**
- Uses world seed hash to set random seed
- Same world seed always produces the same 10 item types
- Different world seeds produce different type combinations

**Theme Detection**
The system analyzes quest keywords to determine themes:
- **Medieval**: castle, kingdom, royal, noble
- **Cyberpunk**: cyber, tech, digital, hack, neural, robot
- **Post-Apocalyptic**: apocalypse, survival, scavenge, wasteland, ruin
- **Steampunk**: steam, mechanical, gear, industrial, clockwork
- **Dark Fantasy**: darkness, shadow, evil, corruption
- **Elemental**: elemental, fire, water, earth, air
- **Nature**: forest, nature, grove, tree
- **Mountain**: mountain, peak, summit, cliff
- **Maritime**: ocean, sea, water, ship
- **Magical**: magic, spell, wizard, mage
- **Military**: war, battle, conflict, army
- **Ancient Ruins**: ancient, ruins, tomb, temple
- **Artifact Hunter**: crystal, gem, shard, artifact

### 4. Item Generation Process
When generating new items:
1. A random item type is selected from the world's available types
2. The AI is provided with the type's description and capabilities
3. The AI generates an item name and special effects based on the type
4. The item includes all type information (name, description, capabilities, category)
5. Rarity and special effects are still generated as before

## Implementation Details

### Files Modified/Created

1. **`server/app/templates/item_types.py`** (NEW)
   - `ItemType` class: Represents individual item types
   - `ItemTypeManager` class: Manages item types for a world
   - `generate_world_item_types()`: Creates 10 types for a world
   - `get_random_item_type()`: Selects random type for item generation

2. **`server/app/templates/items.py`** (MODIFIED)
   - Updated `GenericItemTemplate` to accept `ItemTypeManager`
   - Modified `generate_prompt()` to include item type information
   - Updated `parse_response()` to include type data in generated items

3. **`server/app/database.py`** (MODIFIED)
   - Added `get_item_types()` and `set_item_types()` methods
   - Updated `reset_world()` to clear item types
   - Fixed serialization for list data

4. **`server/app/game_manager.py`** (MODIFIED)
   - Added `ItemTypeManager` initialization
   - Updated `initialize_game()` to generate item types
   - Added `load_item_types()` for existing worlds

5. **`server/app/main.py`** (MODIFIED)
   - Updated item template creation to use item type manager
   - Added item type loading on server startup

### Database Storage
- Item types are stored in Redis under the key "item_types"
- Data format: List of dictionaries with type information
- Automatically cleared when world is reset

### Backward Compatibility
- Existing worlds without item types will generate them on next initialization
- Item generation still works without types (fallback behavior)
- No breaking changes to existing item data structure

## Usage Example

When a player receives an item reward, the system now:

1. Selects a random item type (e.g., "Sword")
2. Provides the AI with: "Create a sword that can slash, stab, parry, and block"
3. AI generates: "Ironclad Blade" with appropriate special effects
4. Item data includes:
   ```json
   {
     "name": "Ironclad Blade",
     "type": "Sword",
     "type_description": "A sharp blade designed for slashing and stabbing...",
     "type_capabilities": ["slash", "stab", "parry", "block"],
     "type_category": "weapon",
     "rarity": 3,
     "special_effects": "allows player to slice through metal"
   }
   ```

## Benefits

1. **Contextual Relevance**: Item types are specifically tailored to each world's theme and quest
2. **Thematic Coherence**: Items make sense within the world's setting and story
3. **Enhanced Immersion**: Players find items that fit the world's narrative and atmosphere
4. **Quest Integration**: Item capabilities align with the main quest objectives
5. **Variety**: Each world has a unique set of 10 thematically appropriate item types
6. **Distinctiveness**: Each type serves a specific purpose within the world's context
7. **Scalability**: Easy to add new themes and item types in the future
8. **AI Guidance**: Provides clear context to AI for better item generation
9. **Deterministic**: Same world seed always produces the same item types
10. **Balanced**: Ensures every world has representation from all major categories

## Logging

The system provides detailed logging of the generation process:

### Generation Logs
- World seed and hash used for generation
- Step-by-step selection process
- Category representation tracking
- Final type selection with capabilities

### Example Log Output
```
INFO:[generate_world_item_types] [Item Type Generation] Using seed hash: 755124622
INFO:[generate_world_item_types] [Item Type Generation] Step 1: Ensuring category representation
INFO:[generate_world_item_types] [Item Type Generation] Selected Mace for weapon category
INFO:[generate_world_item_types] [Item Type Generation] Selected Body Armor for armor category
INFO:[generate_world_item_types] [Item Type Generation] Selected Amulet for magic category
INFO:[generate_world_item_types] [Item Type Generation] Step 2: Filling 7 remaining slots from 12 available types
INFO:[generate_world_item_types] [Item Type Generation] Slot 1: Selected Crossbow (existing category: weapon)
...
INFO:[generate_world_item_types] [Item Type Generation] Final selection complete. Categories represented: ['armor', 'magic', 'weapon']
```

### Loaded Types Logs
- Shows item types loaded from database for existing worlds
- Groups types by category for easy reading
- Displays type names and capabilities

## Future Enhancements

- Add item type-specific special effects
- Implement item type compatibility for equipment slots
- Add item type-based crafting system
- Create item type-specific quests or challenges
- Add item type rarity modifiers 