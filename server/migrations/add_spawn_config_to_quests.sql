-- Add spawn_config JSONB column to quests table
ALTER TABLE quests ADD COLUMN IF NOT EXISTS spawn_config JSONB;

-- Update the tutorial quest (order_index = 0) with Ancient Compass spawn configuration
UPDATE quests
SET spawn_config = '{
  "items": [
    {
      "name": "Ancient Compass",
      "description": "A mystical compass that guides travelers through unknown lands. Its needle glows faintly with magical energy, pointing toward your destiny.",
      "rarity": 2,
      "is_takeable": true,
      "properties": {
        "quest_item": true,
        "magical": true
      },
      "capabilities": ["navigation", "magical_guidance"],
      "spawn_location": {
        "type": "adjacent_room",
        "direction_preference": "any",
        "visibility": "obvious"
      },
      "spawn_trigger": "quest_start"
    }
  ]
}'::jsonb
WHERE order_index = 0 AND is_active = true;

-- Verify the update
SELECT id, name, spawn_config FROM quests WHERE order_index = 0;
