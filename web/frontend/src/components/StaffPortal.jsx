// src/components/StaffPortal.jsx
// ─── Staff Portal — Enterprise Staff only ────────────────────────────────────
// Displays class cards and provides navigation to the Add Students page.

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Building2, GraduationCap, Edit3, Trash2,
    Loader, AlertCircle, Users, X, Shield
} from 'lucide-react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const StaffPortal = () => {
    const role = localStorage.getItem('role') || '';
    const username = localStorage.getItem('username') || 'Staff';
    const navigate = useNavigate();

    const [classes, setClasses] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [deleteTarget, setDeleteTarget] = useState(null); // class_name to confirm delete
    const [deleting, setDeleting] = useState(false);

    // Guard: only enterprise_staff can see this
    if (role !== 'enterprise_staff') {
        return (
            <div className="min-h-[60vh] flex items-center justify-center">
                <div className="text-center space-y-4">
                    <div className="w-16 h-16 rounded-2xl bg-red-500/15 border border-red-500/30 flex items-center justify-center mx-auto">
                        <Shield className="w-8 h-8 text-red-500" />
                    </div>
                    <h2 className="text-2xl font-bold text-white">Access Denied</h2>
                    <p className="text-gray-500 text-sm max-w-md">
                        You don't have permission to access the Staff Portal.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <StaffPortalContent
            username={username}
            classes={classes}
            setClasses={setClasses}
            loading={loading}
            setLoading={setLoading}
            error={error}
            setError={setError}
            deleteTarget={deleteTarget}
            setDeleteTarget={setDeleteTarget}
            deleting={deleting}
            setDeleting={setDeleting}
            navigate={navigate}
        />
    );
};


// ─── Inner component (avoids hooks-after-return issue) ───────────────────────
const StaffPortalContent = ({
    username, classes, setClasses, loading, setLoading,
    error, setError, deleteTarget, setDeleteTarget,
    deleting, setDeleting, navigate
}) => {

    // Fetch all classes for this staff user
    const fetchClasses = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE}/api/enterprise/students/classes`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.detail || 'Failed to fetch classes.');
            }
            const data = await res.json();
            setClasses(data.classes || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [setClasses, setLoading, setError]);

    useEffect(() => { fetchClasses(); }, [fetchClasses]);

    // Delete a class
    const handleDelete = async () => {
        if (!deleteTarget) return;
        setDeleting(true);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(
                `${API_BASE}/api/enterprise/students/class/${encodeURIComponent(deleteTarget)}`,
                {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${token}` },
                }
            );
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.detail || 'Failed to delete class.');
            }
            setDeleteTarget(null);
            fetchClasses();
        } catch (err) {
            setError(err.message);
            setDeleteTarget(null);
        } finally {
            setDeleting(false);
        }
    };

    return (
        <div className="max-w-5xl mx-auto px-6 py-8">
            <style>{`
                @keyframes fadeUp {
                    from { opacity: 0; transform: translateY(16px); }
                    to   { opacity: 1; transform: translateY(0); }
                }
                .fade-in   { animation: fadeUp 0.4s ease both; }
                .fade-in-d { animation: fadeUp 0.4s ease 0.1s both; }
            `}</style>

            {/* Header */}
            <div className="flex items-center justify-between mb-8 fade-in">
                <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-2xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
                        <Building2 className="w-7 h-7 text-blue-400" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white">Staff Portal</h1>
                        <p className="text-gray-500 text-sm">
                            Welcome, <span className="text-blue-400 font-semibold">{username}</span> — manage your classes and students
                        </p>
                    </div>
                </div>
            </div>

            {/* Action Button */}
            <div className="mb-8 fade-in-d">
                <button
                    onClick={() => navigate('/enterprise/portal/add-students')}
                    className="flex items-center gap-2.5 px-5 py-3 rounded-xl text-sm font-bold text-white bg-blue-500 hover:bg-blue-600 transition-all shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40"
                >
                    <GraduationCap className="w-5 h-5" />
                    👨‍🎓 Add Students
                </button>
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
            {!loading && !error && classes.length === 0 && (
                <div className="text-center py-20 fade-in">
                    <div className="w-16 h-16 rounded-2xl bg-gray-800/50 border border-gray-800 flex items-center justify-center mx-auto mb-4">
                        <Users className="w-8 h-8 text-gray-600" />
                    </div>
                    <h3 className="text-lg font-semibold text-gray-400 mb-1">No classes yet</h3>
                    <p className="text-gray-600 text-sm">
                        Click "Add Students" to create your first class.
                    </p>
                </div>
            )}

            {/* Class Cards */}
            {!loading && classes.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 fade-in-d">
                    {classes.map((cls) => (
                        <div
                            key={cls.class_name}
                            className="rounded-xl border border-gray-900 bg-gray-950/60 p-5 flex items-center justify-between hover:border-gray-800 transition-colors group"
                        >
                            {/* Left — class info */}
                            <div className="flex items-center gap-3 min-w-0">
                                <div className="w-10 h-10 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center flex-shrink-0">
                                    <GraduationCap className="w-5 h-5 text-blue-400" />
                                </div>
                                <div className="min-w-0">
                                    <p className="text-sm font-semibold text-white truncate">{cls.class_name}</p>
                                    <p className="text-xs text-gray-500">
                                        {cls.student_count} student{cls.student_count !== 1 ? 's' : ''}
                                    </p>
                                </div>
                            </div>

                            {/* Right — actions */}
                            <div className="flex items-center gap-1.5 flex-shrink-0 ml-3">
                                <button
                                    onClick={() => navigate(`/enterprise/portal/add-students?edit=${encodeURIComponent(cls.class_name)}`)}
                                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-blue-400 hover:bg-blue-500/10 border border-transparent hover:border-blue-500/30 transition-all"
                                    title="Edit class"
                                >
                                    <Edit3 className="w-3.5 h-3.5" />
                                    Edit
                                </button>
                                <button
                                    onClick={() => setDeleteTarget(cls.class_name)}
                                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/30 transition-all"
                                    title="Delete class"
                                >
                                    <Trash2 className="w-3.5 h-3.5" />
                                    Delete
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Delete Confirmation Modal */}
            {deleteTarget && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="w-full max-w-sm rounded-xl border border-gray-800 bg-gray-950 p-6 shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-lg bg-red-500/15 border border-red-500/30 flex items-center justify-center">
                                <Trash2 className="w-5 h-5 text-red-400" />
                            </div>
                            <div>
                                <h3 className="text-sm font-bold text-white">Delete Class</h3>
                                <p className="text-xs text-gray-500">This action cannot be undone</p>
                            </div>
                        </div>

                        <p className="text-sm text-gray-400 mb-6">
                            Are you sure you want to delete <span className="text-white font-semibold">"{deleteTarget}"</span> and all its students?
                        </p>

                        <div className="flex items-center gap-2 justify-end">
                            <button
                                onClick={() => setDeleteTarget(null)}
                                disabled={deleting}
                                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs text-gray-400 hover:text-white hover:bg-gray-800 border border-gray-800 transition-all"
                            >
                                <X className="w-3.5 h-3.5" />
                                Cancel
                            </button>
                            <button
                                onClick={handleDelete}
                                disabled={deleting}
                                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs text-white bg-red-500 hover:bg-red-600 disabled:bg-red-900 disabled:cursor-not-allowed transition-all"
                            >
                                {deleting
                                    ? <><Loader className="w-3.5 h-3.5 animate-spin" /> Deleting…</>
                                    : <><Trash2 className="w-3.5 h-3.5" /> Delete Class</>
                                }
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default StaffPortal;
