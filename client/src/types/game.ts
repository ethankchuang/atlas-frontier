export type Direction = 'north' | 'south' | 'east' | 'west' | 'up' | 'down';

export interface Item {
    id: string;
    name: string;
    description: string;
    is_takeable?: boolean;
    properties: Record<string, string>;
    rarity?: number;
    capabilities?: string[];
}

export interface NPC {
    id: string;
    name: string;
    description: string;
    current_room: string;
    dialogue_history: Array<Record<string, string>>;
    memory_log: string[];
    last_interaction?: string;
    properties: Record<string, unknown>;
}

export interface Room {
    id: string;
    title: string;
    description: string;
    x: number;
    y: number;
    biome?: string;
    biome_color?: string;
    image_url: string;
    image_status: 'pending' | 'generating' | 'content_ready' | 'ready' | 'error';
    image_prompt?: string;
    connections: Record<string, string>;
    npcs: string[];
    items: string[];
    monsters: string[];
    players: string[];
    visited: boolean;
    properties: Record<string, unknown>;
}

export interface Player {
    id: string;
    user_id: string;
    name: string;
    current_room: string;
    inventory: string[];
    quest_progress: Record<string, unknown>;
    memory_log: string[];
    last_action?: string;
    last_action_text?: string;
    health?: number;  // Player health (default 5)
    rejoin_immunity?: boolean;  // Temporary immunity to aggressive monsters when rejoining
}

export interface GameState {
    world_seed: string;
    main_quest_summary: string;
    active_quests: Record<string, Record<string, string>>;
    global_state: Record<string, string>;
    properties: Record<string, unknown>;
}

export interface ActionRequest {
    player_id: string;
    action: string;
    room_id: string;
    target?: string;
}

export interface ActionResponse {
    success: boolean;
    message: string;
    updates: Record<string, unknown>;
    image_url?: string;
}

export type ChatMessageType = 'chat' | 'emote' | 'system' | 'room_description' | 'action_result' | 'narration' | 'item_found' | 'item_obtained' | 'duel_outcome' | 'monster_combat_outcome' | 'ai_response' | 'quest_storyline' | 'quest_completion' | 'npc_dialogue';

export interface Monster {
    id: string;
    name: string;
    description: string;
    aggressiveness: string;
    intelligence: string;
    size: string;
    special_effects: string;
    location: string;
    health: number;
    is_alive: boolean;
    properties: Record<string, string>;
}

export interface ChatMessage {
    player_id: string;
    room_id: string;
    message: string;
    message_type: ChatMessageType;
    timestamp: string;
    id?: string;
    isStreaming?: boolean;
    title?: string;
    description?: string;
    biome?: string;
    players?: Player[];
    monsters?: Monster[];
    atmospheric_presence?: string;
    x?: number;
    y?: number;
    item_name?: string;
    item_rarity?: number;
    item_type?: string;
    rarity_stars?: string;
    quest_data?: Record<string, unknown>;
    npc_id?: string;
    npc_name?: string;
}

export interface NPCInteraction {
    player_id: string;
    npc_id: string;
    room_id: string;
    message: string;
    context: Record<string, string>;
}

export interface RoomInfo {
    room: Room;
    players: Player[];
    npcs: NPC[];
    items: Item[];
    monsters: Monster[];
}

export interface MonsterCombatOutcome {
    type: 'monster_combat_outcome';
    round: number;
    monster_name: string;
    player_move: string;
    monster_move: string;
    player_condition: string;
    monster_condition: string;
    narrative: string;
    combat_ends: boolean;
    monster_defeated: boolean;
    player_vital?: number;
    monster_vital?: number;
    player_control?: number;
    monster_control?: number;
}