# Room Preloading Implementation

## Overview

This implementation adds automatic preloading of adjacent rooms when players travel to new locations. The system generates the 4 adjacent rooms (north, south, east, west) in parallel to improve player experience by reducing loading times when moving between rooms.

## Key Features

### 1. **Parallel Room Generation**
- Preloads all 4 adjacent rooms simultaneously using `asyncio.gather()`
- Each room generation runs independently to maximize efficiency

### 2. **Concurrent Generation Protection**
- Uses Redis locks to prevent multiple processes from generating the same room
- Lock duration: 5 minutes (300 seconds) with automatic expiration
- Graceful handling when locks cannot be acquired

### 3. **Smart Preloading Logic**
- Only generates rooms that don't already exist
- Skips coordinates that are already discovered
- Handles cases where rooms are already being generated

### 4. **Background Processing**
- Preloading happens asynchronously after player movement
- Doesn't block the main game flow or streaming responses
- Players can continue playing while rooms are being generated

## Implementation Details

### Database Methods Added

```python
# Room generation status tracking
await Database.set_room_generation_status(room_id, status)
await Database.get_room_generation_status(room_id)
await Database.is_room_generation_locked(room_id)

# Concurrent generation protection
await Database.set_room_generation_lock(room_id, lock_duration=300)
await Database.release_room_generation_lock(room_id)
await Database.is_room_generation_locked(room_id)
```

### GameManager Methods Added

```python
# Main preloading method
async def preload_adjacent_rooms(self, x: int, y: int, current_room: Room, player: Player)

# Individual room preloading
async def _preload_single_room(self, x: int, y: int, direction: str, current_room: Room, player: Player)
```

### Trigger Points

1. **Player Movement**: After a player successfully moves to a new room
2. **Starting Room Creation**: When the first room is created for new players

## Room Generation Flow

### For New Rooms (Undiscovered Coordinates)

1. **Check Existing Room**: Verify if room already exists at coordinates
2. **Check Discovery Status**: Skip if coordinate already discovered
3. **Acquire Lock**: Try to get generation lock (prevents duplicates)
4. **Generate Content**: Create room description and image in parallel
5. **Save Room**: Store complete room data in database
6. **Mark Discovered**: Mark coordinate as discovered
7. **Release Lock**: Clean up generation lock
8. **Auto-Connect**: Connect to adjacent rooms

### For Existing Rooms (Discovered Coordinates)

1. **Load Room Data**: Retrieve existing room from database
2. **Update Players**: Add current player to room
3. **Return Room**: Provide room data immediately

## Error Handling

### Generation Failures
- Sets room status to "error"
- Creates fallback placeholder room
- Logs detailed error information
- Continues game flow without interruption

### Lock Conflicts
- Uses placeholder room if lock cannot be acquired
- Logs lock acquisition attempts
- Graceful degradation when concurrent generation detected

### Network/API Failures
- Handles AI generation failures gracefully
- Falls back to placeholder content
- Maintains game stability

## Performance Considerations

### Parallel Processing
- All 4 adjacent rooms generated simultaneously
- Uses `asyncio.gather()` for efficient concurrency
- Individual failures don't block other room generation

### Resource Management
- Locks automatically expire after 5 minutes
- Memory-efficient room data storage
- Background processing doesn't impact main game loop

### Caching Strategy
- Rooms are permanently stored once generated
- Discovery status prevents regeneration
- Coordinate-based lookup for fast access

## Testing

Run the test script to verify functionality:

```bash
cd server
python test_preload.py
```

This will:
- Create a test room at origin (0,0)
- Trigger preloading of adjacent rooms
- Verify all 4 rooms are created successfully
- Check generation status and discovery flags

## Benefits

1. **Improved Player Experience**: Faster room transitions
2. **Reduced Loading Times**: Rooms ready before player arrives
3. **Better World Exploration**: Seamless movement between areas
4. **Scalable Architecture**: Handles multiple concurrent players
5. **Fault Tolerance**: Graceful handling of generation failures

## Future Enhancements

- **Smart Preloading**: Only preload rooms in likely travel directions
- **Priority System**: Prioritize rooms based on player movement patterns
- **Memory Management**: Clean up unused preloaded rooms
- **Analytics**: Track preloading effectiveness and player movement patterns 