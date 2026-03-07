import React, { useState, useEffect } from 'react';
import {
    Users, Edit3, Save, X, Mail, Lock, User, Eye, EyeOff,
    Loader, AlertCircle, CheckCircle, Shield, Search, RefreshCw
} from 'lucide-react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ─── Created Accounts — Enterprise Admin only ────────────────────────────────
const CreatedAccounts = () => {
    const role = localStorage.getItem('role') || '';

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
                        You don't have permission to view created accounts.
                    </p>
                </div>
            </div>
        );
    }

    return <StaffList />;
};


// ─── Staff List + Edit ───────────────────────────────────────────────────────
const StaffList = () => {
    const [staff, setStaff] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [editingId, setEditingId] = useState(null);

    const fetchStaff = async () => {
        setLoading(true);
        setError(null);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE}/api/auth/enterprise/staff`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.detail || 'Failed to fetch staff accounts.');
            }
            const data = await res.json();
            setStaff(data.staff || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchStaff(); }, []);

    const filtered = staff.filter(s => {
        const term = searchTerm.toLowerCase();
        return (
            (s.user_id || '').toLowerCase().includes(term) ||
            (s.email || '').toLowerCase().includes(term) ||
            (s.full_name || '').toLowerCase().includes(term)
        );
    });

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
            <div className="flex items-center justify-between mb-8 fade-in">
                <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-2xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
                        <Users className="w-7 h-7 text-blue-400" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white">Created Accounts</h1>
                        <p className="text-gray-500 text-sm">
                            Manage staff accounts in your organization
                        </p>
                    </div>
                </div>
                <button
                    onClick={fetchStaff}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-gray-400 hover:text-blue-400 hover:bg-blue-500/10 transition-all border border-transparent hover:border-blue-500/30"
                >
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    <span className="text-sm">Refresh</span>
                </button>
            </div>

            {/* Search */}
            <div className="relative mb-6 fade-in-d">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                <input
                    type="text"
                    placeholder="Search by name, email, or username…"
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[#3f3f3f]"
                />
            </div>

            {/* Error */}
            {error && (
                <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/25 mb-4 fade-in">
                    <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                    <p className="text-red-400 text-xs">{error}</p>
                </div>
            )}

            {/* Loading */}
            {loading && (
                <div className="flex items-center justify-center py-20">
                    <Loader className="w-6 h-6 text-blue-400 animate-spin" />
                </div>
            )}

            {/* Empty state */}
            {!loading && !error && filtered.length === 0 && (
                <div className="text-center py-20 fade-in">
                    <div className="w-16 h-16 rounded-2xl bg-gray-800/50 border border-gray-800 flex items-center justify-center mx-auto mb-4">
                        <Users className="w-8 h-8 text-gray-600" />
                    </div>
                    <h3 className="text-lg font-semibold text-gray-400 mb-1">
                        {searchTerm ? 'No matching accounts' : 'No staff accounts yet'}
                    </h3>
                    <p className="text-gray-600 text-sm">
                        {searchTerm
                            ? 'Try a different search term.'
                            : 'Create staff accounts from the Admin Dashboard.'}
                    </p>
                </div>
            )}

            {/* Staff Table */}
            {!loading && filtered.length > 0 && (
                <div className="rounded-xl border border-gray-900 bg-gray-950/60 overflow-hidden fade-in-d">
                    {/* Table Header */}
                    <div className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-gray-900 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        <div className="col-span-3">User ID</div>
                        <div className="col-span-3">Email</div>
                        <div className="col-span-2">Full Name</div>
                        <div className="col-span-2">Created</div>
                        <div className="col-span-2 text-right">Actions</div>
                    </div>

                    {/* Rows */}
                    {filtered.map(member => (
                        editingId === member.user_id ? (
                            <EditRow
                                key={member.user_id}
                                member={member}
                                onCancel={() => setEditingId(null)}
                                onSaved={() => { setEditingId(null); fetchStaff(); }}
                            />
                        ) : (
                            <div
                                key={member.user_id}
                                className="grid grid-cols-12 gap-4 px-6 py-3.5 border-b border-gray-900/50 hover:bg-gray-900/30 transition-colors items-center"
                            >
                                <div className="col-span-3 text-sm text-white font-medium truncate">
                                    {member.user_id}
                                </div>
                                <div className="col-span-3 text-sm text-gray-400 truncate">
                                    {member.email}
                                </div>
                                <div className="col-span-2 text-sm text-gray-500 truncate">
                                    {member.full_name || '—'}
                                </div>
                                <div className="col-span-2 text-xs text-gray-600">
                                    {member.created_at
                                        ? new Date(member.created_at).toLocaleDateString()
                                        : '—'}
                                </div>
                                <div className="col-span-2 flex justify-end">
                                    <button
                                        onClick={() => setEditingId(member.user_id)}
                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-blue-400 hover:bg-blue-500/10 border border-transparent hover:border-blue-500/30 transition-all"
                                    >
                                        <Edit3 className="w-3.5 h-3.5" />
                                        Edit
                                    </button>
                                </div>
                            </div>
                        )
                    ))}

                    {/* Footer */}
                    <div className="px-6 py-3 text-xs text-gray-600">
                        Showing {filtered.length} of {staff.length} account{staff.length !== 1 ? 's' : ''}
                    </div>
                </div>
            )}
        </div>
    );
};


// ─── Edit Row (inline) ───────────────────────────────────────────────────────
const EditRow = ({ member, onCancel, onSaved }) => {
    const nameParts = (member.full_name || '').split(' ');
    const [firstName, setFirstName] = useState(nameParts[0] || '');
    const [lastName, setLastName] = useState(nameParts.slice(1).join(' ') || '');
    const [email, setEmail] = useState(member.email || '');
    const [password, setPassword] = useState('');
    const [showPwd, setShowPwd] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);

    const handleSave = async () => {
        setError(null);
        setSuccess(null);

        const payload = {};
        const origFirst = nameParts[0] || '';
        const origLast = nameParts.slice(1).join(' ') || '';

        if (firstName.trim() !== origFirst || lastName.trim() !== origLast) {
            payload.first_name = firstName.trim();
            payload.last_name = lastName.trim();
        }
        if (email.trim().toLowerCase() !== (member.email || '').toLowerCase()) {
            payload.email = email.trim();
        }
        if (password.trim()) {
            payload.password = password;
        }

        if (Object.keys(payload).length === 0) {
            setError('No changes to save.');
            return;
        }

        try {
            setSaving(true);
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE}/api/auth/enterprise/staff/${member.user_id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.detail || 'Failed to update account.');
            }

            setSuccess('Account updated successfully.');
            setTimeout(() => onSaved(), 1000);
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="px-6 py-4 border-b border-gray-900/50 bg-blue-500/5">
            {/* Success / Error */}
            {success && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-500/10 border border-green-500/25 mb-3">
                    <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                    <p className="text-green-400 text-xs">{success}</p>
                </div>
            )}
            {error && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/25 mb-3">
                    <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                    <p className="text-red-400 text-xs">{error}</p>
                </div>
            )}

            <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                    <label className="block text-xs text-gray-500 mb-1">First Name</label>
                    <div className="relative">
                        <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                        <input
                            type="text"
                            value={firstName}
                            onChange={e => setFirstName(e.target.value)}
                            className="w-full pl-10 pr-3 py-2 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors"
                        />
                    </div>
                </div>
                <div>
                    <label className="block text-xs text-gray-500 mb-1">Last Name</label>
                    <input
                        type="text"
                        value={lastName}
                        onChange={e => setLastName(e.target.value)}
                        className="w-full px-3 py-2 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors"
                    />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                    <label className="block text-xs text-gray-500 mb-1">Email</label>
                    <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                        <input
                            type="email"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            className="w-full pl-10 pr-3 py-2 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors"
                        />
                    </div>
                </div>
                <div>
                    <label className="block text-xs text-gray-500 mb-1">New Password (leave blank to keep)</label>
                    <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                        <input
                            type={showPwd ? 'text' : 'password'}
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            placeholder="••••••••"
                            className="w-full pl-10 pr-10 py-2 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[#3f3f3f]"
                        />
                        <button
                            type="button"
                            onClick={() => setShowPwd(v => !v)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 transition-colors"
                        >
                            {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                    </div>
                </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 justify-end">
                <button
                    onClick={onCancel}
                    disabled={saving}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs text-gray-400 hover:text-white hover:bg-gray-800 border border-gray-800 transition-all"
                >
                    <X className="w-3.5 h-3.5" />
                    Cancel
                </button>
                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs text-white bg-blue-500 hover:bg-blue-600 disabled:bg-blue-900 disabled:cursor-not-allowed transition-all"
                >
                    {saving
                        ? <><Loader className="w-3.5 h-3.5 animate-spin" /> Saving…</>
                        : <><Save className="w-3.5 h-3.5" /> Save Changes</>
                    }
                </button>
            </div>
        </div>
    );
};

export default CreatedAccounts;
