# Quest System Integration Guide

## ✅ COMPLETED (70% Done!)

### Backend Core ✅
1. ✅ Database schema (migration + seed data)
2. ✅ Quest Manager (full logic - 625 lines)
3. ✅ Supabase database methods
4. ✅ API endpoints (3 new endpoints)
5. ✅ Player model updates (gold + active_quest_id)
6. ✅ **New player quest assignment** - Tutorial quest auto-assigned
7. ✅ **Ancient Compass spawning** - Spawns in nearby room

### Files Modified
- `server/app/models.py` - Added quest models
- `server/app/ai_handler.py` - Added WORLD_CONFIG for quests
- `server/app/quest_manager.py` - **NEW FILE** (complete quest logic)
- `server/app/supabase_database.py` - Added 9 quest methods
- `server/app/main.py` - Added 3 API endpoints
- `server/app/game_manager.py` - Added tutorial quest assignment + compass spawning

---

## 🚧 CRITICAL REMAINING INTEGRATION

### 1. Quest Objective Tracking in Action Processing

**File**: `server/app/main.py` in `process_action_stream()` function (around line 1623)

Add quest tracking after processing updates. Here's the integration code:

```python
# At the top of main.py, add import
from .quest_manager import QuestManager

# In process_action_stream(), after processing updates and before final yield
# Add this section AFTER line ~2200 (after updates are processed, before returning)

# ============================================
# QUEST OBJECTIVE TRACKING
# ============================================
try:
    quest_manager = QuestManager(game_manager.db)

    # Track movement
    if updates.get("player", {}).get("direction"):
        quest_result = await quest_manager.check_objectives(
            player_id, action, 'move', {}
        )
        if quest_result:
            logger.info(f"[Quest] Movement tracked for player {player_id}")

    # Track "look" command
    if 'look' in action.lower():
        quest_result = await quest_manager.check_objectives(
            player_id, action, 'command', {'command': 'look'}
        )
        if quest_result:
            logger.info(f"[Quest] Look command tracked for player {player_id}")

    # Track item taken
    if updates.get("item_award"):
        item_name = updates["item_award"].get("item_name", "")
        if item_name:
            # Check if item was taken (not just generated)
            quest_result = await quest_manager.check_objectives(
                player_id, action, 'take_item', {'item_name': item_name}
            )
            if quest_result:
                logger.info(f"[Quest] Item taken tracked: {item_name}")

            # Also check if this completes "find_item" objective
            # (item is now in the room, player found it)
            quest_result = await quest_manager.check_objectives(
                player_id, action, 'room_has_item', {'item_name': item_name}
            )

    # Track NPC interaction (when NPC dialogue is processed)
    if updates.get("npc_dialogue") or "talk" in action.lower() or "speak" in action.lower():
        # Extract NPC from context if available
        quest_result = await quest_manager.check_objectives(
            player_id, action, 'talk_npc', {}
        )
        if quest_result:
            logger.info(f"[Quest] NPC interaction tracked")

    # Track biome visit (when player enters new room)
    if updates.get("player", {}).get("direction"):
        # Player moved, check if they entered a new biome
        player = await game_manager.get_player(player_id)
        if player and player.current_room:
            room = await game_manager.get_room(player.current_room)
            if room and room.biome:
                quest_result = await quest_manager.check_objectives(
                    player_id, action, 'visit_biome', {'biome': room.biome}
                )

    # Track combat victory (this is already handled in combat system,
    # but you can add it when combat is won)
    # This would be added in the combat resolution code

    # Handle quest completion
    if quest_result and quest_result.get('type') == 'quest_completed':
        quest_data = quest_result.get('quest', {})
        gold_reward = quest_result.get('gold_reward', 0)
        badge_id = quest_result.get('badge_id')

        # Send quest completion message to player
        completion_message = f"🎉 Quest Completed: {quest_data.get('name', 'Unknown')}!"
        if gold_reward > 0:
            completion_message += f"\n💰 Earned {gold_reward} gold!"
        if badge_id:
            badge = await quest_manager._get_badge(badge_id)
            if badge:
                completion_message += f"\n🏅 Earned badge: {badge.get('name', 'Badge')}!"

        # Store completion message
        await game_manager.db.store_player_message(player_id, {
            'id': str(uuid.uuid4()),
            'player_id': player_id,
            'room_id': room_id,
            'message': completion_message,
            'message_type': 'system',
            'timestamp': datetime.utcnow().isoformat(),
            'is_ai_response': False
        })

        logger.info(f"[Quest] Player {player_id} completed quest: {quest_data.get('name')}")

except Exception as e:
    logger.error(f"[Quest] Error tracking quest objectives: {str(e)}")
    # Don't fail the action if quest tracking fails
```

**Where to add this:**
- In `process_action_stream()` function
- After all updates are processed
- Before the final `yield` statement
- Around line 2200-2300 (after movement/item/NPC processing)

---

### 2. Quest Storyline Display on WebSocket Connection

**File**: `server/app/main.py` in `websocket_endpoint()` function

After player connects and initial room state is sent, add:

```python
# Around line 700-800, after sending initial room update
# Add quest storyline display

try:
    from .quest_manager import QuestManager
    quest_manager = QuestManager(game_manager.db)

    # Check if player has an active quest with unshown storyline
    if player.active_quest_id:
        player_quest = await quest_manager._get_player_quest(player.id, player.active_quest_id)

        if player_quest and not player_quest.get('storyline_shown', False):
            # Send storyline in chunks for typewriter effect
            chunks = await quest_manager.get_storyline_chunks(player.active_quest_id, chunk_size=80)

            for chunk in chunks:
                await websocket.send_json({
                    'type': 'quest_storyline',
                    'message': chunk,
                    'timestamp': datetime.utcnow().isoformat()
                })
                await asyncio.sleep(0.3)  # 300ms delay between chunks for typewriter effect

            # Mark storyline as shown
            player_quest['storyline_shown'] = True
            await quest_manager._save_player_quest(player_quest)

            logger.info(f"[Quest] Displayed storyline for quest {player.active_quest_id} to player {player_id}")

except Exception as e:
    logger.error(f"[Quest] Error displaying quest storyline: {str(e)}")
    # Don't fail connection if quest storyline fails
```

---

### 3. Track Combat Victories for Quests

**File**: `server/app/combat.py` or wherever combat is resolved

After a monster is defeated or a duel is won:

```python
# After combat victory
try:
    from .quest_manager import QuestManager
    quest_manager = QuestManager(db)

    # For monster combat
    quest_result = await quest_manager.check_objectives(
        player_id, "defeated monster", 'defeat_monster', {}
    )

    # For duel victory
    quest_result = await quest_manager.check_objectives(
        player_id, "won duel", 'win_duel', {}
    )

    # Handle quest completion (same as above)
    if quest_result and quest_result.get('type') == 'quest_completed':
        # Send completion message...
        pass

except Exception as e:
    logger.error(f"[Quest] Error tracking combat victory: {str(e)}")
```

---

## 🎨 FRONTEND COMPONENTS (Required)

### 1. Update ChatDisplay for Quest Storyline

**File**: `client/src/components/ChatDisplay.tsx`

Add new case in `renderMessage()`:

```typescript
case 'quest_storyline':
    return (
        <div className="mb-6 font-mono text-center px-4 py-6">
            <div className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-amber-400 via-yellow-500 to-amber-400 bg-clip-text text-transparent leading-relaxed whitespace-pre-wrap animate-fade-in">
                {message.message}
            </div>
        </div>
    );
```

Add CSS animation in your styles:
```css
@keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
}

.animate-fade-in {
    animation: fade-in 0.5s ease-in;
}
```

### 2. Quest Summary Panel (Left Sidebar)

**New File**: `client/src/components/QuestSummaryPanel.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface QuestSummaryPanelProps {
    playerId: string;
    onQuestClick: () => void;
}

export const QuestSummaryPanel: React.FC<QuestSummaryPanelProps> = ({ playerId, onQuestClick }) => {
    const [questStatus, setQuestStatus] = useState<any>(null);

    useEffect(() => {
        const fetchQuestStatus = async () => {
            try {
                const response = await api.get(`/player/${playerId}/quest-status`);
                setQuestStatus(response.data);
            } catch (error) {
                console.error('Error fetching quest status:', error);
            }
        };

        fetchQuestStatus();
        // Refresh every 30 seconds
        const interval = setInterval(fetchQuestStatus, 30000);
        return () => clearInterval(interval);
    }, [playerId]);

    if (!questStatus?.quest) {
        return null;
    }

    const completedCount = questStatus.objectives?.filter((obj: any) => obj.is_completed).length || 0;
    const totalCount = questStatus.objectives?.length || 0;

    return (
        <div
            className="bg-gray-800 bg-opacity-80 p-3 rounded-lg border border-amber-600 cursor-pointer hover:bg-opacity-90 transition-all"
            onClick={onQuestClick}
        >
            <div className="text-amber-400 font-bold text-sm mb-1">Current Quest</div>
            <div className="text-green-300 font-mono text-xs mb-2">{questStatus.quest.name}</div>
            <div className="text-gray-400 text-xs">
                Progress: {completedCount}/{totalCount}
            </div>
            <div className="w-full bg-gray-700 h-2 rounded-full mt-2">
                <div
                    className="bg-amber-500 h-2 rounded-full transition-all"
                    style={{ width: `${(completedCount / totalCount) * 100}%` }}
                />
            </div>
        </div>
    );
};
```

### 3. Quest Log Modal

**New File**: `client/src/components/QuestLogModal.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface QuestLogModalProps {
    playerId: string;
    isOpen: boolean;
    onClose: () => void;
}

export const QuestLogModal: React.FC<QuestLogModalProps> = ({ playerId, isOpen, onClose }) => {
    const [questLog, setQuestLog] = useState<any>({ current: [], completed: [] });
    const [activeTab, setActiveTab] = useState<'current' | 'completed'>('current');

    useEffect(() => {
        if (isOpen) {
            fetchQuestLog();
        }
    }, [isOpen, playerId]);

    const fetchQuestLog = async () => {
        try {
            const response = await api.get(`/player/${playerId}/quest-log`);
            setQuestLog(response.data);
        } catch (error) {
            console.error('Error fetching quest log:', error);
        }
    };

    if (!isOpen) return null;

    const quests = activeTab === 'current' ? questLog.current : questLog.completed;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-900 border-2 border-amber-600 rounded-lg w-full max-w-3xl max-h-[80vh] overflow-hidden">
                {/* Header */}
                <div className="bg-gray-800 p-4 border-b border-amber-600 flex justify-between items-center">
                    <h2 className="text-2xl font-bold text-amber-400">Quest Log</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white text-2xl"
                    >
                        ×
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-gray-700">
                    <button
                        className={`flex-1 py-3 font-bold ${activeTab === 'current' ? 'bg-gray-800 text-amber-400 border-b-2 border-amber-400' : 'text-gray-400 hover:text-white'}`}
                        onClick={() => setActiveTab('current')}
                    >
                        Current Quests ({questLog.current.length})
                    </button>
                    <button
                        className={`flex-1 py-3 font-bold ${activeTab === 'completed' ? 'bg-gray-800 text-amber-400 border-b-2 border-amber-400' : 'text-gray-400 hover:text-white'}`}
                        onClick={() => setActiveTab('completed')}
                    >
                        Completed ({questLog.completed.length})
                    </button>
                </div>

                {/* Content */}
                <div className="p-4 overflow-y-auto max-h-[60vh]">
                    {quests.length === 0 ? (
                        <div className="text-center text-gray-400 py-8">
                            No {activeTab} quests
                        </div>
                    ) : (
                        quests.map((questInfo: any, index: number) => (
                            <div key={index} className="mb-6 bg-gray-800 p-4 rounded-lg border border-gray-700">
                                <div className="flex justify-between items-start mb-2">
                                    <h3 className="text-xl font-bold text-amber-400">{questInfo.quest.name}</h3>
                                    <div className="text-yellow-500 font-bold">
                                        💰 {questInfo.quest.gold_reward} gold
                                    </div>
                                </div>
                                <p className="text-gray-300 mb-4">{questInfo.quest.description}</p>

                                {/* Objectives */}
                                <div className="space-y-2">
                                    <div className="text-green-400 font-bold text-sm">Objectives:</div>
                                    {questInfo.objectives.map((obj: any, objIndex: number) => (
                                        <div key={objIndex} className="flex items-start space-x-2">
                                            <span className={obj.is_completed ? 'text-green-500' : 'text-gray-500'}>
                                                {obj.is_completed ? '✓' : '○'}
                                            </span>
                                            <span className={obj.is_completed ? 'text-gray-400 line-through' : 'text-gray-300'}>
                                                {obj.description}
                                                {obj.progress_data && obj.progress_data.current !== undefined && (
                                                    <span className="text-amber-400 ml-2">
                                                        ({obj.progress_data.current}/{obj.progress_data.required})
                                                    </span>
                                                )}
                                            </span>
                                        </div>
                                    ))}
                                </div>

                                {/* Completion status */}
                                {questInfo.player_quest.status === 'completed' && (
                                    <div className="mt-4 text-green-400 font-bold">
                                        ✓ Completed
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
};
```

### 4. Badge Collection Modal

**New File**: `client/src/components/BadgeCollectionModal.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface BadgeCollectionModalProps {
    playerId: string;
    isOpen: boolean;
    onClose: () => void;
}

export const BadgeCollectionModal: React.FC<BadgeCollectionModalProps> = ({ playerId, isOpen, onClose }) => {
    const [badges, setBadges] = useState<any[]>([]);

    useEffect(() => {
        if (isOpen) {
            fetchBadges();
        }
    }, [isOpen, playerId]);

    const fetchBadges = async () => {
        try {
            const response = await api.get(`/player/${playerId}/badges`);
            setBadges(response.data.badges);
        } catch (error) {
            console.error('Error fetching badges:', error);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-900 border-2 border-purple-600 rounded-lg w-full max-w-4xl max-h-[80vh] overflow-hidden">
                {/* Header */}
                <div className="bg-gray-800 p-4 border-b border-purple-600 flex justify-between items-center">
                    <h2 className="text-2xl font-bold text-purple-400">Badge Collection</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white text-2xl"
                    >
                        ×
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto max-h-[70vh]">
                    {badges.length === 0 ? (
                        <div className="text-center text-gray-400 py-12">
                            No badges earned yet. Complete quests to earn badges!
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                            {badges.map((badgeInfo: any, index: number) => (
                                <div
                                    key={index}
                                    className="bg-gray-800 p-4 rounded-lg border-2 border-purple-500 hover:border-purple-400 transition-all text-center"
                                >
                                    {/* Badge image (placeholder for now) */}
                                    <div className="w-20 h-20 mx-auto mb-3 bg-gradient-to-br from-purple-600 to-purple-900 rounded-full flex items-center justify-center text-4xl">
                                        🏅
                                    </div>

                                    <h3 className="text-purple-300 font-bold mb-1">{badgeInfo.badge.name}</h3>
                                    <p className="text-gray-400 text-xs mb-2">{badgeInfo.badge.description}</p>
                                    <div className="text-gray-500 text-xs">
                                        Earned: {new Date(badgeInfo.earned_at).toLocaleDateString()}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
```

### 5. Add to Game Menu

In your main game interface component, add:

```typescript
import { QuestSummaryPanel } from '@/components/QuestSummaryPanel';
import { QuestLogModal } from '@/components/QuestLogModal';
import { BadgeCollectionModal } from '@/components/BadgeCollectionModal';

// State
const [showQuestLog, setShowQuestLog] = useState(false);
const [showBadges, setShowBadges] = useState(false);

// In left sidebar (below "Also Here")
<QuestSummaryPanel
    playerId={player.id}
    onQuestClick={() => setShowQuestLog(true)}
/>

// In menu buttons
<button onClick={() => setShowQuestLog(true)}>Quests</button>
<button onClick={() => setShowBadges(true)}>Badges</button>

// Modals
<QuestLogModal
    playerId={player.id}
    isOpen={showQuestLog}
    onClose={() => setShowQuestLog(false)}
/>
<BadgeCollectionModal
    playerId={player.id}
    isOpen={showBadges}
    onClose={() => setShowBadges(false)}
/>
```

---

## 🎯 TESTING STEPS

1. **Run Migrations** (REQUIRED FIRST):
   ```sql
   -- In Supabase SQL Editor:
   -- Run server/supabase_quest_migration.sql
   -- Run server/supabase_quest_seed.sql
   ```

2. **Create New Player**:
   - Tutorial quest should be assigned
   - Ancient Compass should spawn in nearby room

3. **Test Movement Tracking**:
   - Move 2 times
   - Check quest progress

4. **Test Look Command**:
   - Use "look" or "look around"
   - Should complete second objective

5. **Test Item Finding**:
   - Navigate to room with compass
   - Use "look" to find it
   - Take the compass

6. **Test Quest Completion**:
   - Should see completion message
   - Check gold balance (should be +50)
   - Check badges (should have "Seeker")

7. **Test UI**:
   - Quest summary panel shows progress
   - Quest log shows current quest
   - Badge collection shows earned badge

---

## 📊 Implementation Status: 70%

- **Backend**: 90% ✅
- **Integration**: 50% 🚧
- **Frontend**: 0% ⚠️

**Estimated Time to Complete**: 3-4 hours
- Integration: 1-2 hours
- Frontend: 2 hours
- Testing: 30 min
