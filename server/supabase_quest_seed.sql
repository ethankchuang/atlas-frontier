-- Quest System Seed Data
-- Run this after the quest migration to populate initial quests and badges

-- ============================================
-- BADGES
-- ============================================

-- Badge 1: Seeker (Tutorial Quest)
INSERT INTO badges (id, name, description, rarity, image_status)
VALUES (
    'badge_seeker',
    'Seeker',
    'Awarded to those who found the Ancient Compass and began their journey',
    'common',
    'pending'
);

-- Badge 2: Diplomat (First Contact Quest)
INSERT INTO badges (id, name, description, rarity, image_status)
VALUES (
    'badge_diplomat',
    'Diplomat',
    'Awarded to those who made first contact with the inhabitants of this realm',
    'common',
    'pending'
);

-- Badge 3: Wanderer (Explorer Quest)
INSERT INTO badges (id, name, description, rarity, image_status)
VALUES (
    'badge_wanderer',
    'Wanderer',
    'Awarded to intrepid explorers who discovered the diversity of this world',
    'rare',
    'pending'
);

-- Badge 4: Warrior (Combat Quest)
INSERT INTO badges (id, name, description, rarity, image_status)
VALUES (
    'badge_warrior',
    'Warrior',
    'Awarded to those who proved their mettle in combat',
    'rare',
    'pending'
);

-- ============================================
-- QUESTS
-- ============================================

-- Quest 1: The Awakening (Tutorial)
INSERT INTO quests (id, name, description, storyline, gold_reward, badge_id, order_index, is_active)
VALUES (
    'quest_the_awakening',
    'The Awakening',
    'Find the Ancient Compass to begin your journey in this mysterious realm',
    E'You awaken in an unfamiliar place, your memories hazy...\n\nThe air feels thick with magic and possibility. Somewhere nearby, you sense an artifact calling to you—an Ancient Compass that will guide your path through this medieval realm.\n\nTo survive here, you must learn the basics:\n• Move through the world using directional commands\n• Observe your surroundings carefully\n• Interact with what you find\n\nThe compass awaits in a room not far from here. Begin your journey...',
    50,
    'badge_seeker',
    0,
    true
);

-- Quest 2: First Contact
INSERT INTO quests (id, name, description, storyline, gold_reward, badge_id, order_index, is_active)
VALUES (
    'quest_first_contact',
    'First Contact',
    'Speak with one of the inhabitants of this world to learn more about your surroundings',
    E'As you journey through this realm, you encounter many inhabitants—travelers, merchants, scholars, and wanderers.\n\nEach has their own story, their own knowledge to share. To truly understand this world, you must learn to communicate with those who call it home.\n\nSeek out an inhabitant and engage them in conversation. Listen to what they have to say...',
    75,
    'badge_diplomat',
    1,
    true
);

-- Quest 3: The Explorer
INSERT INTO quests (id, name, description, storyline, gold_reward, badge_id, order_index, is_active)
VALUES (
    'quest_the_explorer',
    'The Explorer',
    'Discover three different biomes to understand the diversity of this world',
    E'This realm is vast and varied, with landscapes as diverse as they are mysterious.\n\nFrom dense forests to arid deserts, from towering mountains to murky swamps—each biome holds its own secrets, its own dangers, and its own rewards.\n\nVenture forth and discover the diversity of this world. Let your footsteps mark three different lands...',
    100,
    'badge_wanderer',
    2,
    true
);

-- Quest 4: Trial by Combat
INSERT INTO quests (id, name, description, storyline, gold_reward, badge_id, order_index, is_active)
VALUES (
    'quest_trial_by_combat',
    'Trial by Combat',
    'Prove your worth in battle by defeating a creature or winning a duel',
    E'In this realm, strength is tested not just by wit and will, but by steel and skill.\n\nCreatures roam the lands, some peaceful, others hostile. Adventurers like yourself may challenge one another to honorable duels.\n\nThe time has come to prove your mettle. Face a foe in combat and emerge victorious...',
    150,
    'badge_warrior',
    3,
    true
);

-- ============================================
-- QUEST OBJECTIVES
-- ============================================

-- The Awakening Objectives
INSERT INTO quest_objectives (id, quest_id, objective_type, objective_data, order_index, description)
VALUES
(
    'obj_awakening_move',
    'quest_the_awakening',
    'move_n_times',
    '{"required_count": 2}',
    0,
    'Move through the world (0/2 moves)'
),
(
    'obj_awakening_look',
    'quest_the_awakening',
    'use_command',
    '{"command": "look"}',
    1,
    'Use the "look" command to observe your surroundings'
),
(
    'obj_awakening_find_compass',
    'quest_the_awakening',
    'find_item',
    '{"item_name": "Ancient Compass", "item_description": "A mystical compass that guides travelers through unknown lands"}',
    2,
    'Find the Ancient Compass nearby'
);

-- First Contact Objectives
INSERT INTO quest_objectives (id, quest_id, objective_type, objective_data, order_index, description)
VALUES
(
    'obj_first_contact_talk',
    'quest_first_contact',
    'talk_to_npc',
    '{"required_count": 1}',
    0,
    'Speak with any NPC (0/1)'
);

-- The Explorer Objectives
INSERT INTO quest_objectives (id, quest_id, objective_type, objective_data, order_index, description)
VALUES
(
    'obj_explorer_biomes',
    'quest_the_explorer',
    'visit_biomes',
    '{"required_count": 3}',
    0,
    'Discover 3 different biomes (0/3)'
);

-- Trial by Combat Objectives
INSERT INTO quest_objectives (id, quest_id, objective_type, objective_data, order_index, description)
VALUES
(
    'obj_combat_win',
    'quest_trial_by_combat',
    'win_combat',
    '{"required_count": 1, "types": ["monster", "duel"]}',
    0,
    'Defeat a creature or win a duel (0/1)'
);
