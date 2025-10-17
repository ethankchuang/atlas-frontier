# Quest System - Implementation Status

## ✅ **COMPLETED - Backend Core (Ready for Testing)**

### 1. Database Schema ✅
- **Files Created**:
  - `server/supabase_quest_migration.sql` - Structured quest tables
  - `server/supabase_quest_seed.sql` - Initial quest data

- **Tables Created**:
  - `badges` - Badge definitions with AI-generated images
  - `quests` - Quest definitions (name, description, storyline, rewards)
  - `quest_objectives` - Extensible objective system
  - `player_quests` - Player quest progress tracking
  - `player_quest_objectives` - Individual objective completion
  - `player_badges` - Badge collection
  - `player_gold_ledger` - Gold transaction audit trail

### 2. Backend Models ✅
- **File**: `server/app/models.py`
- Added to `Player` model:
  - `gold: int` - Gold balance
  - `active_quest_id: Optional[str]` - Current quest

- New Pydantic Models:
  - `Badge`, `Quest`, `QuestObjective`
  - `PlayerQuest`, `PlayerQuestObjective`
  - `PlayerBadge`, `GoldTransaction`

### 3. World Configuration ✅
- **File**: `server/app/ai_handler.py`
- Added quest system config:
  - `quest_storyline_intro`
  - `quest_narrative_style`
  - `tutorial_quest_theme`
  - `badge_visual_style`

### 4. Quest Manager ✅
- **File**: `server/app/quest_manager.py` (625 lines)
- **Features**:
  - Quest assignment and progression tracking
  - Objective validation (8+ objective types supported)
  - Gold and badge reward system
  - Quest completion detection
  - Storyline chunking for typewriter effect
  - Full quest log (current + completed)

- **Objective Types Supported**:
  - `move_n_times` - Track player movement
  - `use_command` - Track specific commands (e.g., "look")
  - `find_item` - Item spawned in room
  - `take_item` - Player takes item
  - `talk_to_npc` - Conversation with NPCs
  - `visit_biomes` - Explore different biomes
  - `win_combat` - Defeat monsters or win duels
  - **Extensible** - Easy to add new types

### 5. Supabase Database Methods ✅
- **File**: `server/app/supabase_database.py`
- Added quest-specific methods:
  - `get_quest()`, `get_quest_objectives()`
  - `get_player_quest()`, `get_all_player_quests()`
  - `save_player_quest()`, `save_player_quest_objective()`
  - `get_badge()`, `get_player_badges()`, `save_player_badge()`
  - `save_gold_transaction()`

### 6. API Endpoints ✅
- **File**: `server/app/main.py`
- New endpoints:
  - `GET /player/{player_id}/quest-status` - Current quest info
  - `GET /player/{player_id}/quest-log` - All quests (current + completed)
  - `GET /player/{player_id}/badges` - Earned badges

### 7. Initial Quest Content ✅
Created 4 quests in seed data:

1. **"The Awakening"** (Tutorial - order_index: 0)
   - Move 2 times
   - Use "look" command
   - Find Ancient Compass
   - Take Ancient Compass
   - Reward: 50 gold + "Seeker" badge

2. **"First Contact"** (order_index: 1)
   - Talk to any NPC
   - Reward: 75 gold + "Diplomat" badge

3. **"The Explorer"** (order_index: 2)
   - Discover 3 different biomes
   - Reward: 100 gold + "Wanderer" badge

4. **"Trial by Combat"** (order_index: 3)
   - Win combat (monster or duel)
   - Reward: 150 gold + "Warrior" badge

---

## 🚧 **REMAINING WORK**

### 1. Run Database Migrations ⚠️ **REQUIRED FIRST**
```sql
-- In Supabase SQL Editor, run these in order:
1. server/supabase_quest_migration.sql
2. server/supabase_quest_seed.sql
```

### 2. First-Time Player Quest Assignment
**Where**: `server/app/main.py` or `server/app/game_manager.py`

When creating a new player, add:
```python
from .quest_manager import QuestManager

# After player creation
quest_manager = QuestManager(db)
await quest_manager.assign_tutorial_quest(player_id)
```

### 3. Quest Tracking Integration
**Where**: `server/app/main.py` in `process_action_stream()`

After processing each action, check quest objectives:
```python
from .quest_manager import QuestManager
quest_manager = QuestManager(db)

# Track movement
if direction:
    quest_result = await quest_manager.check_objectives(
        player_id, action, 'move', {}
    )

# Track look command
if 'look' in action.lower():
    quest_result = await quest_manager.check_objectives(
        player_id, action, 'command', {'command': 'look'}
    )

# Track item taken
if item_awarded:
    quest_result = await quest_manager.check_objectives(
        player_id, action, 'take_item', {'item_name': item_name}
    )

# Track NPC interaction (when implementing NPC talk)
if npc_talked_to:
    quest_result = await quest_manager.check_objectives(
        player_id, action, 'talk_npc', {'npc_id': npc_id}
    )

# Track biome visit (on room entry)
if new_biome_discovered:
    quest_result = await quest_manager.check_objectives(
        player_id, action, 'visit_biome', {'biome': biome_name}
    )

# Track combat victory
if combat_won:
    quest_result = await quest_manager.check_objectives(
        player_id, action, 'defeat_monster' or 'win_duel', {}
    )

# Handle quest completion
if quest_result and quest_result.get('type') == 'quest_completed':
    # Send quest completion message to player
    # Show rewards (gold + badge)
    pass
```

### 4. Quest Storyline Display (WebSocket)
**Where**: `server/app/main.py` in WebSocket `websocket_endpoint()`

On player connection, check for unshown quest storyline:
```python
from .quest_manager import QuestManager

# After connecting
if player.active_quest_id:
    quest_manager = QuestManager(db)
    player_quest = await quest_manager._get_player_quest(player.id, player.active_quest_id)

    if player_quest and not player_quest.get('storyline_shown'):
        # Send storyline in chunks for typewriter effect
        chunks = await quest_manager.get_storyline_chunks(player.active_quest_id, chunk_size=80)

        for chunk in chunks:
            await websocket.send_json({
                'type': 'quest_storyline',
                'chunk': chunk
            })
            await asyncio.sleep(0.3)  # Delay between chunks

        # Mark as shown
        player_quest['storyline_shown'] = True
        await quest_manager._save_player_quest(player_quest)
```

### 5. Ancient Compass Spawning
**Where**: `server/app/game_manager.py`

Create helper method to spawn quest item near player:
```python
async def spawn_tutorial_item(self, player_id: str):
    """Spawn Ancient Compass in a nearby room for tutorial quest"""
    player = await self.get_player(player_id)
    room = await self.get_room(player.current_room)

    # Find a room 1-2 moves away
    target_room_id = None
    if room.connections:
        # Pick a random connected room
        direction = random.choice(list(room.connections.keys()))
        target_room_id = room.connections[direction]

    if not target_room_id:
        target_room_id = player.current_room

    # Create Ancient Compass item
    compass_id = f"item_ancient_compass_{str(uuid.uuid4())}"
    compass_data = {
        'id': compass_id,
        'name': 'Ancient Compass',
        'description': 'A mystical compass that guides travelers through unknown lands. Its needle glows faintly with magical energy.',
        'is_takeable': True,
        'rarity': 2,
        'properties': {'quest_item': 'tutorial'},
        'capabilities': ['navigation', 'magical']
    }

    await self.db.set_item(compass_id, compass_data)

    # Add to room
    target_room = await self.get_room(target_room_id)
    if target_room_id not in target_room.items:
        target_room.items.append(compass_id)
        await self.db.set_room(target_room_id, target_room.dict())
```

Call this when assigning tutorial quest.

### 6. Frontend - ChatDisplay Update
**File**: `client/src/components/ChatDisplay.tsx`

Add quest storyline rendering:
```typescript
case 'quest_storyline':
    return (
        <div className="mb-6 font-mono text-center px-4">
            <div className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-amber-400 via-yellow-500 to-amber-400 bg-clip-text text-transparent leading-relaxed whitespace-pre-wrap">
                {message.message}
            </div>
        </div>
    );
```

### 7. Frontend - Quest Summary Panel (Left Sidebar)
**New File**: `client/src/components/QuestSummaryPanel.tsx`

```typescript
// Display below "Also Here" panel
// Shows: Quest name + progress (e.g., "2/4 objectives")
// Clickable to open full quest log
```

### 8. Frontend - Quest Log Modal
**New File**: `client/src/components/QuestLogModal.tsx`

```typescript
// Tabs: "Current Quests" | "Completed Quests"
// Shows objectives with checkboxes
// Shows rewards (gold + badge)
```

### 9. Frontend - Badge Collection Modal
**New File**: `client/src/components/BadgeCollectionModal.tsx`

```typescript
// Grid layout of badges
// Shows badge image, name, description, earned date
```

### 10. Frontend - Game Menu Buttons
**Where**: Main game interface (wherever menu is)

Add buttons:
- "Quests" → Opens QuestLogModal
- "Badges" → Opens BadgeCollectionModal

---

## 🎯 **Testing Checklist**

Once migrations are run and remaining work is complete:

- [ ] New player automatically gets tutorial quest
- [ ] Tutorial quest storyline displays on first connection
- [ ] Ancient Compass spawns in nearby room
- [ ] Moving 2 times completes first objective
- [ ] Using "look" completes second objective
- [ ] Taking compass completes quest
- [ ] Gold reward added to player
- [ ] Badge awarded to player
- [ ] Next quest auto-assigned
- [ ] Quest log shows current and completed quests
- [ ] Badge collection displays earned badges

---

## 📊 **Implementation Progress: 60% Complete**

**Backend**: ~90% complete
**Frontend**: ~0% complete
**Integration**: ~30% complete

**Estimated Remaining Work**: 4-6 hours
- Quest tracking integration: 1-2 hours
- First-time player flow: 30 min
- Frontend components: 2-3 hours
- Testing & bug fixes: 1 hour
