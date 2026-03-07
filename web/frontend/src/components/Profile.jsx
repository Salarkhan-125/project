import React, { useState, useEffect } from 'react';
import { User, Award, Target, TrendingUp, Loader, AlertCircle } from 'lucide-react';
import api from '../services/api';

const Profile = () => {
  const [userId] = useState('user_default');
  const [userProgress, setUserProgress] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchUserProgress();
  }, [fetchUserProgress]);

  const fetchUserProgress = async () => {
    try {
      setIsLoading(true);
      const data = await api.getUserProgress(userId);
      setUserProgress(data);
      setIsLoading(false);
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <Loader className="w-12 h-12 text-orange-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading profile...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-red-950/20 border border-red-500/50 rounded-2xl p-8 text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-white mb-2">Error Loading Profile</h2>
          <p className="text-gray-400 mb-6">{error}</p>
          <button
            onClick={fetchUserProgress}
            className="px-6 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-lg transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const user = userProgress?.user || {};

  return (
    <div className="min-h-screen bg-black text-white">
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-white via-orange-500 to-orange-600 bg-clip-text text-transparent">
            Your Profile
          </h1>
          <p className="text-gray-400">Track your progress and achievements</p>
        </div>

        {/* Profile Card */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* User Info */}
          <div className="lg:col-span-1 rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50 backdrop-blur p-6">
            <div className="text-center">
              <div className="w-24 h-24 mx-auto mb-4 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center">
                <User className="w-12 h-12 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-1">
                {user.username || 'Unknown User'}
              </h2>
              <p className="text-gray-400 text-sm mb-4">{user.email || 'No email'}</p>
              <div className="px-4 py-2 rounded-lg bg-orange-500/20 text-orange-500 text-sm font-semibold inline-block">
                {user.role || 'student'}
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="lg:col-span-2 rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50 backdrop-blur p-6">
            <h3 className="text-xl font-bold mb-6 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-orange-500" />
              Statistics
            </h3>
            <div className="grid grid-cols-2 gap-6">
              <div className="text-center p-4 rounded-xl bg-black/30 border border-gray-800">
                <Award className="w-8 h-8 text-orange-500 mx-auto mb-2" />
                <div className="text-3xl font-bold text-white mb-1">
                  {user.total_points || 0}
                </div>
                <p className="text-sm text-gray-400">Total Points</p>
              </div>
              <div className="text-center p-4 rounded-xl bg-black/30 border border-gray-800">
                <Target className="w-8 h-8 text-green-500 mx-auto mb-2" />
                <div className="text-3xl font-bold text-white mb-1">
                  {user.machines_solved || 0}
                </div>
                <p className="text-sm text-gray-400">Machines Solved</p>
              </div>
              <div className="text-center p-4 rounded-xl bg-black/30 border border-gray-800">
                <TrendingUp className="w-8 h-8 text-blue-500 mx-auto mb-2" />
                <div className="text-3xl font-bold text-white mb-1">
                  {user.campaigns_completed || 0}
                </div>
                <p className="text-sm text-gray-400">Campaigns Completed</p>
              </div>
              <div className="text-center p-4 rounded-xl bg-black/30 border border-gray-800">
                <Award className="w-8 h-8 text-purple-500 mx-auto mb-2" />
                <div className="text-3xl font-bold text-white mb-1">
                  #{user.rank || 'N/A'}
                </div>
                <p className="text-sm text-gray-400">Global Rank</p>
              </div>
            </div>
          </div>
        </div>

        {/* Campaigns */}
        <div className="rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50 backdrop-blur p-6 mb-8">
          <h3 className="text-xl font-bold mb-6">Your Campaigns</h3>
          {userProgress?.campaigns && userProgress.campaigns.length > 0 ? (
            <div className="space-y-3">
              {userProgress.campaigns.map((campaign, index) => (
                <div
                  key={campaign.campaign_id}
                  className="p-4 rounded-xl bg-black/30 border border-gray-800 hover:border-orange-500/50 transition-all"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <h4 className="text-white font-semibold">{campaign.campaign_id}</h4>
                      <p className="text-sm text-gray-500">
                        Level {campaign.difficulty} • {campaign.machine_count} machines
                      </p>
                    </div>
                    <div className={`px-3 py-1 rounded-lg text-xs font-semibold ${
                      campaign.completed 
                        ? 'bg-green-950/30 text-green-400 border border-green-500/30'
                        : 'bg-orange-950/30 text-orange-400 border border-orange-500/30'
                    }`}>
                      {campaign.completed ? 'Completed' : 'In Progress'}
                    </div>
                  </div>
                  {campaign.total_points > 0 && (
                    <div className="text-sm text-gray-400">
                      Points earned: <span className="text-orange-500 font-semibold">{campaign.total_points}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p>No campaigns yet. Start your first campaign!</p>
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50 backdrop-blur p-6">
          <h3 className="text-xl font-bold mb-6">Recent Submissions</h3>
          {userProgress?.recent_submissions && userProgress.recent_submissions.length > 0 ? (
            <div className="space-y-2">
              {userProgress.recent_submissions.map((submission, index) => (
                <div
                  key={submission.submission_id}
                  className="p-3 rounded-lg bg-black/30 border border-gray-800 flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${
                      submission.correct ? 'bg-green-500' : 'bg-red-500'
                    }`} />
                    <div>
                      <p className="text-sm text-white">{submission.machine_id}</p>
                      <p className="text-xs text-gray-500">
                        {new Date(submission.submitted_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  {submission.points_awarded > 0 && (
                    <span className="text-orange-500 font-semibold text-sm">
                      +{submission.points_awarded}
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p>No submissions yet. Start solving challenges!</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Profile;
