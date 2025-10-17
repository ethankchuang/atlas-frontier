import React, { useEffect, useState } from 'react';
import { BookOpenIcon } from '@heroicons/react/24/solid';
import apiService from '@/services/api';

interface QuestObjective {
    id: string;
    quest_id: string;
    objective_type: string;
    description: string;
    target_value: number;
    order_index: number;
}

interface PlayerQuestObjective {
    id: string;
    player_quest_id: string;
    objective_id: string;
    is_completed: boolean;
    current_progress: number;
}

interface QuestStatus {
    quest: {
        id: string;
        name: string;
        description: string;
        gold_reward: number;
        badge_name?: string;
    };
    objectives: Array<QuestObjective & { player_progress: PlayerQuestObjective }>;
    progress: {
        completed: number;
        total: number;
    };
}

interface QuestSummaryPanelProps {
    playerId: string;
    onOpenQuestLog: () => void;
}

const QuestSummaryPanel: React.FC<QuestSummaryPanelProps> = ({ playerId, onOpenQuestLog }) => {
    const [questStatus, setQuestStatus] = useState<QuestStatus | null>(null);
    const [isInitialLoad, setIsInitialLoad] = useState(true);

    useEffect(() => {
        const fetchQuestStatus = async (isInitial = false) => {
            try {
                const data = await apiService.getPlayerQuestStatus(playerId);
                // Check if data contains a valid quest
                if (data && data.quest && data.quest.id) {
                    setQuestStatus(data);
                } else {
                    setQuestStatus(null);
                }
            } catch (error) {
                console.error('[QuestSummaryPanel] Failed to fetch quest status:', error);
                setQuestStatus(null);
            } finally {
                if (isInitial) {
                    setIsInitialLoad(false);
                }
            }
        };

        // Initial fetch
        fetchQuestStatus(true);

        // Poll for updates every 10 seconds (without showing loading state)
        const interval = setInterval(() => fetchQuestStatus(false), 10000);

        return () => clearInterval(interval);
    }, [playerId]);

    if (isInitialLoad) {
        return (
            <div className="bg-black/60 backdrop-blur-md border border-amber-900/50 rounded p-2 font-mono">
                <div className="text-amber-400 text-xs animate-pulse">Loading...</div>
            </div>
        );
    }

    if (!questStatus) {
        return (
            <div className="bg-black/60 backdrop-blur-md border border-amber-900/50 rounded p-2 font-mono">
                <div className="text-gray-400 text-xs">No active quest</div>
            </div>
        );
    }

    return (
        <div className="bg-black/60 backdrop-blur-md border border-amber-900/50 rounded p-2 font-mono">
            {/* Header with quest name and progress */}
            <div className="flex items-center justify-between mb-1">
                <div className="text-amber-400 text-xs font-bold flex items-center gap-1">
                    <BookOpenIcon className="w-3 h-3" />
                    <span>Quest</span>
                </div>
                <button
                    onClick={onOpenQuestLog}
                    className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
                >
                    View
                </button>
            </div>

            {/* Quest Name and Progress */}
            <div className="text-green-400 text-xs font-bold mb-1 truncate">
                {questStatus.quest.name}
            </div>

            {/* Compact Progress Bar */}
            <div className="flex items-center gap-2 text-xs text-gray-400">
                <div className="flex-1 h-1.5 bg-gray-700 rounded overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-amber-500 to-yellow-500 transition-all duration-500"
                        style={{ width: `${(questStatus.progress.completed / questStatus.progress.total) * 100}%` }}
                    />
                </div>
                <span className="text-xs whitespace-nowrap">
                    {questStatus.progress.completed}/{questStatus.progress.total}
                </span>
            </div>
        </div>
    );
};

export default QuestSummaryPanel;
