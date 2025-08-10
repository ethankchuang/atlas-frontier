import React from 'react';
import useGameStore from '@/store/gameStore';
import websocketService from '@/services/websocket';

const DuelChallengePopup: React.FC = () => {
    const { duelChallenge, setDuelChallenge } = useGameStore();

    if (!duelChallenge) {
        return null;
    }

    const handleAccept = () => {
        console.log('Accepting duel challenge from:', duelChallenge.challengerName);
        // TODO: Implement duel acceptance logic
        websocketService.sendDuelResponse(duelChallenge.challengerId, 'accept');
        setDuelChallenge(null);
    };

    const handleDecline = () => {
        console.log('Declining duel challenge from:', duelChallenge.challengerName);
        // TODO: Implement duel decline logic
        websocketService.sendDuelResponse(duelChallenge.challengerId, 'decline');
        setDuelChallenge(null);
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-black border border-amber-500 rounded-lg p-6 max-w-md mx-4">
                <div className="text-center mb-6">
                    <h3 className="text-amber-500 font-bold text-xl mb-2">Duel Challenge!</h3>
                    <p className="text-green-400 text-lg">
                        <span className="text-yellow-500 font-bold">{duelChallenge.challengerName}</span> has challenged you to a duel!
                    </p>
                    <p className="text-cyan-400 text-sm mt-2">Accept?</p>
                </div>
                
                <div className="flex gap-4 justify-center">
                    <button
                        onClick={handleAccept}
                        className="flex-1 bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded transition-colors"
                    >
                        Yes
                    </button>
                    <button
                        onClick={handleDecline}
                        className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded transition-colors"
                    >
                        No
                    </button>
                </div>
            </div>
        </div>
    );
};

export default DuelChallengePopup; 