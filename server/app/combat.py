from typing import Dict, List, Optional, Any
import json
import asyncio
from datetime import datetime

from .game_manager import GameManager

# Expose duel and monster combat shared state
duel_moves: Dict[str, Dict[str, str]] = {}
duel_pending: Dict[str, Dict[str, Any]] = {}


async def collect_special_effects_from_inventories(player1_inventory: List[str], player2_inventory: List[str], game_manager: GameManager) -> List[str]:
    """Collect all special effects from both players' inventories for AI context"""
    from .main import logger
    
    special_effects_list = []
    
    # Collect from both players' inventories
    all_inventories = [
        ("Player 1", player1_inventory),
        ("Player 2", player2_inventory)
    ]
    
    try:
        for player_name, inventory in all_inventories:
            for item_id in inventory:
                try:
                    item_data = await game_manager.db.get_item(item_id)
                    if not item_data:
                        continue
                    
                    item_name = item_data.get('name', 'Unknown Item')
                    special_effects = item_data.get('special_effects', '')
                    
                    # Add all special effects to the list (no filtering)
                    if special_effects:
                        effect_entry = f"{player_name} has {item_name}: {special_effects}"
                        special_effects_list.append(effect_entry)
                        logger.info(f"[Special Effects] {effect_entry}")
                        
                except Exception as e:
                    logger.warning(f"[Special Effects] Error processing item {item_id}: {str(e)}")
                    continue
                    
    except Exception as e:
        logger.error(f"[Special Effects] Error collecting special effects: {str(e)}")
    
    return special_effects_list


async def analyze_combat_and_create_narrative(
    player1_name: str, player1_move: str, _player1_condition: str,
    player2_name: str, player2_move: str, _player2_condition: str,
    player1_invalid_move: Optional[Dict[str, Any]], player2_invalid_move: Optional[Dict[str, Any]],
    player1_inventory: List[str], player2_inventory: List[str], room_name: str, room_description: str, 
    current_round: int, duel_info: Dict[str, Any], player1_max_vital: int, player2_max_vital: int,
    game_manager: GameManager, recent_rounds: Optional[List[Dict[str, Any]]] = None,
    special_effects: Optional[List[str]] = None
) -> Dict[str, Any]:
    from .main import logger
    
    recent_summary: List[Dict[str, Any]] = []
    history_lines: List[str] = []
    
    try:
        if recent_rounds:
            for r in recent_rounds[-5:]:
                # For analysis
                recent_summary.append({
                    'round': r.get('round'),
                    'p1_move': r.get('player1_move'),
                    'p2_move': r.get('player2_move'),
                    'p1_damage_dealt': r.get('player1_damage_dealt', 0),
                    'p2_damage_dealt': r.get('player2_damage_dealt', 0),
                    'p1_control_delta': r.get('player1_control_delta'),
                    'p2_control_delta': r.get('player2_control_delta'),
                    'p1_health': r.get('player1_health'),
                    'p2_health': r.get('player2_health'),
                    'p1_control': r.get('player1_control'),
                    'p2_control': r.get('player2_control')
                })
                # For narrative context
                rnum = r.get('round')
                p1m = r.get('player1_move') or r.get('player_move')
                p2m = r.get('player2_move') or r.get('monster_move')
                narrative = r.get('narrative', '')
                if narrative:
                    history_lines.append(f"R{rnum}: {narrative}")
    except Exception:
        recent_summary = []
        history_lines = []
    
    history_block = "\n".join(history_lines) if history_lines else "None"

    # Format special effects for AI context
    special_effects_text = "None"
    if special_effects:
        special_effects_text = "\n".join([f"- {effect}" for effect in special_effects])

    prompt = f"""
You are the AI Gamemaster for a combat turn. Analyze how the combat progresses based on the moves of each combatant.
IMPORTANT:
- make sure to validate the moves of each combatant based on the equipment they have and the special effects they have.
- make sure players feel the impact of their moves and feel like the outcome is logical
- keep combat fast paced and not last a long time.
- The primary outcome should be change in health, control is a secondary outcome
- It is okay to have both players end with a positive outcome, it doesn't have to be one or the other.
- Keep responses concise and to the point, 2 sentences max.

LOCATION: {room_name} - {room_description}

RECENT COMBAT HISTORY:
{history_block}

SPECIAL EFFECTS AVAILABLE:
{special_effects_text}

CURRENT ROUND ACTIONS:
- {player1_name} attempts: "{player1_move}"
  - Inventory: {player1_inventory}
  - Invalid Move Info: {player1_invalid_move if player1_invalid_move else 'None'}

- {player2_name} attempts: "{player2_move}"
  - Inventory: {player2_inventory}
  - Invalid Move Info: {player2_invalid_move if player2_invalid_move else 'None'}

CURRENT COMBAT STATE:
- {player1_name} Current Health: {duel_info.get('player1_health', player1_max_vital)}/{player1_max_vital}
- {player1_name} Current Control: {duel_info.get('player1_control', 0)}/5
- {player2_name} Current Health: {duel_info.get('player2_health', player2_max_vital)}/{player2_max_vital}
- {player2_name} Current Control: {duel_info.get('player2_control', 0)}/5
- Finishing Window Owner: {duel_info.get('finishing_window_owner', 'None')}

RECENT STATS CONTEXT (for reference):
{json.dumps(recent_summary)}

COMBAT SYSTEM RULES:
You are the gamemaster of this combat encounter. You have COMPLETE CONTROL over all combat outcomes, balancing, and special mechanics.

1. EQUIPMENT VALIDATION & SPECIAL EFFECTS:
   - Check the equipment of the players to determine whether or not they are physically able to do the move they inputted.
   - The player is a naked human plus whatever equipment they have. Their valid moves should reflect this.
   - Determine if the player is physically capable of performing the move they input based on the equipment that they own.
   - For example, the player should only be able to do slicing moves if they have something capable of slicing like a sword
   - If the player is not physically capable of performing the move they input THE MOVE SHOULD HAVE NO EFFECT
   - For example, if the player tries to shoot a gun but don't have one, the move should be INVALID AND HAVE NO EFFECT
   - If the move is invalid, explain why in the output narrative
   - If the player has equipment that allows them to perform the move they input then LET IT PASS
   - Not every move requires equipment, for example punch, kick, tackle. Moves using just the players body are always valid. 
   - Don't force yourself to mark one move invalid, it's okay to have both moves valid.

2. TARGETING & ACTIONS:
   - {player1_name}'s attacks target {player2_name}
   - {player2_name}'s attacks target {player1_name}
   - Only describe what each player actually attempted - don't invent actions
   - Defensive moves (dodge, block, parry) only work if explicitly chosen

3. DAMAGE & CONTROL MECHANICS (YOU CONTROL ALL BALANCING):
   - Health represents hit points - when it reaches 0, you're defeated
   - Control represents combat advantage - at 5 Control, you enter "finishing window"
   - Damage Dealt: 0 to 3 (0 = no damage; 1 = light; 2 = moderate; 3 = heavy damage)
   - Control Delta: -2 to 2 (momentum shifts; positive = gaining advantage)
   - YOU decide all values based on what makes sense based on the interaction, edge on the side of doing more damage.
   - Be aggressive, players should feel the impact of the moves and combat should feel relatively fast paced and not last a long time.
   - Make sure there is proper reasoning for the damage and control changes, players should understand why they are what they are.
   - IMPORTANT: Always assign meaningful damage and control values. Don't leave them at 0 unless the move truly has no impact.

4. SPECIAL MECHANICS (YOU CONTROL THESE):
   - Finishing Window: When someone reaches 5 Control, they can attempt finishing moves
   - If someone in finishing window deals ANY damage, it's an instant kill (set target health to 0)
   - Monster Max Health: {player2_max_vital} (varies by monster size)
   - Combat ends when someone's health reaches 0
   - Provide a cool and badass finishing move for the player who wins the duel.

5. BALANCING PHILOSOPHY:
   - Make outcomes feel fair and reasonable, players should feel the impact of their moves
   - Do not make the players feel like they were cheated out of their move.
   - Consider move interactions, timing, and combat flow
   - Players should feel their choices matter
   - Combat should be relatively swift, don't let it drag on.

OUTPUT FORMAT:
Return JSON with:
{{
    "narrative": "An engaging 2-4 sentence description of what happened this round",
    "player1_result": {{
        "reason": "What happened to {player1_name} specifically"
    }},
    "player2_result": {{
        "reason": "What happened to {player2_name} specifically"
    }},
    "player1_damage_dealt": 0,
    "player2_damage_dealt": 0,
    "player1_control_delta": 0,
    "player2_control_delta": 0,
    "player1_intends_heal": false,
    "player2_intends_heal": false,
    "finishing_window_owner": null,
    "instant_kill_occurred": false,
    "combat_ends": false
}}

SPECIAL MECHANICS TO HANDLE:
- Set "finishing_window_owner" to "player1" or "player2" if they reach 5 Control (or null if neither)
- Set "instant_kill_occurred" to true if someone in finishing window deals damage
- Set "combat_ends" to true if someone's health reaches 0
- Handle all balancing decisions yourself - no external game engine will modify your results

Make it dramatic, make it make sense, and make it fun!
"""

    try:
        response = await game_manager.ai_handler.generate_text(prompt)
        result = json.loads(response)
        
        # Debug logging for AI response
        logger.info(f"[analyze_combat_and_create_narrative] AI raw response: {response}")
        
        # Ensure we have all required fields with proper defaults
        combat_result = {
            'narrative': result.get('narrative', f"Round {current_round}: {player1_name} and {player2_name} engaged in combat."),
            'player1_result': result.get('player1_result', {
                'reason': f'{player1_name} continues fighting'
            }),
            'player2_result': result.get('player2_result', {
                'reason': f'{player2_name} continues fighting'
            }),
            'player1_damage_dealt': int(result.get('player1_damage_dealt', 0) or 0),
            'player2_damage_dealt': int(result.get('player2_damage_dealt', 0) or 0),
            'player1_control_delta': int(result.get('player1_control_delta', 0) or 0),
            'player2_control_delta': int(result.get('player2_control_delta', 0) or 0),
            'player1_intends_heal': bool(result.get('player1_intends_heal', False)),
            'player2_intends_heal': bool(result.get('player2_intends_heal', False)),
            'finishing_window_owner': result.get('finishing_window_owner'),
            'instant_kill_occurred': bool(result.get('instant_kill_occurred', False)),
            'combat_ends': bool(result.get('combat_ends', False)),
        }
        
        # Clean up narrative formatting
        narrative = combat_result['narrative'].strip()
        if narrative.startswith('"') and narrative.endswith('"'):
            narrative = narrative[1:-1]
        combat_result['narrative'] = narrative
        
        logger.info(f"[analyze_combat_and_create_narrative] Generated narrative: {narrative}")
        return combat_result
        
    except Exception as e:
        logger.error(f"[analyze_combat_and_create_narrative] Error with AI analysis: {str(e)}")
        raise


async def get_monster_max_vital(monster_data: dict) -> int:
    size = (monster_data or {}).get('size', 'human')
    size_multipliers = {
        'insect': 0.25,
        'chicken': 0.5,
        'human': 1.0,
        'horse': 1.5,
        'dinosaur': 2.0,
        'colossal': 3.0,
    }
    mult = size_multipliers.get(size, 1.0)
    return max(1, int(round(6 * mult)))


# The remaining high-level handlers are kept in main.py to avoid websocket routing changes.
# They will import and use these helpers (analyze_combat_outcome, generate_combat_narrative,
# get_monster_max_vital) and share duel state via this module's dictionaries.


async def generate_and_submit_monster_move(duel_id: str, monster_id: str, player_data: dict, monster_data: dict, room_id: str, round_number: int, game_manager: GameManager):
    from .main import manager, logger
    try:
        # Get room data and recent combat history
        room_data = await game_manager.db.get_room(room_id)
        try:
            recent_rounds = (duel_pending.get(duel_id, {}) or {}).get('history', [])[-5:]
        except Exception:
            recent_rounds = []
        
        # Generate monster move inline
        monster_move = None
        try:
            monster_history_lines: List[str] = []
            try:
                for r in recent_rounds[-5:]:
                    m = r.get('player2_move') or r.get('monster_move') or ''
                    if m:
                        monster_history_lines.append(f"R{r.get('round')}: {m}")
            except Exception:
                monster_history_lines = []
            history_block = "\n".join(monster_history_lines) if monster_history_lines else "None"
            
            monster_name = monster_data.get('name', 'Unknown Monster')
            monster_size = monster_data.get('size', 'human')
            monster_aggressiveness = monster_data.get('aggressiveness', 'neutral')
            monster_intelligence = monster_data.get('intelligence', 'animal')
            monster_description = monster_data.get('description', '')
            monster_special_effects = monster_data.get('special_effects', '')
            monster_health = monster_data.get('health', 100)
            player_name = player_data.get('name', 'Unknown Player')
            room_title = room_data.get('title', 'Unknown Room')
            room_biome = room_data.get('biome', 'unknown')
            
            prompt = f"""You are controlling a monster in combat. Generate ONE specific combat move for this creature.
 
 RECENT MONSTER MOVES (avoid repeating, vary tactics):
 {history_block}
 
 MONSTER DETAILS:
 - Name: {monster_name}
 - Size: {monster_size}
 - Aggressiveness: {monster_aggressiveness}
 - Intelligence: {monster_intelligence}
 - Description: {monster_description}
 - Special Effects: {monster_special_effects}
 - Current Health: {monster_health}
 
 COMBAT CONTEXT:
 - Round: {round_number}
 - Fighting: {player_name}
 - Location: {room_title} ({room_biome})
 
 MOVE GENERATION RULES:
 1. Generate ONE specific combat action (2-5 words)
 2. Match the monster's aggressiveness level
 3. Match the monster's intelligence
 4. Use size appropriately
 5. Incorporate special effects when relevant
 6. Use basic combat actions (no equipment needed)
 7. CRITICAL: Avoid repeating recent moves shown above. Use completely different verbs and tactics.
 8. Be creative and procedural - create something unique for this round
 
 Return ONLY the combat move as a simple string, no JSON formatting, no quotes, no extra text."""
            
            ai_response = await game_manager.ai_handler.generate_text(prompt)
            monster_move = ai_response.strip()
            
            # Clean up the response - remove quotes if present
            if monster_move.startswith('"') and monster_move.endswith('"'):
                monster_move = monster_move[1:-1]
            if monster_move.startswith("'") and monster_move.endswith("'"):
                monster_move = monster_move[1:-1]
                
            # Ensure reasonable length
            if len(monster_move) > 100:
                monster_move = monster_move[:100]
                
            # Basic validation - if empty or too generic, add some variation
            if not monster_move or monster_move.lower() in ['attack', 'attacks', 'move', 'action']:
                aggressiveness = monster_data.get('aggressiveness', 'neutral')
                fallback_moves = {
                    'aggressive': 'lunges forward aggressively',
                    'territorial': 'strikes defensively', 
                    'passive': 'moves cautiously away',
                    'neutral': 'attacks with claws'
                }
                monster_move = fallback_moves.get(aggressiveness, 'attacks with claws')
            
            logger.info(f"[generate_and_submit_monster_move] Generated move for {monster_name}: '{monster_move}'")
            
        except Exception as e:
            logger.error(f"Error generating monster combat move: {str(e)}")
            aggressiveness = monster_data.get('aggressiveness', 'neutral')
            fallback_moves = {
                'aggressive': 'lunges forward aggressively',
                'territorial': 'strikes defensively',
                'passive': 'moves cautiously away',
                'neutral': 'attacks with claws'
            }
            monster_move = fallback_moves.get(aggressiveness, 'attacks')
        
        # Submit the generated move
        if duel_id not in duel_moves:
            duel_moves[duel_id] = {}
        duel_moves[duel_id][monster_id] = monster_move
        logger.info(f"[generate_and_submit_monster_move] Monster {monster_data.get('name')} submitted move: '{monster_move}'")
        
        # Broadcast move message to room
        duel_move_message = {
            "type": "duel_move",
            "player_id": monster_id,
            "move": "preparing combat action...",
            "room_id": room_id,
            "timestamp": datetime.now().isoformat(),
            "is_monster_move": True,
            "monster_name": monster_data.get('name', 'Unknown Monster')
        }
        await manager.broadcast_to_room(room_id, duel_move_message)
        
        # Check if both moves are ready and trigger combat resolution
        if duel_id in duel_pending:
            pending_duel = duel_pending[duel_id]
            player_ids = {pending_duel["player1_id"], pending_duel["player2_id"]}
            if player_ids.issubset(set(duel_moves[duel_id].keys())):
                logger.info(f"[generate_and_submit_monster_move] Both moves ready, processing duel round for {duel_id}")
                await analyze_duel_moves(duel_id, game_manager)
                
    except Exception as e:
        logger.error(f"Error generating and submitting monster move: {str(e)}")


async def prepare_next_monster_duel_round(duel_id: str, game_manager: GameManager):
    from .main import manager, logger
    try:
        if duel_id not in duel_pending:
            return
        duel_info = duel_pending[duel_id]
        if not duel_info.get('is_monster_duel'):
            return
        room_id = duel_info['room_id']
        next_round = duel_info['round'] + 1
        duel_info['round'] = next_round
        next_round_message = {
            "type": "duel_next_round",
            "round": next_round,
            "room_id": room_id,
            "timestamp": datetime.now().isoformat()
        }
        await manager.broadcast_to_room(room_id, next_round_message)
        logger.info(f"[prepare_next_monster_duel_round] Prepared round {next_round} for monster duel {duel_id}")
    except Exception as e:
        logger.error(f"Error preparing next monster duel round: {str(e)}")






async def send_duel_results(
    duel_id: str, room_id: str, player1_id: str, player2_id: str, current_round: int,
    player1_move: str, player2_move: str,
    _player1_condition: str, _player2_condition: str,
    _player1_tags: List[Dict[str, Any]], _player2_tags: List[Dict[str, Any]],
    _player1_total_severity: int, _player2_total_severity: int,
    narrative: str, combat_ends: bool, game_manager: GameManager,
    player1_health: int, player2_health: int, player1_control: int, player2_control: int,
    player1_max_health: int = 6, player2_max_health: int = 6
):
    from .main import manager, logger
    player1_data = await game_manager.db.get_player(player1_id)
    player2_data = await game_manager.db.get_player(player2_id)
    player1_name = player1_data.get('name', 'Unknown') if player1_data else 'Unknown'
    player2_name = player2_data.get('name', 'Unknown') if player2_data else 'Unknown'
    round_message = {
        "type": "duel_round_result",
        "round": current_round,
        "player1_id": player1_id,
        "player2_id": player2_id,
        "player1_move": player1_move,
        "player2_move": player2_move,
        "player1_health": player1_health,
        "player2_health": player2_health,
        "player1_control": player1_control,
        "player2_control": player2_control,
        "player1_max_health": player1_max_health,
        "player2_max_health": player2_max_health,
        "description": narrative,
        "combat_ends": combat_ends,
        "room_id": room_id,
        "timestamp": datetime.now().isoformat()
    }
    await manager.send_to_player(room_id, player1_id, round_message)
    await manager.send_to_player(room_id, player2_id, round_message)
    if combat_ends:
        winner_id = None
        loser_id = None
        p1_broken = player1_health <= 0
        p2_broken = player2_health <= 0
        if p1_broken and not p2_broken:
            winner_id = player2_id
            loser_id = player1_id
        elif p2_broken and not p1_broken:
            winner_id = player1_id
            loser_id = player2_id
        if winner_id:
            try:
                winner_name = player1_name if winner_id == player1_id else player2_name
                loser_name = player2_name if winner_id == player1_id else player1_name
                victory_prompt = f"""
                Create a dramatic victory message for this combat ending.

                Combat Summary:
                - Winner: {winner_name} (ID: {winner_id})
                - Loser: {loser_name} (ID: {loser_id})
                - Final Round: {current_round + 1}

                Instructions:
                - Create an engaging, dramatic victory message
                - Consider the nature of the defeat (body overwhelmed or finishing window converted)
                - Make it feel like a real combat conclusion
                - Keep it concise but impactful

                Return only the victory message text, no JSON formatting.
                """
                victory_message = await game_manager.ai_handler.generate_text(victory_prompt)
                victory_message = victory_message.strip().strip('"')
            except Exception as e:
                logger.error(f"Error generating victory message with AI: {e}")
                victory_message = f"{winner_name} has defeated {loser_name}!"
            outcome_message = {
                "type": "duel_outcome",
                "winner_id": winner_id,
                "loser_id": loser_id,
                "analysis": victory_message,
                "room_id": room_id,
                "timestamp": datetime.now().isoformat(),
                "duel_id": duel_id
            }
            await manager.send_to_player(room_id, player1_id, outcome_message)
            await manager.send_to_player(room_id, player2_id, outcome_message)
            
            # Record combat history to prevent re-aggression
            try:
                from .monster_behavior import monster_behavior_manager
                # If a monster won, record that it has fought the player AND teleport player to spawn
                if winner_id and isinstance(winner_id, str) and winner_id.startswith("monster_"):
                    defeated_player_id = player1_id if winner_id == player2_id else player2_id
                    monster_behavior_manager._record_monster_combat(defeated_player_id, winner_id)
                    logger.info(f"[Combat] Recorded monster victory: {winner_id} defeated {defeated_player_id}")

                    # Teleport defeated player to spawn (0,0)
                    try:
                        defeated_player_data = await game_manager.db.get_player(defeated_player_id)
                        if defeated_player_data:
                            old_room_id = defeated_player_data.get('current_room')
                            spawn_room_id = 'room_start'  # Spawn location (starting room)

                            # Update player's room
                            defeated_player_data['current_room'] = spawn_room_id
                            await game_manager.db.set_player(defeated_player_id, defeated_player_data)
                            
                            # Update room player lists
                            await game_manager.db.remove_from_room_players(old_room_id, defeated_player_id)
                            await game_manager.db.add_to_room_players(spawn_room_id, defeated_player_id)
                            
                            logger.info(f"[Combat] Teleported defeated player {defeated_player_id} from {old_room_id} to spawn {spawn_room_id}")

                            # Get spawn room data
                            spawn_room_data = await game_manager.db.get_room(spawn_room_id)
                            if spawn_room_data:
                                from .models import Room
                                spawn_room = Room(**spawn_room_data)
                                spawn_room.players = await game_manager.db.get_room_players(spawn_room_id)
                                spawn_room_dict = spawn_room.dict()
                                for key, value in spawn_room_dict.items():
                                    if isinstance(value, bytes):
                                        spawn_room_dict[key] = value.decode('utf-8')

                                # Send defeat message and teleport to player
                                await manager.send_to_player(old_room_id, defeated_player_id, {
                                    "type": "player_death",
                                    "message": "💀 You have been defeated! You wake up back at spawn...",
                                    "new_room": spawn_room_dict,
                                    "timestamp": datetime.now().isoformat()
                                })

                                # Broadcast to old room that player left
                                await manager.broadcast_to_room(old_room_id, {
                                    "type": "presence",
                                    "player_id": defeated_player_id,
                                    "status": "left"
                                }, exclude_player=defeated_player_id)

                                # Broadcast to spawn room that player arrived
                                await manager.broadcast_to_room(spawn_room_id, {
                                    "type": "presence",
                                    "player_id": defeated_player_id,
                                    "status": "joined"
                                }, exclude_player=defeated_player_id)
                    except Exception as e:
                        logger.error(f"[Combat] Error teleporting defeated player to spawn: {str(e)}")
            except Exception as e:
                logger.error(f"[Combat] Error recording monster combat history: {str(e)}")
            
            # FUTURE: Replace immediate removal with corpse/loot persistence and respawn timers.
            # Temporary behavior: if a monster loses a duel, remove it from the room for now
            try:
                if loser_id and isinstance(loser_id, str) and loser_id.startswith("monster_"):
                    room_data = await game_manager.db.get_room(room_id)
                    if room_data:
                        monsters_list = list(room_data.get('monsters', []) or [])
                        if loser_id in monsters_list:
                            monsters_list = [m for m in monsters_list if m != loser_id]
                            room_data['monsters'] = monsters_list
                            # Persist updated room
                            await game_manager.db.set_room(room_id, room_data)

                            # Let players know this is a temporary behavior
                            await manager.broadcast_to_room(room_id, {
                                "type": "system_message",
                                "message": f"{loser_name} collapses and disappears for now. Temporary behavior: defeated monsters are removed. A future update will add corpses/loot and proper cleanup.",
                                "timestamp": datetime.now().isoformat()
                            })

                            # Broadcast updated room state so clients refresh monster list
                            try:
                                from .models import Room
                                room = Room(**room_data)
                                room.players = await game_manager.db.get_room_players(room_id)
                                room_dict = room.dict()
                                for key, value in room_dict.items():
                                    if isinstance(value, bytes):
                                        room_dict[key] = value.decode('utf-8')
                                await manager.broadcast_to_room(room_id, {
                                    "type": "room_update",
                                    "room": room_dict
                                })
                            except Exception as e:
                                logger.error(f"[Duel] Failed to broadcast updated room after monster defeat: {str(e)}")
            except Exception as e:
                logger.error(f"[Duel] Error during temporary monster removal: {str(e)}")

            # Clean up duel state so players can act normally again
            try:
                if duel_id in duel_moves:
                    del duel_moves[duel_id]
                if duel_id in duel_pending:
                    del duel_pending[duel_id]
            except Exception as e:
                logger.error(f"[Duel] Error cleaning up duel state for {duel_id}: {str(e)}")
        else:
            # No clear winner; treat as draw and clean up
            try:
                outcome_message = {
                    "type": "duel_outcome",
                    "winner_id": None,
                    "loser_id": None,
                    "analysis": f"{player1_name} and {player2_name} ended their combat.",
                    "room_id": room_id,
                    "timestamp": datetime.now().isoformat(),
                    "duel_id": duel_id
                }
                await manager.send_to_player(room_id, player1_id, outcome_message)
                await manager.send_to_player(room_id, player2_id, outcome_message)
            except Exception as e:
                logger.error(f"[Duel] Error sending draw outcome for {duel_id}: {str(e)}")
            finally:
                try:
                    if duel_id in duel_moves:
                        del duel_moves[duel_id]
                    if duel_id in duel_pending:
                        del duel_pending[duel_id]
                except Exception as e:
                    logger.error(f"[Duel] Error cleaning up duel state (draw) for {duel_id}: {str(e)}")
    else:
        # Continue
        pass


async def analyze_duel_moves(duel_id: str, game_manager: GameManager):
    from .main import logger
    try:
        logger.info(f"[analyze_duel_moves] Starting analysis for duel {duel_id}")
        duel_info = duel_pending.get(duel_id)
        if not duel_info:
            raise ValueError(f"Duel info not found for {duel_id}")
        duel_history = duel_info.setdefault('history', [])
        player1_id = duel_info['player1_id']
        player2_id = duel_info['player2_id']
        room_id = duel_info['room_id']
        current_round = duel_info['round']
        prev_p1_control = duel_info.get('player1_control', 0)
        prev_p2_control = duel_info.get('player2_control', 0)
        prev_finishing_owner = duel_info.get('finishing_window_owner')
        moves = duel_moves.get(duel_id, {})
        player1_move = moves.get(player1_id, 'do nothing')
        player2_move = moves.get(player2_id, 'do nothing')
        player1_data = await game_manager.db.get_player(player1_id)
        player1_name = player1_data.get('name', 'Unknown') if player1_data else "Unknown"
        player1_inventory = player1_data.get('inventory', []) if player1_data else []
        is_monster_duel = duel_info.get('is_monster_duel', False)
        if is_monster_duel:
            monster_data = duel_info.get('monster_data', {})
            player2_name = monster_data.get('name', 'Unknown Monster')
            player2_inventory = []
            player2_data = None
        else:
            player2_data = await game_manager.db.get_player(player2_id)
            player2_name = player2_data.get('name', 'Unknown') if player2_data else "Unknown"
            player2_inventory = player2_data.get('inventory', []) if player2_data else []
        room_data = await game_manager.db.get_room(room_id)
        room_name = room_data.get('title', 'Unknown Room') if room_data else "Unknown Room"
        room_description = room_data.get('description', 'An unknown location') if room_data else "An unknown location"
        player1_condition_prev = 'healthy'
        player2_condition_prev = 'healthy'
        player1_invalid = None  # Equipment validation handled by AI
        player2_invalid = None  # Equipment validation handled by AI
        player1_max_vital = 6
        player2_max_vital = 6
        if is_monster_duel:
            player2_max_vital = await get_monster_max_vital(monster_data)
        
        # Collect special effects from both players' inventories
        logger.info(f"[analyze_duel_moves] Collecting special effects for combat...")
        special_effects_list = await collect_special_effects_from_inventories(player1_inventory, player2_inventory, game_manager)
        logger.info(f"[analyze_duel_moves] Found {len(special_effects_list)} special effects")
        
        logger.info(f"[analyze_duel_moves] Analyzing combat outcome and generating narrative...")
        combat_outcome = await analyze_combat_and_create_narrative(
            player1_name, player1_move, player1_condition_prev,
            player2_name, player2_move, player2_condition_prev,
            player1_invalid, player2_invalid, player1_inventory, player2_inventory,
            room_name, room_description, current_round, duel_info, player1_max_vital, player2_max_vital,
            game_manager, recent_rounds=duel_history[-5:], special_effects=special_effects_list
        )
        # Extract AI decisions - no game engine modifications
        narrative = combat_outcome['narrative']
        p1_damage_dealt = int(combat_outcome.get('player1_damage_dealt', 0) or 0)  # Damage P1 dealt to P2
        p2_damage_dealt = int(combat_outcome.get('player2_damage_dealt', 0) or 0)  # Damage P2 dealt to P1
        p1_control_delta = int(combat_outcome.get('player1_control_delta', 0) or 0)
        p2_control_delta = int(combat_outcome.get('player2_control_delta', 0) or 0)
        
        # Debug logging for damage and control
        logger.info(f"[analyze_duel_moves] AI returned - P1 dealt {p1_damage_dealt} damage, P2 dealt {p2_damage_dealt} damage, P1 control: {p1_control_delta}, P2 control: {p2_control_delta}")
        
        # Apply damage and control changes
        # Health starts at max, decreases with damage. Control starts at 0, increases with advantage.
        p1_health = max(0, duel_info.get('player1_health', player1_max_vital) - p2_damage_dealt)  # P1 takes damage from P2
        p2_health = max(0, duel_info.get('player2_health', player2_max_vital) - p1_damage_dealt)  # P2 takes damage from P1
        p1_control = max(0, min(5, duel_info.get('player1_control', 0) + p1_control_delta))
        p2_control = max(0, min(5, duel_info.get('player2_control', 0) + p2_control_delta))
        
        # Update persistent state
        duel_info['player1_health'] = p1_health
        duel_info['player2_health'] = p2_health
        duel_info['player1_control'] = p1_control
        duel_info['player2_control'] = p2_control
        
        # Apply AI-determined special mechanics
        if combat_outcome.get('finishing_window_owner'):
            duel_info['finishing_window_owner'] = combat_outcome['finishing_window_owner']
        elif combat_outcome.get('finishing_window_owner') is None:
            duel_info['finishing_window_owner'] = None
            
        # Handle instant kills if AI determined one occurred
        if combat_outcome.get('instant_kill_occurred'):
            if combat_outcome.get('finishing_window_owner') == 'player1':
                p2_health = 0  # Set to 0 health (instant kill)
                duel_info['player2_health'] = p2_health
            elif combat_outcome.get('finishing_window_owner') == 'player2':
                p1_health = 0  # Set to 0 health (instant kill)
                duel_info['player1_health'] = p1_health
            duel_info['finishing_window_owner'] = None
        
        # Use AI's combat end determination, but override if health reaches 0 or control reaches 5
        combat_ends = combat_outcome.get('combat_ends', False)
        if p1_health <= 0 or p2_health <= 0:
            combat_ends = True
            logger.info(f"[analyze_duel_moves] Combat ends due to health: P1={p1_health}, P2={p2_health}")
        elif p1_control >= 5 or p2_control >= 5:
            # When control reaches 5, the combatant with 5 control should automatically win
            if p1_control >= 5 and p2_control < 5:
                # Player 1 has finishing window - they win
                p2_health = 0
                duel_info['player2_health'] = p2_health
                combat_ends = True
                logger.info(f"[analyze_duel_moves] Combat ends due to P1 finishing window: P1 control={p1_control}, P2 health set to 0")
            elif p2_control >= 5 and p1_control < 5:
                # Player 2 has finishing window - they win
                p1_health = 0
                duel_info['player1_health'] = p1_health
                combat_ends = True
                logger.info(f"[analyze_duel_moves] Combat ends due to P2 finishing window: P2 control={p2_control}, P1 health set to 0")
            else:
                # Both have 5 control - let AI determine the outcome
                logger.info(f"[analyze_duel_moves] Both players have 5 control, letting AI determine outcome")
        else:
            logger.info(f"[analyze_duel_moves] Combat continues: P1={p1_health}, P2={p2_health}, P1 control={p1_control}, P2 control={p2_control} (AI determined: {combat_ends})")
        try:
            duel_history.append({
                'round': current_round,
                'player1_move': player1_move,
                'player2_move': player2_move,
                'narrative': narrative,
                'player1_result': combat_outcome.get('player1_result', {}),
                'player2_result': combat_outcome.get('player2_result', {}),
                'player1_damage_dealt': p1_damage_dealt,
                'player2_damage_dealt': p2_damage_dealt,
                'player1_control_delta': p1_control_delta,
                'player2_control_delta': p2_control_delta,
                'player1_health': p1_health,
                'player2_health': p2_health,
                'player1_control': p1_control,
                'player2_control': p2_control
            })
            if len(duel_history) > 10:
                del duel_history[:-10]
        except Exception as e:
            logger.error(f"[analyze_duel_moves] Error updating duel history: {str(e)}")
        await send_duel_results(
            duel_id, room_id, player1_id, player2_id, current_round,
            player1_move, player2_move,
            '', '',
            [], [],
            0, 0,
            narrative, combat_ends, game_manager,
            p1_health, p2_health, p1_control, p2_control,
            player1_max_vital, player2_max_vital  # Use actual max health values
        )
    except Exception as e:
        logger.error(f"[analyze_duel_moves] Error: {str(e)}")


async def handle_duel_move(message: dict, room_id: str, player_id: str, game_manager: GameManager):
    from .main import logger
    duel_id = message.get("duel_id")
    if not duel_id:
        opponent_id = message.get("opponent_id")
        if opponent_id:
            for potential_duel_id, duel_info in duel_pending.items():
                if ((duel_info["player1_id"] == player_id and duel_info["player2_id"] == opponent_id) or
                    (duel_info["player1_id"] == opponent_id and duel_info["player2_id"] == player_id)):
                    duel_id = potential_duel_id
                    logger.info(f"[handle_duel_move] Found duel_id {duel_id} for player {player_id} vs {opponent_id}")
                    break
    if not duel_id:
        logger.error(f"[handle_duel_move] Could not find duel_id for player {player_id}")
        return
    move = message["move"]
    if duel_id not in duel_moves:
        duel_moves[duel_id] = {}
    try:
        duel_pending.get(duel_id, {}).setdefault('history', [])
    except Exception:
        pass
    duel_moves[duel_id][player_id] = move
    if duel_id in duel_pending:
        pending_duel = duel_pending[duel_id]
        player_ids = {pending_duel["player1_id"], pending_duel["player2_id"]}
        if pending_duel.get('is_monster_duel') and player_id == pending_duel["player1_id"]:
            monster_id = pending_duel["player2_id"]
            player_data = await game_manager.db.get_player(player_id)
            monster_data = pending_duel.get('monster_data', {})
            room_id = pending_duel["room_id"]
            current_round = pending_duel["round"]
            await generate_and_submit_monster_move(duel_id, monster_id, player_data, monster_data, room_id, current_round, game_manager)
        elif player_ids.issubset(set(duel_moves[duel_id].keys())):
            # Both players have submitted moves, analyze them
            logger.info(f"[handle_duel_move] Both players submitted moves for duel {duel_id}, analyzing...")
            await analyze_duel_moves(duel_id, game_manager)
            # Clear the moves after processing to prevent duplicate processing
            duel_moves[duel_id].clear()
            logger.info(f"[handle_duel_move] Cleared moves for duel {duel_id} after processing")


