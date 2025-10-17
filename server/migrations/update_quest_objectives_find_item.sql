-- Update quest objectives to use find_item instead of separate find/take
-- This migration removes the redundant "take_item" objective for the Ancient Compass

-- Delete the old "take_item" objective
DELETE FROM quest_objectives
WHERE id = 'obj_awakening_take_compass';

-- Update the "find_item" objective description to be clearer
UPDATE quest_objectives
SET description = 'Find the Ancient Compass nearby'
WHERE id = 'obj_awakening_find_compass';

-- Verify the changes
SELECT id, quest_id, objective_type, description, order_index
FROM quest_objectives
WHERE quest_id = 'quest_the_awakening'
ORDER BY order_index;
