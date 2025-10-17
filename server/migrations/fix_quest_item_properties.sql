-- Fix quest items with boolean properties - convert to strings
-- This updates all existing quest items to use string values in properties

-- Update items where properties contain boolean values
UPDATE items
SET data = jsonb_set(
    jsonb_set(
        data,
        '{properties,quest_item}',
        '"True"'::jsonb,
        true
    ),
    '{properties,magical}',
    CASE
        WHEN data->'properties'->>'magical' = 'true' THEN '"True"'::jsonb
        WHEN data->'properties'->>'magical' = 'false' THEN '"False"'::jsonb
        ELSE data->'properties'->'magical'
    END,
    true
)
WHERE data->'properties'->>'quest_item' = 'true'
   OR (data->'properties'->'quest_item')::text = 'true';

-- Verify the fix
SELECT id, data->'name' as name, data->'properties' as properties
FROM items
WHERE data->'properties'->>'quest_item' = 'True'
   OR data->'properties'->>'quest_item' = 'true';
