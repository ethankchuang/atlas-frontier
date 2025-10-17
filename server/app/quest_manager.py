"""
Quest Manager - Handles quest progression, objective tracking, and rewards
"""
import logging
import uuid
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from .models import (
    Player, Quest, QuestObjective, PlayerQuest, PlayerQuestObjective,
    Badge, PlayerBadge, GoldTransaction
)
from .logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class QuestManager:
    def __init__(self, db):
        """Initialize with database connection"""
        self.db = db

    async def assign_tutorial_quest(self, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Assign the tutorial quest (first quest with order_index = 0) to a new player
        Returns quest data if successful, None otherwise
        """
        try:
            # Get the first quest (tutorial quest has order_index = 0)
            quest_data = await self._get_first_quest()
            if not quest_data:
                logger.warning(f"[Quest] No tutorial quest found (no quest with order_index = 0)")
                return None

            if not quest_data.get('is_active'):
                logger.warning(f"[Quest] Tutorial quest {quest_data['id']} is not active")
                return None

            tutorial_quest_id = quest_data['id']

            # Check if player already has this quest
            existing = await self._get_player_quest(player_id, tutorial_quest_id)
            if existing:
                logger.info(f"[Quest] Player {player_id} already has tutorial quest")
                return None

            # Create player quest record
            player_quest_id = f"pq_{str(uuid.uuid4())}"
            player_quest = {
                'id': player_quest_id,
                'player_id': player_id,
                'quest_id': tutorial_quest_id,
                'status': 'in_progress',
                'started_at': datetime.utcnow().isoformat(),
                'completed_at': None,
                'storyline_shown': False
            }

            await self._save_player_quest(player_quest)

            # Get quest objectives
            objectives = await self._get_quest_objectives(tutorial_quest_id)

            # Create player quest objective records
            for obj in objectives:
                pqo_id = f"pqo_{str(uuid.uuid4())}"
                player_quest_objective = {
                    'id': pqo_id,
                    'player_quest_id': player_quest_id,
                    'objective_id': obj['id'],
                    'is_completed': False,
                    'progress_data': self._init_progress_data(obj),
                    'completed_at': None
                }
                await self._save_player_quest_objective(player_quest_objective)

            # Update player's active quest
            player_data = await self.db.get_player(player_id)
            if player_data:
                player_data['active_quest_id'] = tutorial_quest_id
                await self.db.set_player(player_id, player_data)

            logger.info(f"[Quest] Assigned tutorial quest to player {player_id}")

            return {
                'quest': quest_data,
                'player_quest': player_quest,
                'objectives': objectives
            }

        except Exception as e:
            logger.error(f"[Quest] Error assigning tutorial quest: {str(e)}")
            return None

    async def check_objectives(
        self,
        player_id: str,
        action: str,
        action_type: str,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Check if player action completes any quest objectives

        Args:
            player_id: Player ID
            action: The action text
            action_type: Type of action (move, look, take_item, talk_npc, combat_win, etc.)
            context: Additional context (item_name, npc_id, biome, etc.)

        Returns:
            Quest completion data if quest completed, None otherwise
        """
        try:
            # Get player's active quest
            player_data = await self.db.get_player(player_id)
            if not player_data or not player_data.get('active_quest_id'):
                return None

            active_quest_id = player_data['active_quest_id']

            # Get player quest
            player_quest = await self._get_player_quest(player_id, active_quest_id)
            if not player_quest or player_quest['status'] != 'in_progress':
                return None

            # Get all objectives for this quest
            objectives = await self._get_quest_objectives(active_quest_id)
            player_objectives = await self._get_player_quest_objectives(player_quest['id'])

            # Track if any objective was updated
            updated = False

            # Check each objective
            for obj in objectives:
                # Find corresponding player objective
                player_obj = next((po for po in player_objectives if po['objective_id'] == obj['id']), None)
                if not player_obj or player_obj['is_completed']:
                    continue

                # Check if this action completes the objective
                completed, progress_data = await self._check_objective(
                    obj, player_obj, action_type, context
                )

                if completed or progress_data != player_obj.get('progress_data'):
                    # Update player objective
                    player_obj['progress_data'] = progress_data
                    if completed:
                        player_obj['is_completed'] = True
                        player_obj['completed_at'] = datetime.utcnow().isoformat()
                        logger.info(f"[Quest] Objective completed: {obj['description']}")

                    await self._save_player_quest_objective(player_obj)
                    updated = True

            if not updated:
                return None

            # Check if all objectives are completed
            all_completed = all(
                po['is_completed'] for po in await self._get_player_quest_objectives(player_quest['id'])
            )

            if all_completed:
                # Quest completed!
                return await self._complete_quest(player_id, active_quest_id, player_quest)

            # Return progress update
            return {
                'type': 'quest_progress',
                'quest_id': active_quest_id,
                'objectives': await self._get_player_quest_objectives(player_quest['id'])
            }

        except Exception as e:
            logger.error(f"[Quest] Error checking objectives: {str(e)}")
            return None

    async def get_storyline_chunks(self, quest_id: str, chunk_size: int = 80) -> List[str]:
        """
        Get quest storyline split into chunks for typewriter effect
        """
        try:
            quest_data = await self._get_quest(quest_id)
            if not quest_data:
                return []

            storyline = quest_data.get('storyline', '')

            # Split by lines first to preserve formatting
            lines = storyline.split('\n')
            chunks = []
            current_chunk = ""

            for line in lines:
                if len(current_chunk) + len(line) + 1 > chunk_size and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    if current_chunk:
                        current_chunk += '\n' + line
                    else:
                        current_chunk = line

            if current_chunk:
                chunks.append(current_chunk)

            return chunks

        except Exception as e:
            logger.error(f"[Quest] Error getting storyline chunks: {str(e)}")
            return []

    async def get_player_quest_status(self, player_id: str) -> Optional[Dict[str, Any]]:
        """Get current quest status for a player"""
        try:
            player_data = await self.db.get_player(player_id)
            if not player_data or not player_data.get('active_quest_id'):
                return None

            quest_id = player_data['active_quest_id']
            quest_data = await self._get_quest(quest_id)
            player_quest = await self._get_player_quest(player_id, quest_id)

            if not quest_data or not player_quest:
                return None

            # Get objectives with progress
            objectives = await self._get_quest_objectives(quest_id)
            player_objectives = await self._get_player_quest_objectives(player_quest['id'])

            # Combine objective data with player progress
            objectives_with_progress = []
            completed_count = 0
            for obj in objectives:
                player_obj = next((po for po in player_objectives if po['objective_id'] == obj['id']), None)
                is_completed = player_obj['is_completed'] if player_obj else False
                if is_completed:
                    completed_count += 1
                objectives_with_progress.append({
                    'id': obj['id'],
                    'description': obj['description'],
                    'is_completed': is_completed,
                    'player_progress': player_obj if player_obj else None
                })

            return {
                'quest': quest_data,
                'player_quest': player_quest,
                'objectives': objectives_with_progress,
                'progress': {
                    'completed': completed_count,
                    'total': len(objectives)
                }
            }

        except Exception as e:
            logger.error(f"[Quest] Error getting quest status: {str(e)}")
            return None

    async def get_player_quest_log(self, player_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get all quests for a player (current and completed)"""
        try:
            all_player_quests = await self._get_all_player_quests(player_id)

            current_quests = []
            completed_quests = []

            for pq in all_player_quests:
                quest_data = await self._get_quest(pq['quest_id'])
                if not quest_data:
                    continue

                objectives = await self._get_quest_objectives(pq['quest_id'])
                player_objectives = await self._get_player_quest_objectives(pq['id'])

                objectives_with_progress = []
                completed_count = 0
                for obj in objectives:
                    player_obj = next((po for po in player_objectives if po['objective_id'] == obj['id']), None)
                    is_completed = player_obj['is_completed'] if player_obj else False
                    if is_completed:
                        completed_count += 1
                    objectives_with_progress.append({
                        'id': obj['id'],
                        'description': obj['description'],
                        'is_completed': is_completed,
                        'player_progress': player_obj if player_obj else None
                    })

                quest_info = {
                    'quest': quest_data,
                    'player_quest': pq,
                    'objectives': objectives_with_progress,
                    'progress': {
                        'completed': completed_count,
                        'total': len(objectives)
                    }
                }

                if pq['status'] in ['completed', 'claimed']:
                    completed_quests.append(quest_info)
                else:
                    current_quests.append(quest_info)

            return {
                'current_quests': current_quests,
                'completed_quests': completed_quests
            }

        except Exception as e:
            logger.error(f"[Quest] Error getting quest log: {str(e)}")
            return {'current_quests': [], 'completed_quests': []}

    async def get_player_badges(self, player_id: str) -> List[Dict[str, Any]]:
        """Get all badges earned by a player"""
        try:
            player_badges = await self._get_player_badges(player_id)
            badges = []

            for pb in player_badges:
                badge_data = await self._get_badge(pb['badge_id'])
                if badge_data:
                    badges.append({
                        'badge': badge_data,
                        'earned_at': pb['earned_at']
                    })

            return badges

        except Exception as e:
            logger.error(f"[Quest] Error getting player badges: {str(e)}")
            return []

    # Private helper methods

    def _init_progress_data(self, objective: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Initialize progress data for an objective"""
        obj_type = objective['objective_type']
        obj_data = objective['objective_data']

        if obj_type in ['move_n_times', 'talk_to_npc', 'visit_biomes', 'win_combat']:
            required = obj_data.get('required_count', 1)
            return {'current': 0, 'required': required}

        return None

    async def _check_objective(
        self,
        objective: Dict[str, Any],
        player_objective: Dict[str, Any],
        action_type: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if an action completes or progresses an objective
        Returns (is_completed, updated_progress_data)
        """
        obj_type = objective['objective_type']
        obj_data = objective['objective_data']
        progress = player_objective.get('progress_data', {})

        # Move N times
        if obj_type == 'move_n_times' and action_type == 'move':
            current = progress.get('current', 0)
            required = progress.get('required', obj_data.get('required_count', 1))
            current += 1
            progress = {'current': current, 'required': required}
            return (current >= required, progress)

        # Use specific command
        elif obj_type == 'use_command' and action_type == 'command':
            required_cmd = obj_data.get('command', '').lower()
            action_cmd = context.get('command', '').lower()
            logger.info(f"[Quest] Checking use_command - required: '{required_cmd}', action: '{action_cmd}', obj_data: {obj_data}")
            if required_cmd in action_cmd or action_cmd in required_cmd:
                logger.info(f"[Quest] Command matched! Completing objective")
                return (True, progress)
            else:
                logger.info(f"[Quest] Command did not match")

        # Find item (item spawned in room)
        elif obj_type == 'find_item' and action_type == 'room_has_item':
            required_item = obj_data.get('item_name', '').lower()
            found_item = context.get('item_name', '').lower()
            if required_item in found_item or found_item in required_item:
                return (True, progress)

        # Take item
        elif obj_type == 'take_item' and action_type == 'take_item':
            required_item = obj_data.get('item_name', '').lower()
            taken_item = context.get('item_name', '').lower()
            if required_item in taken_item or taken_item in required_item:
                return (True, progress)

        # Talk to NPC
        elif obj_type == 'talk_to_npc' and action_type == 'talk_npc':
            current = progress.get('current', 0)
            required = progress.get('required', obj_data.get('required_count', 1))
            current += 1
            progress = {'current': current, 'required': required}
            return (current >= required, progress)

        # Visit biomes
        elif obj_type == 'visit_biomes' and action_type == 'visit_biome':
            current = progress.get('current', 0)
            required = progress.get('required', obj_data.get('required_count', 1))
            visited_biomes = progress.get('biomes', [])
            new_biome = context.get('biome', '')

            if new_biome and new_biome not in visited_biomes:
                visited_biomes.append(new_biome)
                current = len(visited_biomes)
                progress = {'current': current, 'required': required, 'biomes': visited_biomes}
                return (current >= required, progress)

        # Win combat (monster or duel)
        elif obj_type == 'win_combat' and action_type in ['defeat_monster', 'win_duel']:
            current = progress.get('current', 0)
            required = progress.get('required', obj_data.get('required_count', 1))
            current += 1
            progress = {'current': current, 'required': required}
            return (current >= required, progress)

        return (False, progress)

    async def _complete_quest(
        self,
        player_id: str,
        quest_id: str,
        player_quest: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Complete a quest and award rewards"""
        try:
            # Update quest status
            player_quest['status'] = 'completed'
            player_quest['completed_at'] = datetime.utcnow().isoformat()
            await self._save_player_quest(player_quest)

            # Get quest data for rewards
            quest_data = await self._get_quest(quest_id)
            if not quest_data:
                return {'type': 'quest_completed', 'quest_id': quest_id}

            # Award gold
            gold_reward = quest_data.get('gold_reward', 0)
            if gold_reward > 0:
                await self._award_gold(player_id, gold_reward, 'quest_reward', quest_id, f"Completed quest: {quest_data['name']}")

            # Award badge
            badge_id = quest_data.get('badge_id')
            if badge_id:
                await self._award_badge(player_id, badge_id)

            # Get next quest in sequence
            next_quest = await self._get_next_quest(quest_data['order_index'])

            # Update player's active quest
            player_data = await self.db.get_player(player_id)
            if player_data:
                player_data['active_quest_id'] = next_quest['id'] if next_quest else None
                await self.db.set_player(player_id, player_data)

            # Assign next quest if available
            if next_quest:
                await self.assign_quest(player_id, next_quest['id'])

            logger.info(f"[Quest] Player {player_id} completed quest {quest_id}")

            return {
                'type': 'quest_completed',
                'quest': quest_data,
                'gold_reward': gold_reward,
                'badge_id': badge_id,
                'next_quest': next_quest
            }

        except Exception as e:
            logger.error(f"[Quest] Error completing quest: {str(e)}")
            return {'type': 'quest_completed', 'quest_id': quest_id}

    async def assign_quest(self, player_id: str, quest_id: str) -> bool:
        """Assign a specific quest to a player"""
        try:
            # Check if quest exists
            quest_data = await self._get_quest(quest_id)
            if not quest_data or not quest_data.get('is_active'):
                return False

            # Check if player already has quest
            existing = await self._get_player_quest(player_id, quest_id)
            if existing:
                return False

            # Create player quest
            player_quest_id = f"pq_{str(uuid.uuid4())}"
            player_quest = {
                'id': player_quest_id,
                'player_id': player_id,
                'quest_id': quest_id,
                'status': 'in_progress',
                'started_at': datetime.utcnow().isoformat(),
                'completed_at': None,
                'storyline_shown': False
            }
            await self._save_player_quest(player_quest)

            # Create objective records
            objectives = await self._get_quest_objectives(quest_id)
            for obj in objectives:
                pqo_id = f"pqo_{str(uuid.uuid4())}"
                player_quest_objective = {
                    'id': pqo_id,
                    'player_quest_id': player_quest_id,
                    'objective_id': obj['id'],
                    'is_completed': False,
                    'progress_data': self._init_progress_data(obj),
                    'completed_at': None
                }
                await self._save_player_quest_objective(player_quest_objective)

            logger.info(f"[Quest] Assigned quest {quest_id} to player {player_id}")
            return True

        except Exception as e:
            logger.error(f"[Quest] Error assigning quest: {str(e)}")
            return False

    async def _award_gold(
        self,
        player_id: str,
        amount: int,
        transaction_type: str,
        reference_id: Optional[str],
        description: Optional[str]
    ):
        """Award gold to a player and record transaction"""
        try:
            player_data = await self.db.get_player(player_id)
            if not player_data:
                return

            current_gold = player_data.get('gold', 0)
            new_gold = current_gold + amount
            player_data['gold'] = new_gold

            await self.db.set_player(player_id, player_data)

            # Record transaction
            transaction = {
                'id': f"gt_{str(uuid.uuid4())}",
                'player_id': player_id,
                'amount': amount,
                'transaction_type': transaction_type,
                'reference_id': reference_id,
                'description': description,
                'balance_after': new_gold,
                'created_at': datetime.utcnow().isoformat()
            }
            await self._save_gold_transaction(transaction)

            logger.info(f"[Quest] Awarded {amount} gold to player {player_id}")

        except Exception as e:
            logger.error(f"[Quest] Error awarding gold: {str(e)}")

    async def _award_badge(self, player_id: str, badge_id: str):
        """Award a badge to a player"""
        try:
            # Check if player already has badge
            player_badges = await self._get_player_badges(player_id)
            if any(pb['badge_id'] == badge_id for pb in player_badges):
                return

            player_badge = {
                'id': f"pb_{str(uuid.uuid4())}",
                'player_id': player_id,
                'badge_id': badge_id,
                'earned_at': datetime.utcnow().isoformat()
            }
            await self._save_player_badge(player_badge)

            logger.info(f"[Quest] Awarded badge {badge_id} to player {player_id}")

        except Exception as e:
            logger.error(f"[Quest] Error awarding badge: {str(e)}")

    # Database access methods (using Supabase)

    async def _get_quest(self, quest_id: str) -> Optional[Dict[str, Any]]:
        """Get quest by ID from database"""
        from .supabase_database import SupabaseDatabase
        return await SupabaseDatabase.get_quest(quest_id)

    async def _get_quest_objectives(self, quest_id: str) -> List[Dict[str, Any]]:
        """Get all objectives for a quest"""
        from .supabase_database import SupabaseDatabase
        return await SupabaseDatabase.get_quest_objectives(quest_id)

    async def _get_player_quest(self, player_id: str, quest_id: str) -> Optional[Dict[str, Any]]:
        """Get player quest record"""
        from .supabase_database import SupabaseDatabase
        return await SupabaseDatabase.get_player_quest(player_id, quest_id)

    async def _get_all_player_quests(self, player_id: str) -> List[Dict[str, Any]]:
        """Get all quests for a player"""
        from .supabase_database import SupabaseDatabase
        return await SupabaseDatabase.get_all_player_quests(player_id)

    async def _get_player_quest_objectives(self, player_quest_id: str) -> List[Dict[str, Any]]:
        """Get all player objective records for a quest"""
        from .supabase_database import SupabaseDatabase
        return await SupabaseDatabase.get_player_quest_objectives(player_quest_id)

    async def _get_badge(self, badge_id: str) -> Optional[Dict[str, Any]]:
        """Get badge by ID"""
        from .supabase_database import SupabaseDatabase
        return await SupabaseDatabase.get_badge(badge_id)

    async def _get_player_badges(self, player_id: str) -> List[Dict[str, Any]]:
        """Get all badges for a player"""
        from .supabase_database import SupabaseDatabase
        return await SupabaseDatabase.get_player_badges(player_id)

    async def _get_first_quest(self) -> Optional[Dict[str, Any]]:
        """Get the first quest (tutorial quest with order_index = 0)"""
        from .supabase_database import SupabaseDatabase
        return await SupabaseDatabase.get_first_quest()

    async def _get_next_quest(self, current_order_index: int) -> Optional[Dict[str, Any]]:
        """Get the next quest in sequence"""
        from .supabase_database import SupabaseDatabase
        return await SupabaseDatabase.get_next_quest(current_order_index)

    async def _save_player_quest(self, player_quest: Dict[str, Any]):
        """Save or update player quest"""
        from .supabase_database import SupabaseDatabase
        await SupabaseDatabase.save_player_quest(player_quest)

    async def _save_player_quest_objective(self, objective: Dict[str, Any]):
        """Save or update player quest objective"""
        from .supabase_database import SupabaseDatabase
        await SupabaseDatabase.save_player_quest_objective(objective)

    async def _save_player_badge(self, player_badge: Dict[str, Any]):
        """Save player badge"""
        from .supabase_database import SupabaseDatabase
        await SupabaseDatabase.save_player_badge(player_badge)

    async def _save_gold_transaction(self, transaction: Dict[str, Any]):
        """Save gold transaction"""
        from .supabase_database import SupabaseDatabase
        await SupabaseDatabase.save_gold_transaction(transaction)
