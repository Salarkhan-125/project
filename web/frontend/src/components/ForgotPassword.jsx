import React, { useState } from 'react';
import { Shield, Mail, Loader, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react';

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

// ─── Forgot Password Page ─────────────────────────────────────────────────────
const ForgotPassword = () => {
    const [email, setEmail] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [submitted, setSubmitted] = useState(false);   // true = success screen

    // ── Submit ──
    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!email.trim()) {
            setError('Please enter your email address.');
            return;
        }

        // Basic email format check
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email.trim())) {
            setError('Please enter a valid email address.');
            return;
        }

        try {
            setLoading(true);
            setError(null);

            const response = await fetch(`${API_BASE}/api/auth/forgot-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email.trim() }),
            });

            // We show the success screen regardless of whether the email exists
            // in the database. This is a security best practice — it prevents
            // attackers from knowing which emails are registered.
            if (!response.ok) {
                const body = await response.json().catch(() => ({}));
                // Only surface a real error for server-side failures (5xx),
                // not for "email not found" cases.
                if (response.status >= 500) {
                    throw new Error(body.detail || body.message || 'Something went wrong. Please try again.');
                }
            }

            setSubmitted(true);

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
                        {submitted ? 'Check your inbox' : 'Reset your password'}
                    </p>
                </div>

                {/* ── Success State ── */}
                {submitted ? (
                    <div className="rounded-2xl border border-gray-900 bg-gray-950/70 backdrop-blur px-6 py-8 text-center space-y-4 fade-up">

                        {/* Big check icon */}
                        <div className="w-14 h-14 rounded-full bg-green-500/10 border border-green-500/25 flex items-center justify-center mx-auto">
                            <CheckCircle className="w-7 h-7 text-green-500" />
                        </div>

                        <div>
                            <p className="text-white text-sm font-semibold">Email sent!</p>
                            <p className="text-gray-500 text-xs mt-2 leading-relaxed">
                                If <span className="text-orange-500">{email}</span> is linked to an account,
                                you'll receive a password reset link shortly.
                                <br /><br />
                                Please also check your spam or junk folder.
                            </p>
                        </div>

                        {/* Resend option */}
                        <button
                            type="button"
                            onClick={() => { setSubmitted(false); setError(null); }}
                            className="text-xs text-gray-600 hover:text-orange-500 transition-colors"
                        >
                            Didn't receive it? Send again
                        </button>
                    </div>

                ) : (

                    /* ── Form State ── */
                    <div className="rounded-2xl border border-gray-900 bg-gray-950/70 backdrop-blur px-6 py-7 space-y-4">

                        {/* Helper text */}
                        <p className="text-gray-500 text-xs leading-relaxed fade-up">
                            Enter the email address associated with your account and we'll send you a link to reset your password.
                        </p>

                        {/* Error banner */}
                        {error && (
                            <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/25 fade-up">
                                <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                                <p className="text-red-400 text-xs">{error}</p>
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-4">

                            {/* Email */}
                            <div className="fade-up-1">
                                <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
                                    Email
                                </label>
                                <div className="relative">
                                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                                    <input
                                        type="email"
                                        autoComplete="email"
                                        placeholder="you@example.com"
                                        value={email}
                                        onChange={e => { setEmail(e.target.value); setError(null); }}
                                        className="input-field"
                                        autoFocus
                                    />
                                </div>
                            </div>

                            {/* Submit */}
                            <div className="fade-up-2 pt-1">
                                <button type="submit" disabled={loading} className="primary-btn">
                                    {loading
                                        ? <><Loader className="w-4 h-4 animate-spin" /> Sending link…</>
                                        : 'Send Reset Link'
                                    }
                                </button>
                            </div>

                        </form>
                    </div>
                )}

                {/* Footer — back to login */}
                <div className="text-center mt-5 fade-up-3">
                    <a
                        href="/login"
                        className="inline-flex items-center gap-1.5 text-xs text-gray-600 hover:text-orange-500 transition-colors"
                    >
                        <ArrowLeft className="w-3 h-3" />
                        Back to Sign In
                    </a>
                </div>

            </div>
        </div>
    );
};

export default ForgotPassword;