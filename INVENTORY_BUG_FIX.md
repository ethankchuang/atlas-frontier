# Inventory Loss Bug Fix

## The Problem

When a player received a quest item and then moved to another room, their inventory would be reset and the item would disappear.

### Root Cause

1. **Action starts** → Player data loaded from database (line 1738)
2. **Quest item added** → Item added to inventory and saved to database (line 2700)  
3. **Movement processing** → Code used the OLD player object from step 1 as the base for updates (line 2103)
4. **Result** → The stale player data (without quest items) was used to build the final player state and sent to the client

The bug was in `/server/app/main.py` around line 2103:

```python
# OLD CODE (BUG):
base_player_dict = player.dict()  # Uses stale player from start of action!
if latest_player_data and isinstance(latest_player_data, dict):
    if 'player' in chunk.get('updates', {}) and 'inventory' not in chunk['updates']['player']:
        base_player_dict['inventory'] = latest_player_data.get('inventory', base_player_dict.get('inventory', []))
```

## The Fix

Changed to use the **latest player data from the database** as the base instead of the stale player object:

```python
# NEW CODE (FIXED):
# Use latest_player_data as base instead of stale player object
base_player_dict = latest_player_data if latest_player_data and isinstance(latest_player_data, dict) else player.dict()

# Build updated player with movement/action updates
merged_player_dict = {**base_player_dict, **player_updates}

# If updates explicitly include inventory, trust it (overrides DB)
if 'player' in chunk.get('updates', {}) and 'inventory' in chunk['updates']['player']:
    merged_player_dict['inventory'] = chunk['updates']['player']['inventory']
    logger.info(f"[Inventory] Using explicit inventory from updates: {len(chunk['updates']['player']['inventory'])} items")
else:
    logger.info(f"[Inventory] Preserving inventory from DB: {len(base_player_dict.get('inventory', []))} items")
```

## What Changed

### Before
- Used stale `player` object (from start of action) as base
- Tried to patch inventory after the fact
- Lost quest items added during the action

### After  
- Uses fresh `latest_player_data` (from database) as base
- Includes any quest items added during the action
- Only overrides if movement updates explicitly include inventory
- Added logging to track which inventory source is used

## Benefits

✅ **Quest items persist** after movement  
✅ **Any mid-action inventory changes preserved**  
✅ **Better logging** for debugging inventory issues  
✅ **Cleaner code** - simpler logic, more reliable  

## Testing

To verify the fix works:

1. **Accept a quest** that gives you an item
2. **Receive the item** (check inventory - should see it)
3. **Move to another room** (e.g., "go north")
4. **Check inventory again** - item should still be there ✓

The fix ensures that any inventory changes made during an action (quest rewards, item pickups, etc.) are preserved when the player moves to a new room.

