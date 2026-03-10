import React, { useState, useEffect } from 'react';
import { Trophy, Medal, Award, Loader, AlertCircle } from 'lucide-react';
import api from '../services/api';

const Leaderboard = () => {
  const [leaderboard, setLeaderboard] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeframe, setTimeframe] = useState('all_time');

  const [role] = useState(() => localStorage.getItem('role') || 'individual');
  const isEnterprise = role.startsWith('enterprise_');

  // Theme Constants
  const themeTrophyClass = isEnterprise ? 'text-blue-400' : 'text-yellow-500';
  const rank1Class = isEnterprise ? 'from-blue-400/20 to-blue-500/5 border-blue-400/50' : 'from-yellow-500/20 to-yellow-600/5 border-yellow-500/50';
  const rank3Class = isEnterprise ? 'from-blue-600/20 to-blue-700/5 border-blue-600/50' : 'from-orange-500/20 to-orange-600/5 border-orange-500/50';
  const rank3IconClass = isEnterprise ? 'text-blue-600' : 'text-orange-600';
  const textPrimaryClass = isEnterprise ? 'text-blue-500' : 'text-orange-500';
  const bgPrimaryClass = isEnterprise ? 'bg-blue-500' : 'bg-orange-500';
  const bgPrimaryHoverClass = isEnterprise ? 'hover:bg-blue-600' : 'hover:bg-orange-600';
  const titleGradientClass = isEnterprise ? 'from-white via-blue-400 to-blue-600' : 'from-white via-yellow-500 to-yellow-600';

  useEffect(() => { fetchLeaderboard(); fetchFirstBloods(); }, [timeframe]);

  const [firstBloods, setFirstBloods] = React.useState({});
  const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const fetchFirstBloods = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stats/feed?limit=100`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
      });
      const data = await res.json();
      // Count first bloods per user
      const counts = {};
      (data.feed || []).forEach(e => {
        if (e.first_blood) counts[e.user_id] = (counts[e.user_id] || 0) + 1;
      });
      setFirstBloods(counts);
    } catch (err) {
      console.warn("Failed to fetch first bloods:", err);
    }
  };

  const fetchLeaderboard = async () => {
    try {
      setIsLoading(true);
      const data = await api.getLeaderboard(100, timeframe);
      setLeaderboard((data.entries || []).filter(e => (e.total_points || 0) > 0));
      setIsLoading(false);
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  };

  const getRankIcon = (rank) => {
    if (rank === 1) return <Trophy className={`w-6 h-6 ${themeTrophyClass}`} />;
    if (rank === 2) return <Medal className="w-6 h-6 text-gray-400" />;
    if (rank === 3) return <Award className={`w-6 h-6 ${rank3IconClass}`} />;
    return null;
  };

  const getRankColor = (rank) => {
    if (rank === 1) return rank1Class;
    if (rank === 2) return 'from-gray-400/20 to-gray-500/5 border-gray-400/50';
    if (rank === 3) return rank3Class;
    return 'from-gray-900/50 to-black/50 border-gray-800';
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <Loader className={`w-12 h-12 ${textPrimaryClass} animate-spin mx-auto mb-4`} />
          <p className="text-gray-400">Loading leaderboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-red-950/20 border border-red-500/50 rounded-2xl p-8 text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-white mb-2">Error Loading Leaderboard</h2>
          <p className="text-gray-400 mb-6">{error}</p>
          <button onClick={fetchLeaderboard}
            className={`px-6 py-3 ${bgPrimaryClass} ${bgPrimaryHoverClass} text-white rounded-lg transition-colors`}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-white">
      <div className="max-w-5xl mx-auto px-6 py-8">

        <div className="mb-8">
          <h1 className={`text-4xl font-bold mb-2 bg-gradient-to-r ${titleGradientClass} bg-clip-text text-transparent`}>
            Global Leaderboard
          </h1>
          <p className="text-gray-400">Top hackers ranked by their achievements</p>
        </div>

        {/* Timeframe Selector */}
        <div className="flex gap-2 mb-8">
          {['all_time', 'monthly', 'weekly'].map((tf) => (
            <button key={tf} onClick={() => setTimeframe(tf)}
              className={`px-4 py-2 rounded-lg font-medium transition-all duration-300 ${timeframe === tf
                ? `${bgPrimaryClass} text-white`
                : 'bg-gray-900 text-gray-400 hover:bg-gray-800'
                }`}>
              {tf.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
            </button>
          ))}
        </div>

        {leaderboard.length === 0 ? (
          <div className="text-center py-16 rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50">
            <Trophy className="w-24 h-24 text-gray-700 mx-auto mb-4" />
            <h3 className="text-2xl font-bold text-gray-600 mb-2">No Entries Yet</h3>
            <p className="text-gray-500">Be the first to complete a challenge!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {leaderboard.map((entry, index) => (
              <div key={entry.user_id || index}
                className={`relative rounded-2xl border bg-gradient-to-r p-6 transition-all duration-300 hover:scale-[1.02] ${getRankColor(index + 1)}`}
                style={{ animation: `slideUp 0.4s ease-out ${Math.min(index, 10) * 0.05}s both` }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center justify-center w-12 h-12">
                      {getRankIcon(index + 1) || (
                        <span className="text-2xl font-bold text-gray-500">#{index + 1}</span>
                      )}
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-white flex items-center gap-2">
                        {entry.username || entry.user_id}
                        {firstBloods[entry.user_id] > 0 && (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg font-bold tracking-wide"
                            style={{ background: 'linear-gradient(135deg, #dc2626, #991b1b)', color: '#fca5a5', boxShadow: '0 0 10px #dc262644' }}>
                            🩸 {firstBloods[entry.user_id]}x Blood
                          </span>
                        )}
                      </h3>
                      <p className="text-sm text-gray-400">
                        {entry.machines_solved || 0} machines solved
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-3xl font-bold ${textPrimaryClass}`}>
                      {entry.total_points || 0}
                    </div>
                    <p className="text-xs text-gray-400">points</p>
                  </div>
                </div>

                {/* Stats Bar — Campaigns removed, only Machines + Points */}
                <div className="mt-4 pt-4 border-t border-gray-800 grid grid-cols-2 gap-4 text-sm">
                  <div className="text-center">
                    <p className="text-gray-400">Machines Solved</p>
                    <p className="text-white font-semibold">{entry.machines_solved || 0}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-gray-400">Total Points</p>
                    <p className="text-white font-semibold">{entry.total_points || 0}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>


    </div>
  );
};

export default Leaderboard;
