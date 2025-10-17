# Quest System Implementation Progress

## ✅ Completed

### 1. Database Schema
- **File**: `server/supabase_quest_migration.sql`
- Created structured tables for quests, badges, objectives, and gold system
- Tables:
  - `badges` - Badge definitions with AI-generated images
  - `quests` - Quest definitions
  - `quest_objectives` - Extensible objective system
  - `player_quests` - Player quest progress
  - `player_quest_objectives` - Objective completion tracking
  - `player_badges` - Badge collection
  - `player_gold_ledger` - Gold transaction audit trail

### 2. Seed Data
- **File**: `server/supabase_quest_seed.sql`
- Created 4 initial quests:
  1. **The Awakening** (Tutorial) - Find Ancient Compass (50 gold + Seeker badge)
  2. **First Contact** - Talk to an NPC (75 gold + Diplomat badge)
  3. **The Explorer** - Discover 3 biomes (100 gold + Wanderer badge)
  4. **Trial by Combat** - Win combat (150 gold + Warrior badge)

### 3. Player Model Updates
- **File**: `server/app/models.py`
- Added `gold` and `active_quest_id` fields to Player model
- Added new models: Badge, Quest, QuestObjective, PlayerQuest, PlayerQuestObjective, PlayerBadge, GoldTransaction

### 4. WORLD_CONFIG Updates
- **File**: `server/app/ai_handler.py`
- Added quest-specific configuration:
  - `quest_storyline_intro`
  - `quest_narrative_style`
  - `tutorial_quest_theme`
  - `badge_visual_style`

### 5. Quest Manager Core
- **File**: `server/app/quest_manager.py`
- Created QuestManager class with:
  - `assign_tutorial_quest()` - Assign first quest to new players
  - `check_objectives()` - Track quest progress after each action
  - `get_storyline_chunks()` - Split storyline for typewriter effect
  - `get_player_quest_status()` - Get current quest info
  - `get_player_quest_log()` - Get all quests (current + completed)
  - `get_player_badges()` - Get earned badges
  - Gold and badge reward system

## 🚧 Remaining Work

### 1. Database Integration (Supabase)
**Files to modify**: `server/app/supabase_database.py`

Need to implement these methods:
```python
# Quest queries
async def get_quest(quest_id: str)
async def get_quest_objectives(quest_id: str)
async def get_next_quest(order_index: int)

# Player quest queries
async def get_player_quest(player_id: str, quest_id: str)
async def get_all_player_quests(player_id: str)
async def save_player_quest(player_quest: dict)

# Player objective queries
async def get_player_quest_objectives(player_quest_id: str)
async def save_player_quest_objective(objective: dict)

# Badge queries
async def get_badge(badge_id: str)
async def get_player_badges(player_id: str)
async def save_player_badge(player_badge: dict)

# Gold ledger
async def save_gold_transaction(transaction: dict)
```

### 2. Quest Tracking Integration
**File to modify**: `server/app/main.py` (in `process_action_stream` function)

Add quest tracking after each action:
```python
# After processing action, check quest objectives
quest_manager = QuestManager(db)

# Track different action types
if direction:  # Movement
    await quest_manager.check_objectives(player_id, action, 'move', {})

if 'look' in action.lower():  # Look command
    await quest_manager.check_objectives(player_id, action, 'command', {'command': 'look'})

if item_awarded:  # Item taken
    await quest_manager.check_objectives(player_id, action, 'take_item', {'item_name': item_name})

# etc for other action types
```

### 3. New Player Quest Assignment
**File to modify**: `server/app/main.py` or game manager

When a new player is created, assign tutorial quest:
```python
quest_manager = QuestManager(db)
await quest_manager.assign_tutorial_quest(player_id)
```

### 4. Quest Storyline Delivery
**File to modify**: `server/app/main.py` (WebSocket handler)

On first connection, if player has unshown quest:
```python
# Check if player has active quest with unshown storyline
if player.active_quest_id:
    player_quest = await quest_manager._get_player_quest(player.id, player.active_quest_id)
    if player_quest and not player_quest['storyline_shown']:
        # Send storyline in chunks
        chunks = await quest_manager.get_storyline_chunks(player.active_quest_id)
        for chunk in chunks:
            await websocket.send_json({
                'type': 'quest_storyline',
                'chunk': chunk
            })
        # Mark as shown
        player_quest['storyline_shown'] = True
        await quest_manager._save_player_quest(player_quest)
```

### 5. Frontend - ChatDisplay Component
**File to modify**: `client/src/components/ChatDisplay.tsx`

Add new message type rendering:
```typescript
case 'quest_storyline':
    return (
        <div className="mb-6 font-mono text-center">
            <div className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-amber-400 via-yellow-500 to-amber-400 bg-clip-text text-transparent leading-relaxed">
                {message.message}
            </div>
        </div>
    );
```

### 6. Frontend - Quest Summary Panel
**New file**: `client/src/components/QuestSummaryPanel.tsx`

Display in left sidebar under "Also Here":
- Current quest name
- Progress summary (e.g., "2/4 objectives complete")
- Clickable to open full quest log

### 7. Frontend - Quest Log Modal
**New file**: `client/src/components/QuestLogModal.tsx`

Shows:
- Current quest(s) with objectives and progress
- Completed quests
- Quest rewards (gold, badges)

### 8. Frontend - Badge Collection Modal
**New file**: `client/src/components/BadgeCollectionModal.tsx`

Shows:
- Grid of earned badges
- Badge images, names, descriptions
- Earned date

### 9. Frontend - Game Menu Updates
**File to modify**: `client/src/components/GameInterface.tsx` (or wherever menu is)

Add two new buttons:
- "Quests" button → Opens QuestLogModal
- "Badges" button → Opens BadgeCollectionModal

### 10. API Endpoints
**File to modify**: `server/app/main.py`

Add new endpoints:
```python
@app.get("/player/{player_id}/quest-status")
async def get_quest_status(player_id: str)

@app.get("/player/{player_id}/quest-log")
async def get_quest_log(player_id: str)

@app.get("/player/{player_id}/badges")
async def get_player_badges(player_id: str)
```

### 11. Ancient Compass Item Spawning
**File to modify**: `server/app/game_manager.py`

For tutorial quest, spawn Ancient Compass in a nearby room when player joins:
```python
async def spawn_quest_item(player_id: str, item_name: str, item_description: str):
    # Find a room 1-2 moves away from player's starting position
    # Create the quest item
    # Add to that room's items list
```

### 12. Badge Image Generation
**File to modify**: `server/app/ai_handler.py`

Add method to generate badge images:
```python
async def generate_badge_image(badge_name: str, badge_description: str) -> str:
    prompt = f"A {WORLD_CONFIG['badge_visual_style']}, {badge_description}, centered on shield, high quality game asset"
    return await generate_room_image(prompt, room_id=f"badge_{badge_name}")
```

## 📝 To Run Migrations

1. Run the main schema (if not already done):
```bash
# In Supabase SQL Editor
Run: server/supabase_schema.sql
```

2. Run the quest migration:
```bash
# In Supabase SQL Editor
Run: server/supabase_quest_migration.sql
```

3. Run the seed data:
```bash
# In Supabase SQL Editor
Run: server/supabase_quest_seed.sql
```

## 🎯 Next Steps Priority

1. **Database Integration** - Implement Supabase queries in `supabase_database.py`
2. **Quest Tracking** - Add to action processing in `main.py`
3. **New Player Flow** - Assign tutorial quest on player creation
4. **Frontend Components** - Build quest UI (summary panel, log, badges)
5. **Testing** - End-to-end quest completion flow

## 📋 Testing Checklist

- [ ] New player gets tutorial quest automatically
- [ ] Tutorial quest storyline displays on first connection
- [ ] Moving 2 times completes first objective
- [ ] Using "look" command completes second objective
- [ ] Ancient Compass spawns in nearby room
- [ ] Taking compass completes quest
- [ ] Gold reward added to player balance
- [ ] Badge awarded to player
- [ ] Next quest auto-assigned
- [ ] Quest log shows all quests
- [ ] Badge collection displays earned badges
