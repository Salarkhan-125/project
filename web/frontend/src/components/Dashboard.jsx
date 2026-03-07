import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Server, Cpu, Activity, Shield, ChevronRight,
  AlertCircle, Flag, Clock, Award, ArrowUpRight,
  Flame, Loader, Target, Sparkles, RotateCw
} from 'lucide-react';
import api from '../services/api';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const authHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${localStorage.getItem('token') || ''}`,
});

const useCounter = (target, duration = 1400) => {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    if (target === 0) { setCount(0); return; }
    const start = performance.now();
    const animate = (now) => {
      const p = Math.min((now - start) / duration, 1);
      const e = 1 - Math.pow(1 - p, 4);
      setCount(Math.round(e * target));
      if (p < 1) ref.current = requestAnimationFrame(animate);
    };
    ref.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(ref.current);
  }, [target, duration]);
  return count;
};

const StatCard = ({ icon: Icon, label, value, accent, delay, isLive }) => {
  const animated = useCounter(value ?? 0, 1200);
  return (
    <div
      className="group relative rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50 backdrop-blur p-5 hover:border-orange-500/50 transition-all duration-300"
      style={{ animation: `slideUp 0.4s ease-out ${delay}s both` }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="p-2.5 rounded-xl" style={{ backgroundColor: `${accent}20` }}>
          <Icon className="w-5 h-5" style={{ color: accent }} />
        </div>
        {isLive && (
          <span className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-semibold tracking-widest uppercase">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            live
          </span>
        )}
      </div>
      <p className="text-4xl font-bold text-white tabular-nums leading-none mb-1">{animated}</p>
      <p className="text-xs text-gray-500 uppercase tracking-widest mt-1">{label}</p>
      <div className="absolute bottom-0 left-0 w-full h-0.5 bg-gradient-to-r from-orange-500 to-orange-600 transform scale-x-0 group-hover:scale-x-100 transition-transform duration-500 rounded-b-2xl" />
    </div>
  );
};

const SolveFeedPanel = () => {
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchFeed = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stats/feed?limit=25`, { headers: authHeaders() });
      const data = await res.json();
      setFeed(data.feed || []);
    } catch (_) {}
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchFeed();
    const iv = setInterval(fetchFeed, 15000);
    return () => clearInterval(iv);
  }, []);

  const timeAgo = (iso) => {
    if (!iso) return '';
    const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
    if (diff < 60) return `${diff}s`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    return `${Math.floor(diff / 3600)}h`;
  };

  return (
    <div className="rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50 backdrop-blur p-5 hover:border-orange-500/50 transition-all duration-300"
      style={{ animation: 'slideUp 0.4s ease-out 0.25s both' }}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-white flex items-center gap-2">
          <Activity className="w-4 h-4 text-orange-500" />
          Solve Feed
        </h2>
        <span className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-semibold tracking-widest uppercase">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          live
        </span>
      </div>
      {loading ? (
        <div className="flex items-center justify-center py-10">
          <Loader className="w-5 h-5 text-orange-500 animate-spin" />
        </div>
      ) : feed.length === 0 ? (
        <div className="text-center py-10">
          <Flag className="w-7 h-7 text-gray-700 mx-auto mb-2" />
          <p className="text-xs text-gray-500">No solves yet. Be the first.</p>
        </div>
      ) : (
        <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1"
          style={{ scrollbarWidth: 'thin', scrollbarColor: '#222 transparent' }}>
          {feed.map((entry, i) => (
            <div key={entry.submission_id}
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-black/30 border border-gray-800 hover:border-orange-500/30 transition-colors"
              style={{ animation: `slideUp 0.3s ease-out ${i * 0.03}s both` }}>
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold text-black flex-shrink-0"
                style={{ background: '#ff7300' }}>
                {entry.username?.slice(0, 1).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-xs font-semibold text-gray-100 truncate">{entry.username}</span>
                  {entry.first_blood && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded font-bold tracking-wide"
                      style={{ background: 'linear-gradient(135deg,#dc2626,#7f1d1d)', color: '#fca5a5' }}>
                      1ST BLOOD
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-gray-600 truncate font-mono">
                  <span className="text-orange-500/70">{entry.machine_id?.replace('machine_', '').slice(0, 10)}</span>
                  {entry.points > 0 && <span className="text-emerald-500/80 ml-1">+{entry.points}pts</span>}
                </p>
              </div>
              <span className="text-[10px] text-gray-600 flex-shrink-0">{timeAgo(entry.submitted_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const DiffBadge = ({ level }) => {
  const map = { Easy: '#10b981', Medium: '#f59e0b', Hard: '#f97316', Expert: '#ef4444' };
  const color = map[level] || '#ff7300';
  return (
    <span className="text-[9px] font-semibold px-2 py-0.5 rounded-lg tracking-widest uppercase"
      style={{ color, background: color + '18', border: `1px solid ${color}40` }}>
      {level}
    </span>
  );
};

const Dashboard = () => {
  const navigate  = useNavigate();
  const userId    = localStorage.getItem('userId')   || '';
  const username  = localStorage.getItem('username') || 'Hacker';

  const [stats, setStats]                 = useState({ machines: 0, campaigns: 0, running: 0 });
  const [isLoading, setIsLoading]         = useState(true);
  const [error, setError]                 = useState(null);
  const [activeTab, setActiveTab]         = useState('machines');
  const [userMachines, setUserMachines]   = useState([]);
  const [leaderboard, setLeaderboard]     = useState([]);
  const [todayStats, setTodayStats]       = useState({ solved: 0, flags: 0 });
  const [userCampaigns, setUserCampaigns] = useState([]);

  const fetchAll = useCallback(async () => {
    if (!userId) return;
    try {
      setIsLoading(true);
      const [statsRes, progressRes, campaignsRes, lbRes, machinesRes] = await Promise.all([
        fetch(`${API_BASE}/api/stats?user_id=${encodeURIComponent(userId)}`, { headers: authHeaders() })
          .then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API_BASE}/api/users/${encodeURIComponent(userId)}/progress`, { headers: authHeaders() })
          .then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API_BASE}/api/users/${encodeURIComponent(userId)}/campaigns`, { headers: authHeaders() })
          .then(r => r.ok ? r.json() : []).catch(() => []),
        fetch(`${API_BASE}/api/leaderboard`, { headers: authHeaders() })
          .then(r => r.ok ? r.json() : { entries: [] }).catch(() => ({ entries: [] })),
        api.getMachines().catch(() => []),
      ]);

      const userMachineList = Array.isArray(machinesRes) ? machinesRes : [];
      const runningCount = userMachineList.filter(
        m => m.is_running || m.container?.status === 'running'
      ).length;

      setStats({
        machines:  userMachineList.length,
        campaigns: statsRes?.total_campaigns ?? 0,
        running:   runningCount,
      });

      setUserCampaigns(Array.isArray(campaignsRes) ? campaignsRes : []);
      setUserMachines(userMachineList.slice(0, 10));

      const subs  = progressRes?.recent_submissions || [];
      const today = new Date().toDateString();
      const tSubs = subs.filter(s => new Date(s.submitted_at).toDateString() === today);
      setTodayStats({ solved: tSubs.filter(s => s.correct).length, flags: tSubs.length });

      const lb = Array.isArray(lbRes) ? lbRes : (lbRes?.entries || []);
      setLeaderboard(lb
        .filter(e => (e.total_points || 0) > 0)
        .map(e => ({ ...e, isYou: e.user_id === userId || e.username === username })));

      setIsLoading(false);
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  }, [userId, username]);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(async () => {
      try {
        const machines = await api.getMachines().catch(() => []);
        const running = machines.filter(
          m => m.is_running || m.container?.status === 'running'
        ).length;
        setStats(prev => ({ ...prev, running, machines: machines.length }));
      } catch {}
    }, 5000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  const diffMap = { 1: 'Easy', 2: 'Easy', 3: 'Medium', 4: 'Hard', 5: 'Expert' };

  if (isLoading) return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <div className="text-center">
        <Loader className="w-12 h-12 text-orange-500 animate-spin mx-auto mb-4" />
        <p className="text-gray-400">Loading dashboard...</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-black flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-red-950/20 border border-red-500/50 rounded-2xl p-8 text-center">
        <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
        <h2 className="text-2xl font-bold text-white mb-2">Connection Failed</h2>
        <p className="text-gray-400 mb-6">{error}</p>
        <button onClick={fetchAll} className="px-6 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-lg transition-colors">
          Retry
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-black text-white">
      <div className="max-w-7xl mx-auto px-6 py-8">

        <div className="mb-8 flex items-center justify-between" style={{ animation: 'slideUp 0.4s ease-out both' }}>
          <div>
            <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-white via-orange-500 to-orange-600 bg-clip-text text-transparent">
              Welcome, {username}
            </h1>
            <p className="text-gray-400">
              {new Date().toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </p>
          </div>
          <button onClick={fetchAll} disabled={isLoading}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50">
            <RotateCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="lg:col-span-2 rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50 backdrop-blur overflow-hidden hover:border-orange-500/50 transition-all duration-300"
            style={{ animation: 'slideUp 0.4s ease-out 0.2s both' }}>
            <div className="flex border-b border-gray-800 bg-black/40">
              {[
                { key: 'machines',    label: 'Machines',    icon: Cpu   },
                { key: 'leaderboard', label: 'Leaderboard', icon: Award },
              ].map(t => (
                <button key={t.key} onClick={() => setActiveTab(t.key)}
                  className="flex items-center gap-2 px-5 py-3.5 text-xs font-semibold tracking-wide uppercase transition-all border-b-2"
                  style={{
                    borderBottomColor: activeTab === t.key ? '#f97316' : 'transparent',
                    color: activeTab === t.key ? '#f97316' : '#6b7280',
                  }}>
                  <t.icon className="w-3.5 h-3.5" />
                  {t.label}
                </button>
              ))}
            </div>

            <div className="max-h-80 overflow-y-auto" style={{ scrollbarWidth: 'thin', scrollbarColor: '#222 transparent' }}>
              {activeTab === 'machines' && (
                userMachines.length === 0 ? (
                  <div className="py-14 text-center">
                    <Cpu className="w-8 h-8 text-gray-700 mx-auto mb-2" />
                    <p className="text-sm text-gray-500 mb-3">No machines yet — use Vuln AI to generate one.</p>
                    <button onClick={() => navigate('/vuln-ai')}
                      className="text-sm text-orange-500 hover:text-orange-400 font-medium transition-colors">
                      Open Vuln AI
                    </button>
                  </div>
                ) : (
                  <div>
                    {userMachines.map((m, i) => {
                      const running = m.is_running || m.container?.status === 'running';
                      const diff    = diffMap[m.difficulty] || 'Medium';
                      return (
                        <div key={m.machine_id || i}
                          className="flex items-center gap-4 px-5 py-3.5 border-b border-gray-900 hover:bg-orange-500/3 transition-colors cursor-pointer group"
                          onClick={() => navigate('/machines')}>
                          <div className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                            style={{ background: running ? '#10b981' : '#374151', boxShadow: running ? '0 0 6px #10b981' : 'none' }} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-gray-100 truncate font-mono">
                                {m.cve_id || m.variant || m.machine_id}
                              </span>
                              <DiffBadge level={diff} />
                            </div>
                            <p className="text-[10px] text-gray-600 font-mono mt-0.5">
                              {running ? 'RUNNING' : 'STOPPED'} · {m.machine_id?.replace('machine_', '').slice(0, 10)}
                            </p>
                          </div>
                          <ArrowUpRight className="w-4 h-4 text-gray-700 group-hover:text-orange-500 transition-colors flex-shrink-0" />
                        </div>
                      );
                    })}
                  </div>
                )
              )}

              {activeTab === 'leaderboard' && (
                leaderboard.length === 0 ? (
                  <div className="py-14 text-center">
                    <Award className="w-8 h-8 text-gray-700 mx-auto mb-2" />
                    <p className="text-sm text-gray-500">No entries yet.</p>
                  </div>
                ) : (
                  <div>
                    {leaderboard.slice(0, 8).map((u, i) => {
                      const rankColor = i === 0 ? '#facc15' : i === 1 ? '#9ca3af' : i === 2 ? '#d97706' : '#4b5563';
                      return (
                        <div key={i}
                          className="flex items-center gap-3 px-5 py-3.5 border-b border-gray-900 transition-colors"
                          style={{ background: u.isYou ? 'rgba(249,115,22,0.04)' : undefined }}>
                          <span className="text-xs font-bold w-5 text-center tabular-nums" style={{ color: rankColor }}>{i + 1}</span>
                          <div className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-black flex-shrink-0"
                            style={{ background: u.isYou ? '#f97316' : '#1a1a1a', border: `1px solid ${u.isYou ? '#f97316' : '#333'}` }}>
                            {(u.username || '?').slice(0, 2).toUpperCase()}
                          </div>
                          <div className="flex-1">
                            <span className={`text-sm font-semibold ${u.isYou ? 'text-orange-400' : 'text-gray-200'}`}>
                              {u.username}{u.isYou ? ' you' : ''}
                            </span>
                            {u.machines_solved > 0 && (
                              <span className="ml-2 text-[10px] text-gray-600 font-mono">{u.machines_solved} pwned</span>
                            )}
                          </div>
                          <span className="text-sm font-bold text-white tabular-nums">{(u.total_points || 0).toLocaleString()}</span>
                        </div>
                      );
                    })}
                    <div className="px-5 py-3">
                      <button onClick={() => navigate('/leaderboard')}
                        className="text-xs font-medium text-orange-500 hover:text-orange-400 tracking-wide transition-colors flex items-center gap-1">
                        VIEW FULL BOARD <ArrowUpRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                )
              )}
            </div>
          </div>

          <SolveFeedPanel />
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <StatCard icon={Server}   label="Machines"     value={stats.machines}    accent="#ff7300" delay={0} />
          <StatCard icon={Activity} label="Running"      value={stats.running}     accent="#10b981" delay={0.07} isLive />
          <StatCard icon={Flame}    label="Today Solves" value={todayStats.solved} accent="#f59e0b" delay={0.14} />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" style={{ animation: 'slideUp 0.4s ease-out 0.35s both' }}>
          <div className="rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50 backdrop-blur p-5 hover:border-orange-500/50 transition-all duration-300">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
              <Clock className="w-4 h-4 text-blue-400" />
              Today's Stats
            </h2>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Solved', val: todayStats.solved, color: '#10b981' },
                { label: 'Flags',  val: todayStats.flags,  color: '#f97316' },
              ].map(s => (
                <div key={s.label} className="text-center py-4 rounded-xl border border-gray-800 bg-black/30">
                  <p className="text-3xl font-bold tabular-nums" style={{ color: s.color }}>{s.val}</p>
                  <p className="text-[10px] tracking-widest uppercase mt-1" style={{ color: s.color + '88' }}>{s.label}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-600 mt-3">
              {userCampaigns.length} campaign{userCampaigns.length !== 1 ? 's' : ''} total
            </p>
          </div>

          <div className="rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50 backdrop-blur p-5 hover:border-orange-500/50 transition-all duration-300">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
              <Sparkles className="w-4 h-4 text-yellow-500" />
              Quick Actions
            </h2>
            <div className="space-y-2">
              {[
                { icon: Cpu,    label: 'Browse Machines', sub: 'View your lab environments', color: '#f97316', route: '/machines'    },
                { icon: Award,  label: 'Leaderboard',     sub: 'See top hackers',            color: '#f59e0b', route: '/leaderboard' },
                { icon: Target, label: 'Vuln AI',         sub: 'Generate new machines',      color: '#10b981', route: '/vuln-ai'     },
              ].map(a => (
                <button key={a.label} onClick={() => navigate(a.route)}
                  className="w-full flex items-center justify-between px-4 py-3 rounded-xl border border-gray-800 bg-black/30 hover:bg-gray-900/60 hover:border-orange-500/40 transition-all group">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg" style={{ backgroundColor: a.color + '15' }}>
                      <a.icon className="w-4 h-4" style={{ color: a.color }} />
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-medium text-gray-200 group-hover:text-white transition-colors">{a.label}</p>
                      <p className="text-xs text-gray-500">{a.sub}</p>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-orange-500 group-hover:translate-x-0.5 transition-all" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0);    }
        }
      `}</style>
    </div>
  );
};

export default Dashboard;
