import React, { useEffect, useState } from 'react';
import { XMarkIcon } from '@heroicons/react/24/solid';
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

interface Quest {
    id: string;
    name: string;
    description: string;
    storyline: string;
    gold_reward: number;
    badge_id?: string;
    badge_name?: string;
    badge_description?: string;
    order_index: number;
}

interface PlayerQuest {
    id: string;
    player_id: string;
    quest_id: string;
    is_completed: boolean;
    completed_at?: string;
    started_at: string;
}

interface QuestWithProgress {
    quest: Quest;
    player_quest: PlayerQuest;
    objectives: Array<QuestObjective & { player_progress: PlayerQuestObjective }>;
    progress: {
        completed: number;
        total: number;
    };
}

interface QuestLogData {
    current_quests: QuestWithProgress[];
    completed_quests: QuestWithProgress[];
}

interface QuestLogModalProps {
    playerId: string;
    isOpen: boolean;
    onClose: () => void;
}

const QuestLogModal: React.FC<QuestLogModalProps> = ({ playerId, isOpen, onClose }) => {
    const [questLog, setQuestLog] = useState<QuestLogData | null>(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'current' | 'completed'>('current');

    useEffect(() => {
        if (!isOpen) return;

        const fetchQuestLog = async () => {
            try {
                setLoading(true);
                const data = await apiService.getPlayerQuestLog(playerId);
                // Ensure data has the expected structure
                if (data && typeof data === 'object') {
                    setQuestLog({
                        current_quests: Array.isArray(data.current_quests) ? data.current_quests : [],
                        completed_quests: Array.isArray(data.completed_quests) ? data.completed_quests : []
                    });
                } else {
                    setQuestLog({ current_quests: [], completed_quests: [] });
                }
            } catch (error) {
                console.error('[QuestLogModal] Failed to fetch quest log:', error);
                setQuestLog({ current_quests: [], completed_quests: [] });
            } finally {
                setLoading(false);
            }
        };

        fetchQuestLog();
    }, [playerId, isOpen]);

    if (!isOpen) return null;

    const renderQuestCard = (questData: QuestWithProgress, isCompleted: boolean) => (
        <div
            key={questData.quest.id}
            className="bg-black/40 border border-amber-900/50 rounded-lg p-4 hover:border-amber-700/50 transition-colors"
        >
            {/* Quest Header */}
            <div className="flex items-start justify-between mb-3">
                <div>
                    <h3 className="text-lg font-bold text-amber-400 mb-1">
                        {questData.quest.name}
                    </h3>
                    <p className="text-sm text-gray-400 italic">
                        {questData.quest.description}
                    </p>
                </div>
                {isCompleted && (
                    <div className="text-2xl">✓</div>
                )}
            </div>

            {/* Progress Bar (only for current quests) */}
            {!isCompleted && (
                <div className="mb-3">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>Progress</span>
                        <span>{questData.progress.completed}/{questData.progress.total}</span>
                    </div>
                    <div className="w-full h-2 bg-gray-700 rounded overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-amber-500 to-yellow-500 transition-all duration-500"
                            style={{ width: `${(questData.progress.completed / questData.progress.total) * 100}%` }}
                        />
                    </div>
                </div>
            )}

            {/* Objectives */}
            <div className="mb-3 space-y-2">
                <div className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                    Objectives
                </div>
                {questData.objectives.map((objective) => (
                    <div key={objective.id} className="flex items-start gap-2 text-sm">
                        <div className={`mt-0.5 ${objective.player_progress.is_completed ? 'text-green-400' : 'text-gray-500'}`}>
                            {objective.player_progress.is_completed ? '✓' : '○'}
                        </div>
                        <div className={objective.player_progress.is_completed ? 'text-gray-400 line-through' : 'text-gray-300'}>
                            {objective.description}
                        </div>
                    </div>
                ))}
            </div>

            {/* Rewards */}
            <div className="pt-3 border-t border-amber-900/30 flex items-center gap-4 text-sm">
                <div className="text-gray-400 font-bold">Rewards:</div>
                <div className="flex items-center gap-1 text-yellow-500">
                    <span>💰</span>
                    <span>{questData.quest.gold_reward} gold</span>
                </div>
                {questData.quest.badge_name && (
                    <div className="flex items-center gap-1 text-purple-400">
                        <span>🏅</span>
                        <span>{questData.quest.badge_name}</span>
                    </div>
                )}
            </div>

            {/* Completion Date */}
            {isCompleted && questData.player_quest.completed_at && (
                <div className="mt-2 text-xs text-gray-500">
                    Completed: {new Date(questData.player_quest.completed_at).toLocaleDateString()}
                </div>
            )}
        </div>
    );

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
            <div className="bg-gray-900 border-2 border-amber-700 rounded-lg w-full max-w-3xl max-h-[80vh] flex flex-col font-mono">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-amber-900/50">
                    <h2 className="text-2xl font-bold text-amber-400">Quest Log</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white transition-colors"
                    >
                        <XMarkIcon className="w-6 h-6" />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-amber-900/50">
                    <button
                        onClick={() => setActiveTab('current')}
                        className={`flex-1 py-3 text-sm font-bold transition-colors ${
                            activeTab === 'current'
                                ? 'bg-amber-900/30 text-amber-400 border-b-2 border-amber-500'
                                : 'text-gray-400 hover:text-gray-300'
                        }`}
                    >
                        Current Quests
                        {questLog && questLog.current_quests.length > 0 && (
                            <span className="ml-2 text-xs bg-amber-900/50 px-2 py-0.5 rounded">
                                {questLog.current_quests.length}
                            </span>
                        )}
                    </button>
                    <button
                        onClick={() => setActiveTab('completed')}
                        className={`flex-1 py-3 text-sm font-bold transition-colors ${
                            activeTab === 'completed'
                                ? 'bg-amber-900/30 text-amber-400 border-b-2 border-amber-500'
                                : 'text-gray-400 hover:text-gray-300'
                        }`}
                    >
                        Completed Quests
                        {questLog && questLog.completed_quests.length > 0 && (
                            <span className="ml-2 text-xs bg-amber-900/50 px-2 py-0.5 rounded">
                                {questLog.completed_quests.length}
                            </span>
                        )}
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-4">
                    {loading ? (
                        <div className="flex items-center justify-center h-full">
                            <div className="text-amber-400 text-lg animate-pulse">Loading quests...</div>
                        </div>
                    ) : questLog ? (
                        <div className="space-y-4">
                            {activeTab === 'current' ? (
                                questLog.current_quests.length > 0 ? (
                                    questLog.current_quests.map((quest) => renderQuestCard(quest, false))
                                ) : (
                                    <div className="text-center text-gray-400 py-8">
                                        No active quests
                                    </div>
                                )
                            ) : (
                                questLog.completed_quests.length > 0 ? (
                                    questLog.completed_quests.map((quest) => renderQuestCard(quest, true))
                                ) : (
                                    <div className="text-center text-gray-400 py-8">
                                        No completed quests yet
                                    </div>
                                )
                            )}
                        </div>
                    ) : (
                        <div className="text-center text-red-400 py-8">
                            Failed to load quest log
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default QuestLogModal;
