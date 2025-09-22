# Admin Utilities

This directory contains admin utilities for managing and viewing the game's stored data.

## Message Viewer (`view_messages.py`)

A comprehensive tool to view all stored message data including player actions, AI responses, chat messages, and game sessions.

### Usage

```bash
# View summary of all data
python3 view_messages.py --type summary

# View all action records (player inputs + AI responses)
python3 view_messages.py --type action

# View chat messages
python3 view_messages.py --type chat

# View game sessions
python3 view_messages.py --type session

# View all data types
python3 view_messages.py --type all

# Filter by specific player
python3 view_messages.py --type action --player player_123

# Filter by specific room
python3 view_messages.py --type action --room room_start

# Limit number of records shown
python3 view_messages.py --type action --limit 10

# Export all data to JSON file
python3 view_messages.py --export data_export.json
```

### Command Line Options

- `--type`: Type of data to view (`action`, `chat`, `session`, `all`, `summary`, `export`)
- `--player`: Filter by specific player ID
- `--room`: Filter by specific room ID  
- `--limit`: Maximum number of records to show (default: 50)
- `--export`: Export data to specified JSON filename

### Data Types

#### Action Records
- **Player Input**: The exact text the player typed
- **AI Response**: The AI's narrative response
- **Timestamp**: When the action occurred
- **Room**: Which room the action took place in
- **Metadata**: Additional context (room title, NPCs present, AI model used)
- **Updates**: Game state changes that occurred

#### Chat Messages
- **Player Messages**: Text chat between players
- **System Messages**: Game system notifications
- **Timestamps**: When messages were sent
- **Room Context**: Which room the chat occurred in

#### Game Sessions
- **Session Tracking**: Player session information
- **Start Times**: When sessions began
- **Action Counts**: Total actions per session
- **Rooms Visited**: List of rooms explored
- **Items Obtained**: Items collected during session

## Item Viewer (`view_items.py`)

A comprehensive tool to view all items in the game database, focusing on 2-star and above items since 1-star items are generated on-demand.

### Usage

```bash
# View all 2-star and above items (default)
python3 view_items.py

# View all 3-star and above items
python3 view_items.py --min-rarity 3

# View only 4-star legendary items
python3 view_items.py --rarity 4

# Filter by room name
python3 view_items.py --room "forest"

# Filter by item name
python3 view_items.py --item "sword"

# Combine filters
python3 view_items.py --min-rarity 3 --room "cave" --item "crystal"
```

### Command Line Options

- `--min-rarity`: Minimum rarity to display (1-4, default: 2)
- `--rarity`: Show only specific rarity level (1, 2, 3, or 4)
- `--room`: Filter by room name or ID (partial match)
- `--item`: Filter by item name (partial match)

### Output Format

For each item, displays:
- **Name**: Item name
- **ID**: Unique item identifier
- **Rarity**: Star rating and rarity name (e.g., "★★★ (Rare)")
- **Location**: Room title and ID where the item is located
- **Description**: Item description (truncated if long)
- **Capabilities**: List of what the player can do with the item
- **Properties**: Additional item properties and stats

### Summary Statistics

At the end, shows:
- Total items found
- Breakdown by rarity level
- Breakdown by room location

## Biome 3-Star Item Viewer (`view_biome_three_star_items.py`)

A comprehensive tool to view all biomes, their preallocated 3-star rooms, and the actual 3-star items.

### Usage

```bash
# View summary of all biomes and their 3-star items (default)
python3 view_biome_three_star_items.py

# View summary only
python3 view_biome_three_star_items.py summary

# View detailed information for each biome
python3 view_biome_three_star_items.py detailed

# Export all biome data to JSON file
python3 view_biome_three_star_items.py export

# View all information (summary + detailed + export)
python3 view_biome_three_star_items.py all
```

### Command Line Options

- `summary`: Show summary statistics and overview of all biomes
- `detailed`: Show detailed information for each biome including item data
- `export`: Export all biome data to JSON file
- `all`: Run all commands (summary + detailed + export)

### Output Format

#### Summary View
- **Total biomes**: Count of all biomes in the database
- **Biomes with 3-star rooms**: Count of biomes that have preallocated 3-star rooms
- **Biomes with 3-star items**: Count of biomes that actually have 3-star items generated
- **Coverage percentage**: Percentage of biomes with 3-star rooms

For each biome:
- **Name and description**: Biome identification
- **Color**: Hex color code for the biome
- **3-star room**: Room ID where the 3-star item should be
- **Coordinates**: World coordinates (x, y) of the 3-star room
- **3-star item**: Actual item details if generated

#### Detailed View
- Complete information for each biome including:
  - Full item details (ID, name, description, capabilities)
  - Room and coordinate information
  - Status indicators for room and item existence

#### Export Format
- JSON file containing all biome data with timestamps
- Useful for data analysis and backup purposes

### 3-Star Item System

This tool helps monitor the new preallocation system where:
1. **New biomes** automatically get a preallocated 3-star room when created
2. **3-star rooms** are placed at deterministic coordinates within each biome
3. **3-star items** are generated when players visit the designated room
4. **Guaranteed coverage**: Every biome is guaranteed to have exactly one 3-star room

### Example Output

```
📊 SUMMARY:
   Total biomes: 12
   Biomes with 3-star rooms: 12
   Biomes with 3-star items: 8
   Coverage: 100.0% have 3-star rooms

🌍 FOREST
   Description: A dense woodland with towering trees
   Color: #228B22
   ✅ 3-star room: room_0_0
   📍 Coordinates: (0, 0)
   ⭐ 3-star item: Ancient Forest Staff
      Description: A gnarled staff carved from ancient oak
      Capabilities: cast nature spells, commune with animals, heal wounds
```

## Debug Tools

### Redis Debug (`debug_redis.py`)

A debugging tool to inspect Redis storage directly:

```bash
python3 debug_redis.py
```

Shows:
- All Redis keys and their types
- Action data stored in lists
- Chat message storage
- Session information
- Raw data inspection

## Data Storage Format

### Action Records
Stored as Redis lists with key pattern: `actions:player:{player_id}`
Each action is a JSON object containing:
- Player input and AI response
- Timestamps and room context
- Game state updates
- Metadata about the interaction

### Chat Messages  
Stored as Redis lists with key pattern: `chat:room:{room_id}`
Each message is a JSON object with player info, message content, and timestamps.

### Game Sessions
Stored as Redis hashes with key pattern: `session:{session_id}`
Contains session metadata, player info, and activity tracking.

## Examples

```bash
# View recent actions for a specific player
python3 view_messages.py --type action --player player_abc123 --limit 5

# Export all data for analysis
python3 view_messages.py --export full_data_export.json

# Check what data exists
python3 view_messages.py --type summary

# Debug Redis storage issues
python3 debug_redis.py
``` 