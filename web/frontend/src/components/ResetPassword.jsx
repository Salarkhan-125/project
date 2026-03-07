import React, { useState, useEffect } from 'react';
import { Shield, Lock, Eye, EyeOff, Loader, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react';

// ─── Your FastAPI backend URL ─────────────────────────────────────────────────
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ─── Particle grid background ────────────────────────────────────────────────
const GridBg = () => (
    <svg className="absolute inset-0 w-full h-full opacity-[0.04] pointer-events-none" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#ff7300" strokeWidth="0.5" />
            </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
    </svg>
);

// ─── Reset Password Page ──────────────────────────────────────────────────────
// This page is opened from the link inside the reset email.
// The link should look like:  https://yourdomain.com/reset-password?token=<TOKEN>
// ─────────────────────────────────────────────────────────────────────────────
const ResetPassword = () => {
    const [password, setPassword] = useState('');
    const [confirmPwd, setConfirmPwd] = useState('');
    const [showPwd, setShowPwd] = useState(false);
    const [showConfirm, setShowConfirm] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);
    const [tokenMissing, setTokenMissing] = useState(false);

    // ── Read token from URL query param on mount ──
    const token = new URLSearchParams(window.location.search).get('token');

    useEffect(() => {
        if (!token) {
            setTokenMissing(true);
        }
    }, [token]);

    // ── Password strength helper ──
    const getStrength = (pwd) => {
        if (pwd.length === 0) return null;
        if (pwd.length < 6) return { label: 'Too short', color: '#ef4444', width: '25%' };
        if (pwd.length < 10) return { label: 'Fair', color: '#f97316', width: '55%' };
        if (!/[A-Z]/.test(pwd) || !/[0-9]/.test(pwd))
            return { label: 'Good', color: '#eab308', width: '75%' };
        return { label: 'Strong', color: '#22c55e', width: '100%' };
    };
    const strength = getStrength(password);

    // ── Submit ──
    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!password.trim() || !confirmPwd.trim()) {
            setError('Please fill in both fields.');
            return;
        }
        if (password.length < 4) {
            setError('Password must be at least 4 characters.');
            return;
        }
        if (password !== confirmPwd) {
            setError('Passwords do not match.');
            return;
        }

        try {
            setLoading(true);
            setError(null);

            const response = await fetch(`${API_BASE}/api/auth/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, new_password: password }),
            });

            if (!response.ok) {
                const body = await response.json().catch(() => ({}));
                throw new Error(body.detail || body.message || 'Reset failed. The link may have expired.');
            }

            setSuccess(true);

            // Redirect to login after 2.5 seconds
            setTimeout(() => {
                window.location.href = '/login';
            }, 2500);

        } catch (err) {
            setError(err.message || 'Something went wrong. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-black flex items-center justify-center relative overflow-hidden">

            {/* Ambient glow */}
            <div
                className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full blur-3xl opacity-10 pointer-events-none"
                style={{ background: 'radial-gradient(ellipse, #ff7300, transparent 70%)' }}
            />
            <GridBg />

            <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .fade-up   { animation: fadeUp 0.45s ease both; }
        .fade-up-1 { animation: fadeUp 0.45s ease 0.05s both; }
        .fade-up-2 { animation: fadeUp 0.45s ease 0.10s both; }
        .fade-up-3 { animation: fadeUp 0.45s ease 0.15s both; }
        .fade-up-4 { animation: fadeUp 0.45s ease 0.20s both; }

        .input-field {
          width: 100%;
          padding: 0.65rem 0.875rem 0.65rem 2.5rem;
          background: #0a0a0a;
          border: 1px solid #1f1f1f;
          border-radius: 0.625rem;
          color: #fff;
          font-size: 0.875rem;
          outline: none;
          transition: border-color 0.2s;
        }
        .input-field::placeholder { color: #3f3f3f; }
        .input-field:focus { border-color: #ff7300; }

        .primary-btn {
          width: 100%;
          padding: 0.7rem;
          background: #ff7300;
          color: #fff;
          font-size: 0.875rem;
          font-weight: 700;
          border: none;
          border-radius: 0.625rem;
          cursor: pointer;
          transition: background 0.2s, transform 0.1s;
          display: flex; align-items: center; justify-content: center; gap: 0.5rem;
        }
        .primary-btn:hover:not(:disabled) { background: #e66a00; }
        .primary-btn:active:not(:disabled) { transform: scale(0.98); }
        .primary-btn:disabled { background: #4a3000; cursor: not-allowed; }

        .strength-bar-track {
          height: 3px;
          background: #1f1f1f;
          border-radius: 9999px;
          margin-top: 6px;
          overflow: hidden;
        }
        .strength-bar-fill {
          height: 100%;
          border-radius: 9999px;
          transition: width 0.3s ease, background-color 0.3s ease;
        }
      `}</style>

            {/* Card */}
            <div className="relative z-10 w-full max-w-sm mx-4">

                {/* Logo / Brand */}
                <div className="text-center mb-8 fade-up">
                    <div className="w-14 h-14 rounded-2xl bg-orange-500/15 border border-orange-500/30 flex items-center justify-center mx-auto mb-4">
                        <Shield className="w-7 h-7 text-orange-500" />
                    </div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">HackForge</h1>
                    <p className="text-gray-600 text-sm mt-1">
                        {success ? 'Password updated!' : 'Set a new password'}
                    </p>
                </div>

                {/* ── Invalid / missing token state ── */}
                {tokenMissing ? (
                    <div className="rounded-2xl border border-gray-900 bg-gray-950/70 backdrop-blur px-6 py-8 text-center space-y-4 fade-up">
                        <div className="w-14 h-14 rounded-full bg-red-500/10 border border-red-500/25 flex items-center justify-center mx-auto">
                            <AlertCircle className="w-7 h-7 text-red-500" />
                        </div>
                        <div>
                            <p className="text-white text-sm font-semibold">Invalid or expired link</p>
                            <p className="text-gray-500 text-xs mt-2 leading-relaxed">
                                This password reset link is missing or has expired. Please request a new one.
                            </p>
                        </div>
                        <a
                            href="/forgot-password"
                            className="inline-block text-xs text-orange-500 hover:text-orange-400 transition-colors font-semibold"
                        >
                            Request a new link →
                        </a>
                    </div>

                ) : success ? (

                    /* ── Success state ── */
                    <div className="rounded-2xl border border-gray-900 bg-gray-950/70 backdrop-blur px-6 py-8 text-center space-y-4 fade-up">
                        <div className="w-14 h-14 rounded-full bg-green-500/10 border border-green-500/25 flex items-center justify-center mx-auto">
                            <CheckCircle className="w-7 h-7 text-green-500" />
                        </div>
                        <div>
                            <p className="text-white text-sm font-semibold">Password changed!</p>
                            <p className="text-gray-500 text-xs mt-2 leading-relaxed">
                                Your password has been updated successfully.<br />
                                Redirecting you to sign in…
                            </p>
                        </div>
                    </div>

                ) : (

                    /* ── Form state ── */
                    <div className="rounded-2xl border border-gray-900 bg-gray-950/70 backdrop-blur px-6 py-7 space-y-4">

                        {/* Error banner */}
                        {error && (
                            <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/25 fade-up">
                                <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                                <p className="text-red-400 text-xs">{error}</p>
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-4">

                            {/* New Password */}
                            <div className="fade-up-1">
                                <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
                                    New Password
                                </label>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                                    <input
                                        type={showPwd ? 'text' : 'password'}
                                        autoComplete="new-password"
                                        placeholder="••••••••"
                                        value={password}
                                        onChange={e => { setPassword(e.target.value); setError(null); }}
                                        className="input-field"
                                        style={{ paddingRight: '2.5rem' }}
                                        autoFocus
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPwd(v => !v)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 transition-colors"
                                    >
                                        {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>

                                {/* Strength bar */}
                                {strength && (
                                    <div className="mt-2">
                                        <div className="strength-bar-track">
                                            <div
                                                className="strength-bar-fill"
                                                style={{ width: strength.width, backgroundColor: strength.color }}
                                            />
                                        </div>
                                        <p className="text-xs mt-1" style={{ color: strength.color }}>
                                            {strength.label}
                                        </p>
                                    </div>
                                )}
                            </div>

                            {/* Confirm Password */}
                            <div className="fade-up-2">
                                <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
                                    Confirm Password
                                </label>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                                    <input
                                        type={showConfirm ? 'text' : 'password'}
                                        autoComplete="new-password"
                                        placeholder="••••••••"
                                        value={confirmPwd}
                                        onChange={e => { setConfirmPwd(e.target.value); setError(null); }}
                                        className="input-field"
                                        style={{ paddingRight: '2.5rem' }}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowConfirm(v => !v)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 transition-colors"
                                    >
                                        {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>

                                {/* Match indicator */}
                                {confirmPwd.length > 0 && (
                                    <p className="text-xs mt-1.5" style={{ color: password === confirmPwd ? '#22c55e' : '#ef4444' }}>
                                        {password === confirmPwd ? '✓ Passwords match' : '✗ Passwords do not match'}
                                    </p>
                                )}
                            </div>

                            {/* Submit */}
                            <div className="fade-up-3 pt-1">
                                <button type="submit" disabled={loading} className="primary-btn">
                                    {loading
                                        ? <><Loader className="w-4 h-4 animate-spin" /> Updating password…</>
                                        : 'Set New Password'
                                    }
                                </button>
                            </div>

                        </form>
                    </div>
                )}

                {/* Footer */}
                {!success && !tokenMissing && (
                    <div className="text-center mt-5 fade-up-4">
                        <a
                            href="/login"
                            className="inline-flex items-center gap-1.5 text-xs text-gray-600 hover:text-orange-500 transition-colors"
                        >
                            <ArrowLeft className="w-3 h-3" />
                            Back to Sign In
                        </a>
                    </div>
                )}

            </div>
        </div>
    );
};

export default ResetPassword;