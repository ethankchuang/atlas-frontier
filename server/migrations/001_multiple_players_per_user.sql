-- Schema Update: Multiple Players Per User
-- Run this in Supabase SQL Editor after clearing data

-- Remove current_player_id from user_profiles table
ALTER TABLE user_profiles DROP COLUMN IF EXISTS current_player_id;

-- Add user_id column to players table with foreign key constraint
ALTER TABLE players ADD COLUMN user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE;

-- Add index for better performance
CREATE INDEX IF NOT EXISTS idx_players_user_id ON players(user_id);
