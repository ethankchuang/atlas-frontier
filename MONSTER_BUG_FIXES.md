# Monster Bug Fixes - "Unknown Monster" Issue

## Problem Summary
Players encountered a bug where entering a room with a corrupted monster would:
1. Display "unknown monster" as the creature's name
2. Immediately send player into combat (even for aggressive monsters where retreat should be allowed)
3. Cause the game to hang when trying to fight the monster

## Root Causes Identified

### 1. Missing Monster Validation During Creation
- Monster generation involved multiple steps (AI generation → parsing → database save)
- If any step failed partially, corrupted monster data could be saved
- No validation ensured all required fields were present and valid

### 2. No Error Handling for Corrupt Monsters
- When combat or behavior systems encountered corrupt monsters, they would fail silently or hang
- Missing fields caused `get()` fallbacks to "Unknown Monster" but combat still proceeded
- No cleanup mechanism to remove corrupt monsters from the game

### 3. Lack of Database Transaction Safety
- Monster creation wasn't atomic (all-or-nothing)
- Partial saves could occur, leaving incomplete data in the database
- No verification that save operations actually succeeded

## Fixes Implemented

### Fix #1: Monster Data Validation (`game_manager.py`)

Added `_validate_monster_data()` method that ensures:
- All required fields exist (`id`, `name`, `description`, `aggressiveness`, `intelligence`, `size`, `location`, `health`, `is_alive`)
- Correct data types for each field
- String fields are not empty
- Enum values are valid (aggressiveness, intelligence, size)
- Health is positive
- Name and description length limits are enforced

**Location:** `server/app/game_manager.py:204-257`

### Fix #3: Error Handling in Combat System (`combat.py`)

Added validation in `generate_and_submit_monster_move()`:
- Checks if monster_data exists before processing
- Validates all required fields are present
- If corrupt monster detected:
  - Cancels the duel immediately
  - Removes monster from the room
  - Deletes monster from database
  - Notifies player with clear error message
  - Allows player to continue without hanging

**Location:** `server/app/combat.py:346-531`

### Fix #3: Error Handling in Monster Behavior (`monster_behavior.py`)

Added validation in multiple locations:

1. **Room Entry (`handle_player_room_entry`):**
   - Validates monster data when player enters room
   - Removes corrupt monsters before they can interact
   - **Location:** `server/app/monster_behavior.py:78-102`

2. **Aggressive Combat Initiation (`handle_aggressive_combat_initiation`):**
   - Validates monster before initiating combat
   - Returns friendly message if monster is corrupt
   - Cleans up corrupt monster automatically
   - **Location:** `server/app/monster_behavior.py:496-540`

3. **Territorial Combat Initiation (`handle_territorial_combat_initiation`):**
   - Same validation for territorial monsters
   - **Location:** `server/app/monster_behavior.py:390-420`

4. **Added Helper Method (`_cleanup_corrupt_monster`):**
   - Centralized cleanup logic
   - Removes monster from room, database, and tracking
   - **Location:** `server/app/monster_behavior.py:365-388`

### Fix #4: Database Transaction Safety (`game_manager.py`)

Enhanced `generate_room_monsters()` method:
- Validates generated data before saving
- Strips whitespace from name/description
- Verifies save operation by reading back from database
- Rolls back on failure (doesn't add monster_id to list)
- Cleans up partial monsters if creation fails
- Logs detailed error messages for debugging

**Location:** `server/app/game_manager.py:259-364`

## Testing Recommendations

1. **Monitor Logs:** Watch for messages like:
   - `[Monsters] Monster validation failed:`
   - `[MonsterBehavior] Corrupt monster {id} detected`
   - These indicate the fixes are catching and preventing corrupt monsters

2. **Test AI Generation Failures:**
   - The system should gracefully handle AI timeouts
   - Monsters with missing names/descriptions should be rejected
   - No "Unknown Monster" should appear in-game

3. **Test Combat with Existing Corrupt Monsters:**
   - If any corrupt monsters exist in the database, they should be:
     - Detected when player enters room
     - Removed automatically
     - Player shown friendly message

4. **Clean Up Existing Corrupt Monsters:**
   - Run `check_rooms.py` to identify rooms with corrupt monsters
   - The game will now auto-clean them when discovered
   - Or manually clean database if needed

## Summary

All three requested fixes have been implemented:
- ✅ **Fix #1:** Validation when creating monsters
- ✅ **Fix #3:** Error handling for corrupt monsters  
- ✅ **Fix #4:** Database transaction safety

The game will now:
- Prevent corrupt monsters from being created
- Auto-detect and remove any existing corrupt monsters
- Never hang or crash when encountering corrupt data
- Always show player-friendly messages when issues occur

## Files Modified

1. `server/app/game_manager.py` - Added validation and transaction safety
2. `server/app/combat.py` - Added corrupt monster error handling
3. `server/app/monster_behavior.py` - Added validation and cleanup helpers

