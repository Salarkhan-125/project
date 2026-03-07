// src/App.js
import React, { useState, useMemo } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import { Home, Server, Trophy, LogOut, Bot, Building2, Users, BookOpen } from 'lucide-react';
import hackforgeLogo from './assets/logo.png';

// Import components
import Login from './components/Login';
import Register from './components/Register';
import ForgotPassword from './components/ForgotPassword';
import ResetPassword from './components/ResetPassword';
import Dashboard from './components/Dashboard';
import Campaigns from './components/Campaigns';
import CampaignDetail from './components/CampaignDetail';
import Machines from './components/Machines';
import Leaderboard from './components/Leaderboard';
import Profile from './components/Profile';
import ContainerDebug from './components/ContainerDebug';
import LabChat from './components/LabChat';
import EnterpriseDashboard from './components/EnterpriseDashboard';
import CreatedAccounts from './components/CreatedAccounts';
import LandingPage from './components/LandingPage';
import StaffPortal from './components/StaffPortal';
import AddStudents from './components/AddStudents';

// ─── Enterprise Staff Portal — now a full component in StaffPortal.jsx ──────

// ─── Protected Route wrapper ─────────────────────────────────────────────────
const ProtectedRoute = ({ isLoggedIn, children }) => {
  if (!isLoggedIn) return <Navigate to="/landing" replace />;
  return children;
};

// ─── Navigation — adapts to user role ────────────────────────────────────────
const Navigation = ({ onLogout }) => {
  const location = useLocation();
  const isActive = (path) => location.pathname === path;
  const username = localStorage.getItem('username') || 'User';
  const role = localStorage.getItem('role') || 'individual';

  const navItems = useMemo(() => {
    if (role === 'enterprise_admin') {
      return [
        { path: '/enterprise/admin/dashboard', icon: Building2, label: 'Admin Dashboard' },
        { path: '/enterprise/admin/accounts', icon: Users, label: 'Created Accounts' },
      ];
    }
    if (role === 'enterprise_staff') {
      return [
        { path: '/enterprise/portal', icon: Building2, label: 'Staff Portal' },
        { path: '/leaderboard', icon: Trophy, label: 'Leaderboard' },
        { path: '/campaigns', icon: BookOpen, label: 'Campaigns' },
        { path: '/vuln-ai', icon: Bot, label: 'Vuln AI' },
      ];
    }
    return [
      { path: '/', icon: Home, label: 'Dashboard' },
      { path: '/machines', icon: Server, label: 'Machines' },
      { path: '/leaderboard', icon: Trophy, label: 'Leaderboard' },
      { path: '/vuln-ai', icon: Bot, label: 'Vuln AI' },
    ];
  }, [role]);

  const isEnterprise = role.startsWith('enterprise_');
  const accent = isEnterprise ? '#3b82f6' : '#ff7300';
  const accentHover = isEnterprise ? 'hover:text-blue-400 hover:bg-blue-500/10' : 'hover:text-white hover:bg-gray-900/50';
  const activeClasses = isEnterprise
    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
    : 'bg-orange-500/20 text-orange-500 border border-orange-500/50';

  const roleLabel = role === 'enterprise_admin' ? 'Enterprise Admin'
    : role === 'enterprise_staff' ? 'Enterprise Staff'
      : 'Individual';

  return (
    <header className="border-b border-gray-900 bg-black/50 backdrop-blur-xl sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center overflow-hidden">
              <img src={hackforgeLogo} alt="HackForge" className="w-10 h-10 object-contain" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
                HackForge
              </h1>
              <p className="text-xs text-gray-500">{isEnterprise ? 'Enterprise' : 'Cybersecurity Training'}</p>
            </div>
          </Link>

          {/* Nav links */}
          <nav className="flex items-center gap-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.path);
              return (
                <Link key={item.path} to={item.path}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-300 ${active ? activeClasses : `text-gray-400 ${accentHover}`}`}>
                  <Icon className="w-4 h-4" />
                  <span className="text-sm font-medium">{item.label}</span>
                </Link>
              );
            })}

            {/* ── User avatar + hover profile card ── */}
            <div className="relative group ml-1">
              {/* Trigger */}
              <div className="flex items-center gap-2 px-3 py-2 border border-gray-800 rounded-lg cursor-default hover:border-gray-700 transition-colors">
                <div className="w-6 h-6 rounded-full flex items-center justify-center text-white font-bold text-xs flex-shrink-0"
                  style={{ background: accent }}>
                  {username.slice(0, 1).toUpperCase()}
                </div>
                <span className="text-xs text-gray-400">{username}</span>
                {isEnterprise && (
                  <span className="text-xs text-blue-400 font-semibold">
                    ({role === 'enterprise_admin' ? 'Admin' : 'Staff'})
                  </span>
                )}
              </div>

              {/* Dropdown card */}
              <div className="absolute right-0 top-full mt-2 w-52 rounded-xl border border-gray-800 bg-gray-950 shadow-2xl
                opacity-0 invisible translate-y-1
                group-hover:opacity-100 group-hover:visible group-hover:translate-y-0
                transition-all duration-200 z-50">

                {/* Avatar + name */}
                <div className="p-4 border-b border-gray-800/60">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
                      style={{ background: `linear-gradient(135deg, ${accent}, ${accent}88)` }}>
                      {username.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white truncate">{username}</p>
                      <p className="text-xs text-gray-500">{roleLabel}</p>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="p-2">
                  <button onClick={onLogout}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors">
                    <LogOut className="w-4 h-4" />
                    Logout
                  </button>
                </div>
              </div>
            </div>
          </nav>
        </div>
      </div>

      <style>{`
        @keyframes glow {
          0%, 100% { box-shadow: 0 0 20px ${accent}4d; }
          50%       { box-shadow: 0 0 40px ${accent}99; }
        }
      `}</style>
    </header>
  );
};

// ─── Role-guarded route helper ────────────────────────────────────────────────
const Guarded = ({ roles, children }) => {
  const role = localStorage.getItem('role') || 'individual';
  if (!roles.includes(role)) return <Navigate to="/" replace />;
  return children;
};

// ─── App shell ────────────────────────────────────────────────────────────────
const AppShell = ({ onLogout }) => (
  <div className="min-h-screen bg-black">
    <Navigation onLogout={onLogout} />
    <Routes>
      <Route path="/" element={<Guarded roles={['individual']}><Dashboard /></Guarded>} />
      <Route path="/machines" element={<Guarded roles={['individual']}><Machines /></Guarded>} />
      <Route path="/profile" element={<Guarded roles={['individual']}><Profile /></Guarded>} />
      <Route path="/debug" element={<Guarded roles={['individual']}><ContainerDebug /></Guarded>} />
      <Route path="/leaderboard" element={<Guarded roles={['individual', 'enterprise_staff']}><Leaderboard /></Guarded>} />
      <Route path="/vuln-ai" element={<Guarded roles={['individual', 'enterprise_staff']}><LabChat /></Guarded>} />
      <Route path="/campaigns" element={<Guarded roles={['enterprise_staff']}><Campaigns /></Guarded>} />
      <Route path="/campaigns/:campaignId" element={<Guarded roles={['enterprise_staff']}><CampaignDetail /></Guarded>} />
      <Route path="/enterprise/admin/dashboard" element={<Guarded roles={['enterprise_admin']}><EnterpriseDashboard /></Guarded>} />
      <Route path="/enterprise/admin/accounts" element={<Guarded roles={['enterprise_admin']}><CreatedAccounts /></Guarded>} />
      <Route path="/enterprise/portal" element={<Guarded roles={['enterprise_staff']}><StaffPortal /></Guarded>} />
      <Route path="/enterprise/portal/add-students" element={<Guarded roles={['enterprise_staff']}><AddStudents /></Guarded>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </div>
);

// ─── Main App ─────────────────────────────────────────────────────────────────
function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    return !!(localStorage.getItem('token') && localStorage.getItem('userId'));
  });

  const handleLoginSuccess = (data) => {
    if (data?.token) localStorage.setItem('token', data.token);
    if (data?.userId) localStorage.setItem('userId', data.userId);
    if (data?.username) localStorage.setItem('username', data.username);
    if (data?.role) localStorage.setItem('role', data.role);
    setIsLoggedIn(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('userId');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    localStorage.removeItem('account_type');
    setIsLoggedIn(false);
  };

  return (
    <Router>
      <Routes>
        <Route path="/landing" element={isLoggedIn ? <Navigate to="/" replace /> : <LandingPage />} />
        <Route path="/login" element={isLoggedIn ? <Navigate to="/" replace /> : <Login onLoginSuccess={handleLoginSuccess} />} />
        <Route path="/Register" element={isLoggedIn ? <Navigate to="/" replace /> : <Register onRegisterSuccess={handleLoginSuccess} />} />
        <Route path="/forgot-password" element={isLoggedIn ? <Navigate to="/" replace /> : <ForgotPassword />} />
        <Route path="/reset-password" element={isLoggedIn ? <Navigate to="/" replace /> : <ResetPassword />} />
        <Route path="/*" element={
          <ProtectedRoute isLoggedIn={isLoggedIn}>
            <AppShell onLogout={handleLogout} />
          </ProtectedRoute>
        } />
      </Routes>
    </Router>
  );
}

export default App;
