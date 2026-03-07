import React, { useState } from 'react';
import { Building2, UserPlus, Mail, Lock, User, Eye, EyeOff, Loader, AlertCircle, CheckCircle, Shield } from 'lucide-react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ─── Enterprise Admin Dashboard ──────────────────────────────────────────────
const EnterpriseDashboard = () => {
    const role = localStorage.getItem('role') || '';
    const username = localStorage.getItem('username') || 'Admin';

    // Guard: only enterprise_admin can see this
    if (role !== 'enterprise_admin') {
        return (
            <div className="min-h-[60vh] flex items-center justify-center">
                <div className="text-center space-y-4">
                    <div className="w-16 h-16 rounded-2xl bg-red-500/15 border border-red-500/30 flex items-center justify-center mx-auto">
                        <Shield className="w-8 h-8 text-red-500" />
                    </div>
                    <h2 className="text-2xl font-bold text-white">Access Denied</h2>
                    <p className="text-gray-500 text-sm max-w-md">
                        You don't have permission to access the Enterprise Admin Dashboard.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto px-6 py-8">
            <style>{`
                @keyframes fadeUp {
                    from { opacity: 0; transform: translateY(16px); }
                    to   { opacity: 1; transform: translateY(0); }
                }
                .fade-in { animation: fadeUp 0.4s ease both; }
                .fade-in-d { animation: fadeUp 0.4s ease 0.1s both; }
            `}</style>

            {/* Header */}
            <div className="flex items-center gap-4 mb-8 fade-in">
                <div className="w-14 h-14 rounded-2xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
                    <Building2 className="w-7 h-7 text-blue-400" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-white">Enterprise Admin Dashboard</h1>
                    <p className="text-gray-500 text-sm">
                        Welcome, <span className="text-blue-400 font-semibold">{username}</span> — manage your organization's accounts
                    </p>
                </div>
            </div>

            {/* Content */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Create Staff Account Form */}
                <div className="lg:col-span-2 fade-in-d">
                    <CreateStaffForm />
                </div>

                {/* Info Panel */}
                <div className="space-y-4 fade-in-d">
                    <div className="rounded-xl border border-gray-900 bg-gray-950/60 p-5">
                        <h3 className="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
                            <Shield className="w-4 h-4 text-blue-400" />
                            Admin Permissions
                        </h3>
                        <ul className="space-y-2 text-xs text-gray-500">
                            <li className="flex items-start gap-2">
                                <span className="text-blue-400 mt-0.5">✓</span>
                                Create staff/teacher accounts
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-blue-400 mt-0.5">✓</span>
                                Staff inherit your organization
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-blue-400 mt-0.5">✓</span>
                                Password set by admin (no self-reset)
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-gray-600 mt-0.5">◻</span>
                                <span className="text-gray-600">Analytics (coming soon)</span>
                            </li>
                        </ul>
                    </div>

                    <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4">
                        <p className="text-xs text-blue-300/80 leading-relaxed">
                            <strong className="text-blue-400">Security note:</strong> Staff accounts are automatically
                            linked to your organization. They cannot reset their own passwords — only you can manage credentials.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};


// ─── Create Staff Account Form ───────────────────────────────────────────────
const CreateStaffForm = () => {
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPwd, setShowPwd] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSuccess(null);

        // Client-side validation
        if (!firstName.trim() || !email.trim() || !password.trim()) {
            setError('Please fill in all required fields.');
            return;
        }
        if (password.length < 8) {
            setError('Password must be at least 8 characters.');
            return;
        }

        try {
            setLoading(true);

            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE}/api/auth/enterprise/create-user`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({
                    first_name: firstName.trim(),
                    last_name: lastName.trim(),
                    email: email.trim(),
                    password,
                }),
            });

            if (!response.ok) {
                const body = await response.json().catch(() => ({}));
                throw new Error(body.detail || 'Failed to create account.');
            }

            const data = await response.json();
            setSuccess(`Staff account created for ${data.email} (username: ${data.username})`);

            // Reset form
            setFirstName('');
            setLastName('');
            setEmail('');
            setPassword('');
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="rounded-xl border border-gray-900 bg-gray-950/60 overflow-hidden">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-900 flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
                    <UserPlus className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                    <h2 className="text-sm font-bold text-white">Create Staff Account</h2>
                    <p className="text-xs text-gray-600">Add a new staff or teacher to your organization</p>
                </div>
            </div>

            <div className="px-6 py-5">
                {/* Success banner */}
                {success && (
                    <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-green-500/10 border border-green-500/25 mb-4">
                        <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                        <p className="text-green-400 text-xs">{success}</p>
                    </div>
                )}

                {/* Error banner */}
                {error && (
                    <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/25 mb-4">
                        <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                        <p className="text-red-400 text-xs">{error}</p>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">

                    {/* Name row */}
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
                                First Name *
                            </label>
                            <div className="relative">
                                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                                <input
                                    type="text"
                                    placeholder="John"
                                    value={firstName}
                                    onChange={e => { setFirstName(e.target.value); setError(null); }}
                                    className="w-full pl-10 pr-3 py-2.5 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[#3f3f3f]"
                                />
                            </div>
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
                                Last Name
                            </label>
                            <input
                                type="text"
                                placeholder="Doe"
                                value={lastName}
                                onChange={e => setLastName(e.target.value)}
                                className="w-full px-3 py-2.5 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[#3f3f3f]"
                            />
                        </div>
                    </div>

                    {/* Email */}
                    <div>
                        <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
                            Email *
                        </label>
                        <div className="relative">
                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                            <input
                                type="email"
                                placeholder="staff@company.com"
                                value={email}
                                onChange={e => { setEmail(e.target.value); setError(null); }}
                                className="w-full pl-10 pr-3 py-2.5 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[#3f3f3f]"
                            />
                        </div>
                    </div>

                    {/* Password */}
                    <div>
                        <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
                            Password *
                        </label>
                        <div className="relative">
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                            <input
                                type={showPwd ? 'text' : 'password'}
                                placeholder="Minimum 8 characters"
                                value={password}
                                onChange={e => { setPassword(e.target.value); setError(null); }}
                                className="w-full pl-10 pr-10 py-2.5 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[#3f3f3f]"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPwd(v => !v)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 transition-colors"
                            >
                                {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                        </div>
                        <p className="text-xs text-gray-700 mt-1">Must be at least 8 characters</p>
                    </div>

                    {/* Role info (non-editable) */}
                    <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-blue-500/5 border border-blue-500/20">
                        <Shield className="w-4 h-4 text-blue-400 flex-shrink-0" />
                        <p className="text-xs text-gray-400">
                            Role: <span className="text-blue-400 font-semibold">Enterprise Staff</span> — assigned automatically
                        </p>
                    </div>

                    {/* Submit */}
                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full py-2.5 bg-blue-500 hover:bg-blue-600 disabled:bg-blue-900 disabled:cursor-not-allowed text-white text-sm font-bold rounded-lg transition-all flex items-center justify-center gap-2"
                    >
                        {loading
                            ? <><Loader className="w-4 h-4 animate-spin" /> Creating…</>
                            : <><UserPlus className="w-4 h-4" /> Create Staff Account</>
                        }
                    </button>
                </form>
            </div>
        </div>
    );
};

export default EnterpriseDashboard;
