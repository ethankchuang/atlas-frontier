export type Direction = 'north' | 'south' | 'east' | 'west' | 'up' | 'down';

export interface Item {
    id: string;
    name: string;
    description: string;
    is_takeable: boolean;
    properties: Record<string, string>;
}

export interface NPC {
    id: string;
    name: string;
    description: string;
    current_room: string;
    dialogue_history: Array<Record<string, string>>;
    memory_log: string[];
    last_interaction?: string;
    properties: Record<string, any>;
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
    players: string[];
    visited: boolean;
    properties: Record<string, any>;
}

export interface Player {
    id: string;
    name: string;
    current_room: string;
    inventory: string[];
    quest_progress: Record<string, any>;
    memory_log: string[];
    last_action?: string;
    last_action_text?: string;
}

export interface GameState {
    world_seed: string;
    main_quest_summary: string;
    active_quests: Record<string, Record<string, string>>;
    global_state: Record<string, string>;
    properties: Record<string, any>;
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
    updates: Record<string, any>;
    image_url?: string;
}

export interface ChatMessage {
    player_id: string;
    room_id: string;
    message: string;
    message_type: 'chat' | 'emote' | 'system' | 'room_description' | 'item_obtained';
    timestamp: string;
    id?: string;
    isStreaming?: boolean;
    title?: string;
    description?: string;
    biome?: string;
    players?: Player[];
    x?: number;
    y?: number;
    item_name?: string;
    item_rarity?: number;
    rarity_stars?: string;
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
}