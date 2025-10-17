# Quest Item Spawning System

## Overview

The quest system now supports generic, database-driven item spawning through the `spawn_config` JSONB field in the `quests` table. This eliminates the need for hardcoded item spawning logic.

## Database Schema

### New Column: `quests.spawn_config`

Type: `JSONB`

Structure:
```json
{
  "items": [
    {
      "name": "Item Name",
      "description": "Item description text",
      "rarity": 1-5,
      "is_takeable": true/false,
      "properties": {
        "quest_item": true,
        "custom_key": "custom_value"
      },
      "capabilities": ["capability1", "capability2"],
      "spawn_location": {
        "type": "starting_room|adjacent_room|nearby|random_biome|specific_coordinates",
        "distance": 1,
        "direction_preference": "any|north|south|east|west",
        "biome": "forest",
        "coordinates": {"x": 0, "y": 0},
        "visibility": "obvious|hidden"
      },
      "spawn_trigger": "quest_start|quest_objective"
    }
  ]
}
```

## Spawn Location Types

### 1. `starting_room`
Spawns the item directly in the player's starting room.

**Example:**
```json
"spawn_location": {
  "type": "starting_room",
  "visibility": "obvious"
}
```

### 2. `adjacent_room` (default)
Spawns the item in a room directly connected to the starting room.

**Parameters:**
- `direction_preference`: (optional) Preferred direction - "north", "south", "east", "west", or "any" (default)

**Example:**
```json
"spawn_location": {
  "type": "adjacent_room",
  "direction_preference": "north",
  "visibility": "obvious"
}
```

### 3. `nearby`
Spawns the item within N rooms of the starting room using BFS search.

**Parameters:**
- `distance`: Number of rooms away (default: 2)

**Example:**
```json
"spawn_location": {
  "type": "nearby",
  "distance": 3,
  "visibility": "hidden"
}
```

### 4. `random_biome` (not yet implemented)
Will spawn the item in a random room of a specific biome.

**Parameters:**
- `biome`: The biome type to spawn in

### 5. `specific_coordinates` (not yet implemented)
Will spawn the item at specific world coordinates.

**Parameters:**
- `coordinates`: Object with `x` and `y` values

## Spawn Triggers

### `quest_start`
Item spawns immediately when the quest is assigned to the player. This is the most common trigger for tutorial/starter items.

### `quest_objective` (future)
Item spawns when a specific quest objective is reached.

## Example: Ancient Compass (Tutorial Quest)

```json
{
  "items": [
    {
      "name": "Ancient Compass",
      "description": "A mystical compass that guides travelers through unknown lands. Its needle glows faintly with magical energy, pointing toward your destiny.",
      "rarity": 2,
      "is_takeable": true,
      "properties": {
        "quest_item": true,
        "magical": true
      },
      "capabilities": ["navigation", "magical_guidance"],
      "spawn_location": {
        "type": "adjacent_room",
        "direction_preference": "any",
        "visibility": "obvious"
      },
      "spawn_trigger": "quest_start"
    }
  ]
}
```

## Migration Instructions

1. Run the migration to add the `spawn_config` column:
   ```bash
   psql -h <host> -U <user> -d <database> -f server/migrations/add_spawn_config_to_quests.sql
   ```

2. The migration will automatically update the tutorial quest with the Ancient Compass configuration.

3. Verify the update:
   ```sql
   SELECT id, name, spawn_config FROM quests WHERE order_index = 0;
   ```

## Code Changes

### Removed
- `GameManager.spawn_tutorial_compass()` - Removed hardcoded Ancient Compass spawning

### Added
- `GameManager.spawn_quest_items()` - Generic item spawning based on spawn_config
- `GameManager._determine_spawn_room()` - Helper to determine spawn location based on config

### Updated
- `GameManager.create_player()` - Now uses generic spawn_quest_items()
- `/auth/guest` endpoint in main.py - Now uses generic spawn_quest_items()

## Creating New Quests with Items

When creating new quests that require item spawning:

1. Add your quest to the `quests` table
2. Add a `spawn_config` JSONB field with your item configuration
3. The item will automatically spawn when the quest is assigned
4. No code changes required!

## Future Enhancements

- [ ] Implement `random_biome` spawn type
- [ ] Implement `specific_coordinates` spawn type
- [ ] Add `quest_objective` spawn trigger support
- [ ] Add `visibility` parameter to control item discoverability
- [ ] Add support for multiple items per quest
- [ ] Add conditional spawning (spawn only if player meets certain criteria)
