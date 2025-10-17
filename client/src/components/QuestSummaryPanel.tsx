import React, { useEffect, useState, useRef } from 'react';
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
    const [isExpanded, setIsExpanded] = useState(true); // Start expanded for new players
    const [opacity, setOpacity] = useState(1);
    const fadeTimerRef = useRef<NodeJS.Timeout | null>(null);

    // Auto-fade after 10 seconds of inactivity
    useEffect(() => {
        const resetFadeTimer = () => {
            if (fadeTimerRef.current) {
                clearTimeout(fadeTimerRef.current);
            }
            setOpacity(1);
            fadeTimerRef.current = setTimeout(() => {
                setOpacity(0.3);
            }, 10000);
        };

        resetFadeTimer();
        return () => {
            if (fadeTimerRef.current) {
                clearTimeout(fadeTimerRef.current);
            }
        };
    }, [questStatus, isExpanded]);

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

    const handleMouseEnter = () => {
        setOpacity(1);
        if (fadeTimerRef.current) {
            clearTimeout(fadeTimerRef.current);
        }
    };

    const handleMouseLeave = () => {
        fadeTimerRef.current = setTimeout(() => {
            setOpacity(0.3);
        }, 10000);
    };

    if (isInitialLoad) {
        return null;
    }

    if (!questStatus) {
        return null;
    }

    // Compact view
    if (!isExpanded) {
        return (
            <div 
                className="transition-opacity duration-300 cursor-pointer w-auto"
                style={{ opacity }}
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
                onClick={() => setIsExpanded(true)}
            >
                <div className="bg-black/80 border border-amber-500 rounded-lg px-2 py-1.5 hover:bg-black/90 transition-colors">
                    <div className="flex items-center gap-1.5">
                        <BookOpenIcon className="h-4 w-4 text-amber-500" />
                        <span className="text-amber-400 font-bold text-sm">
                            {questStatus.progress.completed}/{questStatus.progress.total}
                        </span>
                    </div>
                </div>
            </div>
        );
    }

    // Expanded view
    return (
        <div 
            className="bg-black/90 backdrop-blur-md border border-amber-500 rounded-lg p-2 font-mono transition-opacity duration-300 w-auto min-w-[180px]"
            style={{ opacity }}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            {/* Header with quest name and progress */}
            <div className="flex items-center justify-between mb-1">
                <div className="text-amber-400 text-sm font-bold flex items-center gap-1">
                    <BookOpenIcon className="w-4 h-4" />
                    <span>Quest</span>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={onOpenQuestLog}
                        className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
                    >
                        View
                    </button>
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            setIsExpanded(false);
                        }}
                        className="text-amber-400 hover:text-amber-300 text-sm font-bold ml-1"
                        title="Minimize"
                    >
                        ✕
                    </button>
                </div>
            </div>

            {/* Quest Name and Progress */}
            <div className="text-green-400 text-sm font-bold mb-1 truncate">
                {questStatus.quest.name}
            </div>

            {/* Compact Progress Bar */}
            <div className="flex items-center gap-2 text-sm mb-2">
                <div className="flex-1 h-2 bg-gray-700 rounded overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-amber-500 to-yellow-500 transition-all duration-500"
                        style={{ width: `${(questStatus.progress.completed / questStatus.progress.total) * 100}%` }}
                    />
                </div>
                <span className="text-sm whitespace-nowrap text-amber-300">
                    {questStatus.progress.completed}/{questStatus.progress.total}
                </span>
            </div>

            {/* Objectives List */}
            <div className="space-y-1 border-t border-amber-900/30 pt-2">
                {questStatus.objectives.map((objective) => (
                    <div key={objective.id} className="flex items-start gap-1.5 text-sm">
                        <div className={`mt-0.5 ${objective.player_progress.is_completed ? 'text-green-400' : 'text-amber-400/50'}`}>
                            {objective.player_progress.is_completed ? '✓' : '○'}
                        </div>
                        <div className={objective.player_progress.is_completed ? 'text-green-300/70 line-through' : 'text-green-200'}>
                            {objective.description}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default QuestSummaryPanel;
