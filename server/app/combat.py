from typing import Dict, List, Optional, Any
import json
import asyncio
from datetime import datetime

from .game_manager import GameManager

# Expose duel and monster combat shared state
duel_moves: Dict[str, Dict[str, str]] = {}
duel_pending: Dict[str, Dict[str, Any]] = {}

monster_combat_pending: Dict[str, Dict[str, Any]] = {}
monster_combat_moves: Dict[str, Dict[str, str]] = {}

async def analyze_combat_outcome(player1_name: str, player1_move: str, _player1_condition: str, player1_equipment_valid: bool,
                                player2_name: str, player2_move: str, _player2_condition: str, player2_equipment_valid: bool,
                                player1_invalid_move: Optional[Dict[str, Any]], player2_invalid_move: Optional[Dict[str, Any]],
                                player1_inventory: List[str], player2_inventory: List[str], room_name: str, room_description: str, game_manager: GameManager,
                                recent_rounds: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    from .main import logger  # avoid circular logger import
    recent_summary: List[Dict[str, Any]] = []
    try:
        if recent_rounds:
            for r in recent_rounds[-5:]:
                recent_summary.append({
                    'round': r.get('round'),
                    'p1_move': r.get('player1_move'),
                    'p2_move': r.get('player2_move'),
                    'p1_vital_delta': r.get('player1_vital_delta'),
                    'p2_vital_delta': r.get('player2_vital_delta'),
                    'p1_control_delta': r.get('player1_control_delta'),
                    'p2_control_delta': r.get('player2_control_delta'),
                    'p1_vital': r.get('player1_vital'),
                    'p2_vital': r.get('player2_vital'),
                    'p1_control': r.get('player1_control'),
                    'p2_control': r.get('player2_control')
                })
    except Exception:
        recent_summary = []

    prompt = f"""
COMBAT OUTCOME ANALYSIS:

Location: {room_name} - {room_description}

{player1_name} vs {player2_name} in combat:

{player1_name} action toward {player2_name}:
- Move: "{player1_move}"
- Equipment Valid: {player1_equipment_valid}
- Inventory: {player1_inventory}
- Invalid Move Info: {player1_invalid_move if player1_invalid_move else 'None'}

{player2_name} action toward {player1_name}:
- Move: "{player2_move}"
- Equipment Valid: {player2_equipment_valid}
- Inventory: {player2_inventory}
- Invalid Move Info: {player2_invalid_move if player2_invalid_move else 'None'}

Recent Rounds (most recent last, if any):
{json.dumps(recent_summary)}

CRITICAL RULES:
1. VALIDATION RULES:
   - If player1_equipment_valid = True, {player1_name}'s move is VALID and can have full effect
   - If player2_equipment_valid = True, {player2_name}'s move is VALID and can have full effect
   - Basic combat actions (punch, kick, tackle, dodge, block, etc.) are ALWAYS VALID
   - Equipment-based actions (slash with sword, shoot with bow, etc.) require the specific equipment
   - Invalid moves (missing equipment) have NO EFFECT and cannot harm anyone
   - Valid moves can cause damage and affect the target

2. DO NOT INVENT ACTIONS:
   - ONLY use the exact moves provided above for each side
   - If a player's move is defensive (defend, block, parry, dodge, retreat), treat it as DEFENSIVE. Do not describe them attacking
   - Attacks must come from explicit attack-like moves (punch, stab, shoot, slash, strike, etc.)

3. TARGETING:
   - {player1_name}'s attack-like moves target {player2_name}
   - {player2_name}'s attack-like moves target {player1_name}
   - Successful attacks harm the TARGET, not the attacker
   - VALID ATTACKS should have impact unless countered by defensive actions
   - Monster attacks are ALWAYS VALID and should have some effect

4. DEFENSE:
   - Defensive moves (block, dodge, parry) can reduce or prevent damage only when the player actually chose them
   - Invalid moves (missing equipment) cause NO DAMAGE and have NO EFFECT

5. EXPLAIN MISSED/FAILED ATTACKS:
   - If an attack fails or misses, explain WHY (invalid equipment, target blocked, target dodged, poor footing, etc.)

6. VARIETY WITHIN REASON:
   - Make outcomes varied and exciting yet reasonable and consistent with the stated moves.
   - Avoid monotonous 1-point trades. If the last rounds were minor or symmetric, consider a justified shift (clean hit, counter, positioning) to vary Vital/Control deltas.
   - Escalate to higher Vital deltas (2-3) ONLY when a clear, clean hit or advantage is present; use 0 when fully negated by defense.
   - Control deltas should reflect momentum: gains for clean hits/positioning, losses for overcommitting/being countered.
   - Maintain logical consistency: outcomes must make sense given each player's chosen move this round.

7. CLOCK DELTAS (YOU MUST DECIDE EACH ROUND):
   - Output explicit deltas for both Vital (damage/strain) and Control (advantage) for each side, even if small.
   - Vital delta range: -1..3 (negative only for clear healing/recovery; 0 if no effect; higher = harsher harm to the target).
   - Control delta range: -2..2 (advantage shifts up/down; gains for clean hits/positioning, losses for overcommitting/being countered).
   - If a move is INVALID due to equipment, it should cause NO harmful effect (0 Vital to the opponent) and typically reduce the actor's Control by 0..1.
   - When both sides hit, both targets can take Vital increases; adjust Control based on who came out ahead.
   - Bars should generally move every round; use small deltas (e.g., ±1) when outcomes are marginal. Use variety across rounds when justified.

8. MOVE VALIDATION:
   - Determine if you think the player should be able to do the move they are attempting.
   - Determine using their inventory and the world context.
   - If the move requires an items the player doesn't have, it should be INVALID.
   - If a move is invalid, it should have no effect.
   - In the output, describe why the move is invalid.

8. HEALING INTENT (NO KEYWORD MATCHING):
   - Determine if a player is intending to heal or recover based on the described action intent, not keywords.
   - Only set a negative Vital delta for that player when you judge they are attempting a healing/recovery action.
   - Provide boolean flags player1_intends_heal and player2_intends_heal accordingly.

Return JSON:
{{
    "player1_result": {{
        "reason": "description of what happened to {player1_name}"
    }},
    "player2_result": {{
        "reason": "description of what happened to {player2_name}"
    }},
    "player1_vital_delta": -1,
    "player2_vital_delta": -1,
    "player1_control_delta": -2,
    "player2_control_delta": -2,
    "player1_intends_heal": false,
    "player2_intends_heal": false
}}
"""

    try:
        response = await game_manager.ai_handler.generate_text(prompt)
        result = json.loads(response)
        return {
            'player1_result': result.get('player1_result', {
                'reason': f'{player1_name} continues fighting'
            }),
            'player2_result': result.get('player2_result', {
                'reason': f'{player2_name} continues fighting'
            }),
            'player1_vital_delta': int(result.get('player1_vital_delta', 0) or 0),
            'player2_vital_delta': int(result.get('player2_vital_delta', 0) or 0),
            'player1_control_delta': int(result.get('player1_control_delta', 0) or 0),
            'player2_control_delta': int(result.get('player2_control_delta', 0) or 0),
            'player1_intends_heal': bool(result.get('player1_intends_heal', False)),
            'player2_intends_heal': bool(result.get('player2_intends_heal', False)),
        }
    except Exception as e:
        logger.error(f"[analyze_combat_outcome] Error analyzing combat outcome with AI: {str(e)}")
        p1_vital_delta_fb = 0
        p2_vital_delta_fb = 0
        p1_control_delta_fb = 0
        p2_control_delta_fb = 0
        if player1_equipment_valid:
            p2_vital_delta_fb = 1
            p1_control_delta_fb += 1
        else:
            p1_control_delta_fb -= 1
        if player2_equipment_valid:
            p1_vital_delta_fb = 1
            p2_control_delta_fb += 1
        else:
            p2_control_delta_fb -= 1
        return {
            'player1_result': {
                'reason': f"{player1_name} {'attempted invalid move' if not player1_equipment_valid else 'acted effectively'}"
            },
            'player2_result': {
                'reason': f"{player2_name} {'attempted invalid move' if not player2_equipment_valid else 'acted effectively'}"
            },
            'player1_vital_delta': p1_vital_delta_fb,
            'player2_vital_delta': p2_vital_delta_fb,
            'player1_control_delta': p1_control_delta_fb,
            'player2_control_delta': p2_control_delta_fb,
        }


async def generate_combat_narrative(
    player1_name: str, player1_move: str, player1_result: Dict[str, Any],
    player2_name: str, player2_move: str, player2_result: Dict[str, Any],
    player1_invalid_move: Optional[Dict[str, Any]], player2_invalid_move: Optional[Dict[str, Any]],
    current_round: int, room_name: str, room_description: str, game_manager: GameManager,
    recent_rounds: Optional[List[Dict[str, Any]]] = None
) -> str:
    from .main import logger
    recent_rounds = recent_rounds or []
    history_lines: List[str] = []
    try:
        for r in recent_rounds[-10:]:
            rnum = r.get('round')
            p1m = r.get('player1_move') or r.get('player_move')
            p2m = r.get('player2_move') or r.get('monster_move')
            p1res = (r.get('player1_result') or r.get('player_result') or {}).get('reason', '')
            p2res = (r.get('player2_result') or r.get('monster_result') or {}).get('reason', '')
            history_lines.append(f"R{rnum}: {player1_name} -> '{p1m}' ({p1res}); {player2_name} -> '{p2m}' ({p2res})")
    except Exception:
        history_lines = []
    history_block = "\n".join(history_lines) if history_lines else "None"

    prompt = f"""
        Create an engaging, descriptive narrative for this combat round.
 
        Location: {room_name} - {room_description}
 
        Recent Rounds (most recent first, up to 10):
        {history_block}
 
        Combat Context:
        - {player1_name} acts with: {player1_move}
        - {player2_name} acts with: {player2_move}
         
         {player1_name} Results:
         - Outcome: {player1_result.get('reason', 'Unknown')}
         
         {player2_name} Results:
         - Outcome: {player2_result.get('reason', 'Unknown')}
         
         Invalid Move Context:
         - {player1_name} Invalid: {player1_invalid_move if player1_invalid_move else 'None'}
         - {player2_name} Invalid: {player2_invalid_move if player2_invalid_move else 'None'}
 
         Instructions:
         - Create a vivid, engaging narrative that describes what happened
         - If there are invalid moves (missing equipment), EXPLAIN WHY they failed (e.g., "tried to shoot without a gun")
         - If moves are valid (including basic actions like punch/kick), describe them accordingly
         - Describe the actual outcomes and their impact on both players
         - Make it feel like a real combat scene, not just a game log
         - Keep it concise but descriptive (2-4 sentences)
         - Use active voice and dynamic language
         - Use actual player names: {player1_name} and {player2_name}
         - Basic actions like punch, kick, tackle are valid and can cause damage when chosen
         - Only equipment-based actions without the required equipment are invalid
         - ALWAYS explain why attacks miss or fail - be specific about the reason
          
         CRITICAL RULES:
         1. DO NOT directly reference tags, severity levels, or game mechanics
            - Don't say "with a severity level of 3" or "gets a negative tag"
            - Instead, describe the actual injury/advantage naturally
            - Example: "leaving him bruised and shaken" not "gets bruised ribs tag"
           
         2. MOVE IMPACT RULES:
            - Do NOT invent actions. ONLY describe what each side actually attempted.
            - If a player's move is defensive (e.g., defend, block, parry, dodge, retreat), DO NOT describe them attacking. Focus on mitigation, positioning, or advantage shifts.
            - VALID ATTACKS MUST CAUSE DAMAGE unless the target is explicitly defending in their own move
            - If a valid attack lands, describe the damage and its effect; if it fails, explain why
            - If an attack misses, EXPLAIN WHY (missing equipment, target blocked, target dodged, etc.)
            - Invalid moves (missing equipment) have NO EFFECT and should be explained as such
         
         3. DODGING/BLOCKING RULES:
             - Players can ONLY dodge/block if their move explicitly includes dodging/blocking
             - If a player's move is "punch", they cannot dodge - they are punching
             - If a player's move is "dodge" or "block", then they can avoid attacks
             - If a player's move is "kick", they cannot dodge - they are kicking
             - Only describe dodging/blocking when it's part of the player's actual move
 
         3. ENVIRONMENT AWARENESS:
             - The combat is taking place in: 
         """

    try:
        narrative = await game_manager.ai_handler.generate_text(prompt)
        narrative = narrative.strip()
        if narrative.startswith('"') and narrative.endswith('"'):
            narrative = narrative[1:-1]
        logger.info(f"[generate_combat_narrative] AI generated narrative: {narrative}")
        return narrative
    except Exception as e:
        logger.error(f"[generate_combat_narrative] Error generating combat narrative with AI: {str(e)}")
        return f"Round {current_round}: {player1_name} and {player2_name} engaged in combat in {room_name}."


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


async def generate_monster_combat_move(monster_data: Dict[str, Any], player_data: Dict[str, Any], room_data: Dict[str, Any], round_number: int, game_manager: GameManager, recent_rounds: Optional[List[Dict[str, Any]]] = None) -> str:
    from .main import logger
    try:
        recent_rounds = recent_rounds or []
        monster_history_lines: List[str] = []
        try:
            for r in recent_rounds[-5:]:
                m = r.get('player2_move') or r.get('monster_move') or ''
                if m:
                    monster_history_lines.append(f"R{r.get('round')}: {m}")
        except Exception:
            monster_history_lines = []
        history_block = "\n".join(monster_history_lines) if monster_history_lines else "None"
        recent_moves = [
            (r.get('player2_move') or r.get('monster_move') or '').strip().lower()
            for r in recent_rounds[-5:]
            if (r.get('player2_move') or r.get('monster_move'))
        ]
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
        prompt = f"""You are controlling a monster in combat. Generate FIVE distinct candidate combat moves for this creature.
 
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
 1. Generate FIVE specific combat actions (2-5 words each)
 2. Match the monster's aggressiveness level
 3. Match the monster's intelligence
 4. Use size appropriately
 5. Incorporate special effects when relevant
 6. Use basic combat actions (no equipment needed)
 7. Avoid repeating recent moves; vary verbs and approach.
 
 Return STRICT JSON array of 5 strings, no prose, e.g.: ["option 1", "option 2", "option 3", "option 4", "option 5"]"""
        ai_response = await game_manager.ai_handler.generate_text(prompt)
        text = ai_response.strip()
        options: List[str] = []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                options = [str(x).strip() for x in parsed if isinstance(x, (str, int, float))]
        except Exception:
            try:
                start = text.find('[')
                end = text.rfind(']')
                if start != -1 and end != -1 and end > start:
                    parsed = json.loads(text[start:end+1])
                    if isinstance(parsed, list):
                        options = [str(x).strip() for x in parsed if isinstance(x, (str, int, float))]
            except Exception:
                options = []
        if not options:
            options = [line.strip('- ').strip() for line in text.splitlines() if line.strip()][:5]
        try:
            from difflib import SequenceMatcher
            def max_similarity(candidate: str) -> float:
                cand = (candidate or '').strip().lower()
                if not recent_moves:
                    return 0.0
                return max(SequenceMatcher(None, cand, prev).ratio() for prev in recent_moves)
            ranked = sorted(options, key=lambda o: (round(max_similarity(o), 4), len(o)))
            chosen = ranked[0] if ranked else (options[0] if options else "attacks")
        except Exception:
            chosen = options[0] if options else "attacks"
        if len(chosen) > 100:
            chosen = chosen[:100]
        logger.info(f"[generate_monster_combat_move] Generated move for {monster_name} (chosen): '{chosen}' from options: {options}")
        return chosen
    except Exception as e:
        logger.error(f"Error generating monster combat move: {str(e)}")
        aggressiveness = monster_data.get('aggressiveness', 'neutral')
        fallback_moves = {
            'aggressive': 'lunges forward aggressively',
            'territorial': 'strikes defensively',
            'passive': 'moves cautiously away',
            'neutral': 'attacks with claws'
        }
        return fallback_moves.get(aggressiveness, 'attacks')


async def auto_submit_monster_move(duel_id: str, monster_id: str, player_data: dict, monster_data: dict, room_id: str, round_number: int, game_manager: GameManager):
    from .main import manager, logger
    try:
        room_data = await game_manager.db.get_room(room_id)
        try:
            recent_rounds = (duel_pending.get(duel_id, {}) or {}).get('history', [])[-5:]
        except Exception:
            recent_rounds = []
        monster_move = await generate_monster_combat_move(monster_data, player_data, room_data, round_number, game_manager, recent_rounds=recent_rounds)
        if duel_id not in duel_moves:
            duel_moves[duel_id] = {}
        duel_moves[duel_id][monster_id] = monster_move
        logger.info(f"[auto_submit_monster_move] Monster {monster_data.get('name')} submitted move: '{monster_move}'")
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
        if duel_id in duel_pending:
            pending_duel = duel_pending[duel_id]
            player_ids = {pending_duel["player1_id"], pending_duel["player2_id"]}
            if player_ids.issubset(set(duel_moves[duel_id].keys())):
                logger.info(f"[auto_submit_monster_move] Both moves ready, processing duel round for {duel_id}")
                await analyze_duel_moves(duel_id, game_manager)
    except Exception as e:
        logger.error(f"Error auto-submitting monster move: {str(e)}")


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


async def send_monster_combat_results(room_id: str, player_id: str, monster_id: str, round_number: int,
                                    player_move: str, monster_move: str,
                                    narrative: str, combat_ends: bool, game_manager: GameManager,
                                    player_condition: str = '', monster_condition: str = '',
                                    _player_total_severity: int = 0, _monster_total_severity: int = 0):
    from .main import manager, logger
    try:
        monster_data = await game_manager.db.get_monster(monster_id)
        monster_name = monster_data.get('name', 'Unknown Monster') if monster_data else "Unknown Monster"
        combat_message = {
            "type": "monster_combat_outcome",
            "round": round_number,
            "monster_name": monster_name,
            "player_move": player_move,
            "monster_move": monster_move,
            "narrative": narrative,
            "combat_ends": combat_ends,
            "monster_defeated": False,
            "player_vital": 0,
            "monster_vital": 0,
            "player_control": 0,
            "monster_control": 0,
        }
        await manager.broadcast_to_room(room_id, combat_message)
        logger.info(f"[send_monster_combat_results] Sent combat results to room {room_id}")
    except Exception as e:
        logger.error(f"Error sending monster combat results: {str(e)}")


async def analyze_monster_combat(combat_id: str, game_manager: GameManager):
    from .main import logger
    try:
        logger.info(f"[analyze_monster_combat] Starting analysis for combat {combat_id}")
        combat_info = monster_combat_pending[combat_id]
        combat_history = combat_info.setdefault('history', [])
        player_id = combat_info['player_id']
        monster_id = combat_info['monster_id']
        room_id = combat_info['room_id']
        current_round = combat_info['round']
        moves = monster_combat_moves[combat_id]
        player_move = moves.get(player_id, 'do nothing')
        monster_move = moves.get(monster_id, 'do nothing')
        logger.info(f"[analyze_monster_combat] Round {current_round}: {player_id} vs {monster_id}")
        logger.info(f"[analyze_monster_combat] Moves: '{player_move}' vs '{monster_move}'")
        player_data = await game_manager.db.get_player(player_id)
        monster_data = await game_manager.db.get_monster(monster_id)
        player_name = player_data.get('name', 'Unknown') if player_data else "Unknown"
        monster_name = monster_data.get('name', 'Unknown Monster') if monster_data else "Unknown Monster"
        player_inventory = player_data.get('inventory', []) if player_data else []
        room_data = await game_manager.db.get_room(room_id)
        room_name = room_data.get('title', 'Unknown Room') if room_data else "Unknown Room"
        room_description = room_data.get('description', 'An unknown location') if room_data else "An unknown location"
        player_condition = 'healthy'
        monster_condition = 'healthy'
        equipment_result = {
            'player1_valid': True,
            'player2_valid': True,
            'player1_reason': 'Validation disabled; decided in prompt',
            'player2_reason': 'Validation disabled; decided in prompt'
        }
        player_invalid = None if equipment_result['player1_valid'] else {
            'move': player_move,
            'reason': equipment_result['player1_reason']
        }
        monster_invalid = None
        logger.info(f"[analyze_monster_combat] Equipment validation complete:")
        logger.info(f"[analyze_monster_combat] {player_name}: {'VALID' if equipment_result['player1_valid'] else 'INVALID'} - {equipment_result['player1_reason']}")
        logger.info(f"[analyze_monster_combat] {monster_name}: VALID (monster attacks)")
        logger.info(f"[analyze_monster_combat] Analyzing combat outcome...")
        combat_outcome = await analyze_combat_outcome(
            player_name, player_move, player_condition, equipment_result['player1_valid'],
            monster_name, monster_move, monster_condition, True,
            player_invalid, monster_invalid, player_inventory, [],
            room_name, room_description, game_manager
        )
        logger.info(f"[analyze_monster_combat] Combat outcome received (vital/control only)")
        logger.info(f"[analyze_monster_combat] Generating combat narrative...")
        narrative = await generate_combat_narrative(
            player_name, player_move, combat_outcome['player1_result'],
            monster_name, monster_move, combat_outcome['player2_result'],
            player_invalid, monster_invalid, current_round,
            room_name, room_description, game_manager,
            recent_rounds=combat_history[-10:]
        )
        logger.info(f"[analyze_monster_combat] Narrative generated: {narrative[:100]}...")
        try:
            combat_history.append({
                'round': current_round,
                'player_move': player_move,
                'monster_move': monster_move,
                'narrative': narrative,
                'player_result': combat_outcome.get('player1_result', {}),
                'monster_result': combat_outcome.get('player2_result', {})
            })
            if len(combat_history) > 10:
                del combat_history[:-10]
        except Exception as e:
            logger.error(f"[analyze_monster_combat] Error updating combat history: {str(e)}")
        combat_ends = False
        await send_monster_combat_results(
            room_id, player_id, monster_id, current_round,
            player_move, monster_move,
            narrative=narrative, combat_ends=combat_ends, game_manager=game_manager,
            player_condition='', monster_condition='', _player_total_severity=0, _monster_total_severity=0
        )
        if not combat_ends:
            combat_info['round'] = current_round + 1
    except Exception as e:
        logger.error(f"Error analyzing monster combat: {str(e)}")


async def send_duel_results(
    duel_id: str, room_id: str, player1_id: str, player2_id: str, current_round: int,
    player1_move: str, player2_move: str,
    _player1_condition: str, _player2_condition: str,
    _player1_tags: List[Dict[str, Any]], _player2_tags: List[Dict[str, Any]],
    _player1_total_severity: int, _player2_total_severity: int,
    narrative: str, combat_ends: bool, game_manager: GameManager,
    player1_vital: int, player2_vital: int, player1_control: int, player2_control: int,
    player1_max_vital: int = 6, player2_max_vital: int = 6
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
        "player1_vital": player1_vital,
        "player2_vital": player2_vital,
        "player1_control": player1_control,
        "player2_control": player2_control,
        "player1_max_vital": player1_max_vital,
        "player2_max_vital": player2_max_vital,
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
        p1_broken = player1_vital >= player1_max_vital
        p2_broken = player2_vital >= player2_max_vital
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
        equipment_result = {
            'player1_valid': True,
            'player2_valid': True,
            'player1_reason': 'Validation disabled; decided in prompt',
            'player2_reason': 'Validation disabled; decided in prompt'
        }
        player1_invalid = None if equipment_result['player1_valid'] else {
            'move': player1_move,
            'reason': equipment_result['player1_reason']
        }
        player2_invalid = None if equipment_result['player2_valid'] else {
            'move': player2_move,
            'reason': equipment_result['player2_reason']
        }
        logger.info(f"[analyze_duel_moves] Analyzing combat outcome...")
        combat_outcome = await analyze_combat_outcome(
            player1_name, player1_move, player1_condition_prev, equipment_result['player1_valid'],
            player2_name, player2_move, player2_condition_prev, equipment_result['player2_valid'],
            player1_invalid, player2_invalid, player1_inventory, player2_inventory,
            room_name, room_description, game_manager,
            recent_rounds=duel_history[-5:]
        )
        narrative = await generate_combat_narrative(
            player1_name, player1_move, combat_outcome['player1_result'],
            player2_name, player2_move, combat_outcome['player2_result'],
            player1_invalid, player2_invalid, current_round,
            room_name, room_description, game_manager,
            recent_rounds=duel_history[-10:]
        )
        p1_vital_delta = int(combat_outcome.get('player1_vital_delta', 0) or 0)
        p2_vital_delta = int(combat_outcome.get('player2_vital_delta', 0) or 0)
        p1_control_delta = int(combat_outcome.get('player1_control_delta', 0) or 0)
        p2_control_delta = int(combat_outcome.get('player2_control_delta', 0) or 0)
        p1_intends_heal = bool(combat_outcome.get('player1_intends_heal', False))
        p2_intends_heal = bool(combat_outcome.get('player2_intends_heal', False))
        p1_vital_delta = max(-1 if p1_intends_heal else 0, min(3, p1_vital_delta))
        p2_vital_delta = max(-1 if p2_intends_heal else 0, min(3, p2_vital_delta))
        p1_control_delta = max(-2, min(2, p1_control_delta))
        p2_control_delta = max(-2, min(2, p2_control_delta))
        try:
            if p1_vital_delta < p2_vital_delta:
                if p1_control_delta <= 0 and p2_control_delta > 0:
                    p1_control_delta, p2_control_delta = 1, 0
                elif p2_control_delta > p1_control_delta:
                    p2_control_delta = min(0, p2_control_delta)
                    p1_control_delta = max(1, p1_control_delta)
            elif p2_vital_delta < p1_vital_delta:
                if p2_control_delta <= 0 and p1_control_delta > 0:
                    p2_control_delta, p1_control_delta = 1, 0
                elif p1_control_delta > p2_control_delta:
                    p1_control_delta = min(0, p1_control_delta)
                    p2_control_delta = max(1, p2_control_delta)
            else:
                if p1_control_delta > 0 and p2_control_delta > 0:
                    if p1_control_delta >= p2_control_delta:
                        p2_control_delta = 0
                    else:
                        p1_control_delta = 0
        except Exception:
            pass
        p1_control_delta = max(-2, min(2, p1_control_delta))
        p2_control_delta = max(-2, min(2, p2_control_delta))
        p1_vital = max(0, duel_info.get('player1_vital', 0) + p1_vital_delta)
        p2_vital = max(0, duel_info.get('player2_vital', 0) + p2_vital_delta)
        p1_control = max(0, min(5, duel_info.get('player1_control', 0) + p1_control_delta))
        p2_control = max(0, min(5, duel_info.get('player2_control', 0) + p2_control_delta))
        duel_info['player1_vital'] = p1_vital
        duel_info['player2_vital'] = p2_vital
        duel_info['player1_control'] = p1_control
        duel_info['player2_control'] = p2_control
        player1_max_vital = 6
        player2_max_vital = 6
        if is_monster_duel:
            player2_max_vital = await get_monster_max_vital(monster_data)
        finishing_owner = duel_info.get('finishing_window_owner')
        if p1_control >= 5 and not finishing_owner:
            duel_info['finishing_window_owner'] = 'player1'
        elif p2_control >= 5 and not finishing_owner:
            duel_info['finishing_window_owner'] = 'player2'
        instant_kill_owner = None
        if prev_finishing_owner == 'player1' and p2_vital_delta > 0:
            instant_kill_owner = 'player1'
        elif prev_finishing_owner == 'player2' and p1_vital_delta > 0:
            instant_kill_owner = 'player2'
        if instant_kill_owner == 'player1':
            p2_vital = player2_max_vital
            duel_info['player2_vital'] = p2_vital
            try:
                combat_outcome['player2_result']['reason'] = (combat_outcome['player2_result'].get('reason') or 'Finished decisively while outmatched')
            except Exception:
                pass
            duel_info['finishing_window_owner'] = None
        elif instant_kill_owner == 'player2':
            p1_vital = player1_max_vital
            duel_info['player1_vital'] = p1_vital
            try:
                combat_outcome['player1_result']['reason'] = (combat_outcome['player1_result'].get('reason') or 'Finished decisively while outmatched')
            except Exception:
                pass
            duel_info['finishing_window_owner'] = None
        p1_broken = p1_vital >= player1_max_vital
        p2_broken = p2_vital >= player2_max_vital
        combat_ends = p1_broken or p2_broken
        logger.info(f"[analyze_duel_moves] Combat ends: {combat_ends} (reason: {'player1_vital_full' if p1_broken else ''} {'player2_vital_full' if p2_broken else ''})")
        try:
            duel_history.append({
                'round': current_round,
                'player1_move': player1_move,
                'player2_move': player2_move,
                'narrative': narrative,
                'player1_result': combat_outcome.get('player1_result', {}),
                'player2_result': combat_outcome.get('player2_result', {}),
                'player1_vital_delta': p1_vital_delta,
                'player2_vital_delta': p2_vital_delta,
                'player1_control_delta': p1_control_delta,
                'player2_control_delta': p2_control_delta,
                'player1_vital': p1_vital,
                'player2_vital': p2_vital,
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
            p1_vital, p2_vital, p1_control, p2_control,
            player1_max_vital, player2_max_vital
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
            await auto_submit_monster_move(duel_id, monster_id, player_data, monster_data, room_id, current_round, game_manager)
        elif player_ids.issubset(set(duel_moves[duel_id].keys())):
            await analyze_duel_moves(duel_id, game_manager)


