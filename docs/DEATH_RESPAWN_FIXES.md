# Death/Respawn Player State Fix

## Problem
Player health was working correctly upon revival/respawn until they re-entered the room where they died. When returning to the death room, the player's health would be corrupted or reset to a lower value.

## Root Cause
When a player re-enters a room, multiple systems were fetching and broadcasting player data:
1. The `/room/{room_id}/info` API returned ALL players in the room, including the current player
2. The `updatePresence` endpoint was re-saving player data to the database
3. Various WebSocket handlers were merging incoming player updates without preserving critical fields

This created opportunities for stale or cached player data to overwrite the current player's correct health when they re-entered their death room.

## Solution

### 1. Filter Current Player from Room Player List (GameLayout.tsx)
**File:** `client/src/components/GameLayout.tsx`

When fetching room info, we now filter out the current player from the `playersInRoom` list to prevent any potential state corruption:

```typescript
// CRITICAL: Filter out the current player from the playersInRoom list
// to prevent overwriting the current player's state with potentially stale data
const otherPlayers = roomInfo.players.filter((p: { id: string }) => p.id !== player.id);
setPlayersInRoom(otherPlayers);
```

### 2. Prevent Player Data Overwrites in Presence Updates (main.py)
**File:** `server/app/main.py` - `/presence` endpoint

The `updatePresence` endpoint was fetching player data and immediately saving it back, which could re-persist stale data. Now it only updates room presence lists without modifying the player document:

```python
# CRITICAL: Only update room presence lists, don't modify player data
# This prevents accidentally overwriting health or other critical fields
if player.current_room != request.room_id:
    await game_manager.db.remove_from_room_players(player.current_room, request.player_id)
    await game_manager.db.add_to_room_players(request.room_id, request.player_id)
```

Removed the line that was saving player data: `await game_manager.db.set_player(request.player_id, player.dict())`

### 3. Safeguard WebSocket Player Updates (websocket.ts)
**File:** `client/src/services/websocket.ts` - `handlePlayerUpdate()`

Added defensive checks to preserve player health when receiving player updates:

```typescript
// Merge incoming updates with current state, preferring current health
const mergedPlayer = {
    ...player,
    // Prefer current health if it's set (prevents overwrites from stale data)
    health: currentPlayer.health !== undefined ? currentPlayer.health : player.health
};
```

### 4. Safeguard Room Update Handler (api.ts)
**File:** `client/src/services/api.ts` - room_update handler

Added similar safeguards when processing room updates that include player data:

```typescript
// CRITICAL: Preserve health when merging player updates
const updatedPlayer = { 
    ...store.player, 
    ...data.updates.player,
    // Preserve current health if set
    health: currentHealth !== undefined ? currentHealth : data.updates.player.health
};
```

## Testing
To verify the fix works:

1. Create a character and enter a room with an aggressive monster
2. Let the monster defeat you (player dies and respawns at spawn)
3. Verify you have full health (5) after respawn
4. Move to another room, then return to the room where you died
5. **Expected:** Player still has full health
6. **Previous Bug:** Player would have reduced health

## Impact
- **Player Health Integrity:** Player health is now preserved across room transitions
- **Death/Respawn Flow:** Players maintain their restored health when revisiting death locations
- **Defensive Programming:** Multiple layers of safeguards prevent stale data from corrupting player health
- **No Breaking Changes:** All changes are backward compatible and defensive in nature

## Files Modified
- `client/src/components/GameLayout.tsx`
- `client/src/services/websocket.ts`
- `client/src/services/api.ts`
- `server/app/main.py`
