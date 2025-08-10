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