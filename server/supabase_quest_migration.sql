-- Quest System Migration for Supabase
-- Run this migration after the main schema is set up

-- Badges table - Badge definitions with AI-generated images
CREATE TABLE badges (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    image_url TEXT,
    image_status TEXT DEFAULT 'pending', -- pending, generating, ready, error
    rarity TEXT DEFAULT 'common', -- common, rare, epic, legendary
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Quests table - Quest definitions
CREATE TABLE quests (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    storyline TEXT NOT NULL, -- The narrative text shown in chat
    gold_reward INTEGER NOT NULL DEFAULT 0,
    badge_id TEXT REFERENCES badges(id) ON DELETE SET NULL,
    order_index INTEGER NOT NULL DEFAULT 0, -- Sequential ordering (0 = tutorial)
    is_daily BOOLEAN DEFAULT FALSE, -- For future AI-generated daily quests
    is_active BOOLEAN DEFAULT TRUE, -- Can be toggled on/off
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Quest objectives table - Extensible quest completion criteria
CREATE TABLE quest_objectives (
    id TEXT PRIMARY KEY,
    quest_id TEXT NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    objective_type TEXT NOT NULL, -- find_item, move_n_times, use_command, visit_biome, talk_to_npc, defeat_monster, etc.
    objective_data JSONB NOT NULL, -- Flexible data for each type
    order_index INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL, -- Shown to player
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Player quests table - Player quest progress
CREATE TABLE player_quests (
    id TEXT PRIMARY KEY,
    player_id TEXT NOT NULL,
    quest_id TEXT NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'available', -- available, in_progress, completed, claimed
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    storyline_shown BOOLEAN DEFAULT FALSE, -- Has intro been displayed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(player_id, quest_id)
);

-- Player quest objectives table - Individual objective tracking
CREATE TABLE player_quest_objectives (
    id TEXT PRIMARY KEY,
    player_quest_id TEXT NOT NULL REFERENCES player_quests(id) ON DELETE CASCADE,
    objective_id TEXT NOT NULL REFERENCES quest_objectives(id) ON DELETE CASCADE,
    is_completed BOOLEAN DEFAULT FALSE,
    progress_data JSONB, -- For counting objectives: {"current": 2, "required": 3}
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(player_quest_id, objective_id)
);

-- Player badges table - Badge collection
CREATE TABLE player_badges (
    id TEXT PRIMARY KEY,
    player_id TEXT NOT NULL,
    badge_id TEXT NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
    earned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(player_id, badge_id)
);

-- Player gold ledger table - Gold transactions (audit trail)
CREATE TABLE player_gold_ledger (
    id TEXT PRIMARY KEY,
    player_id TEXT NOT NULL,
    amount INTEGER NOT NULL, -- Positive for credit, negative for debit
    transaction_type TEXT NOT NULL, -- quest_reward, purchase, sale, transfer, etc.
    reference_id TEXT, -- Quest ID, item ID, etc.
    description TEXT,
    balance_after INTEGER NOT NULL, -- Running balance
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for better performance
CREATE INDEX idx_badges_rarity ON badges(rarity);
CREATE INDEX idx_badges_updated_at ON badges(updated_at);

CREATE INDEX idx_quests_order_index ON quests(order_index);
CREATE INDEX idx_quests_is_active ON quests(is_active);
CREATE INDEX idx_quests_is_daily ON quests(is_daily);
CREATE INDEX idx_quests_updated_at ON quests(updated_at);

CREATE INDEX idx_quest_objectives_quest_id ON quest_objectives(quest_id);
CREATE INDEX idx_quest_objectives_order_index ON quest_objectives(order_index);

CREATE INDEX idx_player_quests_player_id ON player_quests(player_id);
CREATE INDEX idx_player_quests_quest_id ON player_quests(quest_id);
CREATE INDEX idx_player_quests_status ON player_quests(status);
CREATE INDEX idx_player_quests_player_status ON player_quests(player_id, status);

CREATE INDEX idx_player_quest_objectives_player_quest_id ON player_quest_objectives(player_quest_id);
CREATE INDEX idx_player_quest_objectives_objective_id ON player_quest_objectives(objective_id);
CREATE INDEX idx_player_quest_objectives_completed ON player_quest_objectives(is_completed);

CREATE INDEX idx_player_badges_player_id ON player_badges(player_id);
CREATE INDEX idx_player_badges_badge_id ON player_badges(badge_id);

CREATE INDEX idx_player_gold_ledger_player_id ON player_gold_ledger(player_id);
CREATE INDEX idx_player_gold_ledger_transaction_type ON player_gold_ledger(transaction_type);
CREATE INDEX idx_player_gold_ledger_created_at ON player_gold_ledger(created_at DESC);

-- Triggers to update updated_at timestamp
CREATE TRIGGER update_badges_updated_at
    BEFORE UPDATE ON badges
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_quests_updated_at
    BEFORE UPDATE ON quests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_quest_objectives_updated_at
    BEFORE UPDATE ON quest_objectives
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_player_quests_updated_at
    BEFORE UPDATE ON player_quests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_player_quest_objectives_updated_at
    BEFORE UPDATE ON player_quest_objectives
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
