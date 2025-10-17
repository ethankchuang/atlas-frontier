# Quest Item Discovery System

## Overview

The quest system now supports **automatic item discovery** - when a player enters a room containing a quest item that completes their objective, the item is automatically added to their inventory.

This is **fully generic** and works for any quest item, not just the Ancient Compass.

## How It Works

### 1. Item Spawning (on quest assignment)

When a player is assigned a quest, items from `spawn_config` are spawned in the world **with player ownership**:

```python
# In game_manager.py - spawn_quest_items()
properties = item_config.get('properties', {})
if properties.get('quest_item'):
    properties['spawned_for_player_id'] = player_id  # <-- Player ownership!

item_data = {
    'id': item_id,
    'name': 'Ancient Compass',
    'properties': properties,  # Contains quest_item and spawned_for_player_id
    ...
}
await self.db.set_item(item_id, item_data)

# Add item to target room
target_room.items.append(item_id)
```

**Key**:
- `quest_item: true` marks this as a quest item
- `spawned_for_player_id` ensures only the correct player can take it

### 2. Discovery Detection (on every action)

Every time a player performs an action, the system checks if they're in a room with **their** quest items:

```python
# In main.py - quest tracking section (lines 2545-2605)

# Check both new_room (after movement) and current room (for other actions)
check_room = new_room if 'new_room' in locals() else room

if check_room and check_room.items:
    for room_item_id in check_room.items:
        room_item_data = await game_manager.db.get_item(room_item_id)

        # Is this a quest item?
        if room_item_data.get('properties', {}).get('quest_item'):
            # Check ownership - only process if it's THIS player's item
            spawned_for = room_item_data.get('properties', {}).get('spawned_for_player_id')

            if spawned_for and spawned_for != player_id:
                # Not this player's item, skip it
                continue

            # This is the player's quest item - check if finding it completes objective
            quest_result = await quest_manager.check_objectives(
                player_id,
                action,
                'find_item',
                {'item_name': room_item_data.get('name')}
            )
```

**Important**: Players only see and interact with quest items spawned specifically for them. Other players' quest items are invisible to them.

### 3. Auto-Take Mechanism

If the quest item completes an objective, it's automatically added to inventory:

```python
if quest_result:
    # Remove from room
    check_room.items.remove(room_item_id)
    await game_manager.db.set_room(check_room.id, check_room.dict())

    # Add to player inventory
    player.inventory.append(room_item_id)
    await game_manager.db.set_player(player_id, player.dict())

    # Notify frontend with special message
    chunk["updates"]["quest_item_found"] = {
        "id": room_item_id,
        "name": room_item_data['name'],
        "description": room_item_data['description'],
        "rarity": room_item_data.get('rarity', 1)
    }
```

### 4. Quest Objective Matching

The quest manager checks if the item matches the objective:

```python
# In quest_manager.py - _check_objective()

elif obj_type == 'find_item' and action_type == 'find_item':
    required_item = obj_data.get('item_name', '').lower()
    found_item = context.get('item_name', '').lower()
    if required_item in found_item or found_item in required_item:
        return (True, progress)  # Objective complete!
```

## When Discovery Happens

The system checks for quest items:
- ✅ **After movement** - When player enters a new room
- ✅ **After "look"** - When player looks around current room
- ✅ **After any action** - Any time the player acts in a room with quest items

This means players will discover quest items as soon as they:
1. Move into the room, OR
2. Use "look" in the room, OR
3. Do anything else in the room

## Creating New Quest Items

To add quest items to any quest:

### Step 1: Add spawn_config to quest

```sql
UPDATE quests
SET spawn_config = '{
  "items": [
    {
      "name": "Magic Amulet",
      "description": "A shimmering amulet pulsing with arcane energy",
      "rarity": 2,
      "is_takeable": true,
      "properties": {
        "quest_item": true,
        "magical": true
      },
      "capabilities": ["protection", "arcane"],
      "spawn_location": {
        "type": "nearby",
        "distance": 3
      },
      "spawn_trigger": "quest_start"
    }
  ]
}'::jsonb
WHERE id = 'quest_your_quest_id';
```

### Step 2: Add quest objective

```sql
INSERT INTO quest_objectives (id, quest_id, objective_type, objective_data, order_index, description)
VALUES (
    'obj_your_quest_find_amulet',
    'quest_your_quest_id',
    'find_item',
    '{"item_name": "Magic Amulet"}',
    0,
    'Find the Magic Amulet'
);
```

**That's it!** The system will:
1. Spawn the amulet when the quest is assigned
2. Detect when the player enters the room with it
3. Automatically add it to their inventory
4. Complete the quest objective

## Important Properties

### Required Item Properties

For quest items to work correctly, they must have:

```json
{
  "properties": {
    "quest_item": true  // <-- REQUIRED for auto-discovery
  }
}
```

Any item with `properties.quest_item = true` will trigger the discovery system.

### Optional Item Properties

You can add additional properties for quest-specific logic:

```json
{
  "properties": {
    "quest_item": true,
    "quest_id": "quest_the_awakening",  // Track which quest this is for
    "magical": true,                     // Custom properties
    "unique": true                       // Custom properties
  }
}
```

## Behavior Details

### Player Ownership System
Each quest item is spawned **specifically for one player**:
- Item has `spawned_for_player_id` property set to the player's ID
- Only that player can auto-take the item when entering the room
- Other players don't see or interact with quest items not meant for them
- Prevents cross-player item taking and interference

### Single Item Per Action
Only **one quest item** is auto-taken per action to avoid spam. If multiple quest items are in the room, they're processed one at a time.

### Item Removal
Once a quest item is taken, it's **permanently removed from the room**. This prevents items piling up.

### Multiple Players, Multiple Items
If 3 players are on the tutorial quest simultaneously:
- Player 1's compass spawns in room_1_0
- Player 2's compass spawns in room_0_1
- Player 3's compass spawns in room_1_1
- Each player only sees and can take their own compass
- No interference between players

### Frontend Notification
When a quest item is discovered, the frontend receives:

```json
{
  "updates": {
    "player": {
      "inventory": [...new inventory...]
    },
    "quest_item_found": {
      "id": "item_ancient_compass_...",
      "name": "Ancient Compass",
      "description": "A mystical compass...",
      "rarity": 2
    }
  }
}
```

The frontend can show a special discovery message or animation.

## Migration Instructions

To apply the updated quest system:

1. **Add spawn_config column** (if not already done):
   ```bash
   psql $DATABASE_URL -f server/migrations/add_spawn_config_to_quests.sql
   ```

2. **Update quest objectives**:
   ```bash
   psql $DATABASE_URL -f server/migrations/update_quest_objectives_find_item.sql
   ```

3. **Restart the server** to load the new code

## Testing

To test the quest item discovery:

1. Create a new guest player
2. They'll be assigned the tutorial quest
3. Ancient Compass spawns in adjacent room
4. When they move to that room, compass is auto-added to inventory
5. Quest objective completes

Check server logs for:
```
[Quest] Player guest_xxx found quest item 'Ancient Compass' - auto-taking
[Quest] Successfully auto-took quest item 'Ancient Compass' for player guest_xxx
```

## Future Enhancements

Potential improvements to the system:

- [ ] Add configurable discovery messages per item
- [ ] Support for "hidden" items that require specific actions to discover
- [ ] Quest items that spawn in player inventory directly (skip room placement)
- [ ] Multi-step discovery (find clue → find item)
- [ ] Quest items that require specific conditions to pick up
