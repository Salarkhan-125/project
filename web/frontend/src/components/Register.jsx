import React, { useState, useRef, useEffect } from 'react';
import { Shield, Lock, Mail, Eye, EyeOff, Loader, AlertCircle, User, CheckCircle } from 'lucide-react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

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

// ─── 4-box OTP input ──────────────────────────────────────────────────────────
const OTPInput = ({ value, onChange, disabled }) => {
    const inputRefs = [useRef(), useRef(), useRef(), useRef()];
    const digits = (value + '    ').slice(0, 4).split('');

    const handleChange = (index, e) => {
        const char = e.target.value.replace(/\D/g, '').slice(-1);
        const newDigits = [...digits.map(d => d.trim())];
        newDigits[index] = char;
        onChange(newDigits.join(''));
        if (char && index < 3) inputRefs[index + 1].current?.focus();
    };

    const handleKeyDown = (index, e) => {
        if (e.key === 'Backspace' && !digits[index].trim() && index > 0) {
            inputRefs[index - 1].current?.focus();
        }
    };

    const handlePaste = (e) => {
        e.preventDefault();
        const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 4);
        onChange(pasted.padEnd(4, ' ').slice(0, 4).trimEnd());
        const focusIdx = Math.min(pasted.length, 3);
        inputRefs[focusIdx].current?.focus();
    };

    return (
        <div className="flex gap-3 justify-center">
            {[0, 1, 2, 3].map(i => (
                <input
                    key={i}
                    ref={inputRefs[i]}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digits[i].trim()}
                    onChange={e => handleChange(i, e)}
                    onKeyDown={e => handleKeyDown(i, e)}
                    onPaste={handlePaste}
                    disabled={disabled}
                    style={{
                        width: '56px', height: '64px',
                        textAlign: 'center', fontSize: '1.5rem', fontWeight: '700',
                        background: '#0a0a0a',
                        border: `2px solid ${digits[i].trim() ? '#ff7300' : '#1f1f1f'}`,
                        borderRadius: '0.75rem', color: '#fff', outline: 'none',
                        transition: 'border-color 0.2s', caretColor: '#ff7300',
                    }}
                    onFocus={e => e.target.style.borderColor = '#ff7300'}
                    onBlur={e => e.target.style.borderColor = digits[i].trim() ? '#ff7300' : '#1f1f1f'}
                />
            ))}
        </div>
    );
};

// ─── Register Page ────────────────────────────────────────────────────────────
const Register = ({ onRegisterSuccess }) => {

    // Form fields
    const [username, setUsername] = useState('');
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPwd, setShowPwd] = useState(false);

    // OTP / flow
    const [step, setStep] = useState('form'); // 'form' | 'otp' | 'success'
    const [otp, setOtp] = useState('');
    const [countdown, setCountdown] = useState(300);
    const [canResend, setCanResend] = useState(false);
    const timerRef = useRef(null);

    // Shared
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Start countdown whenever we enter OTP step
    useEffect(() => {
        if (step !== 'otp') return;
        setCountdown(300);
        setCanResend(false);
        timerRef.current = setInterval(() => {
            setCountdown(prev => {
                if (prev <= 1) { clearInterval(timerRef.current); setCanResend(true); return 0; }
                return prev - 1;
            });
        }, 1000);
        return () => clearInterval(timerRef.current);
    }, [step]);

    const fmt = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

    // ── Step 1: submit form → send OTP ──
    const handleFormSubmit = async (e) => {
        e.preventDefault();
        if (!username.trim() || !fullName.trim() || !email.trim() || !password.trim()) {
            setError('Please fill in all fields.'); return;
        }
        if (password.length < 4) { setError('Password must be at least 4 characters.'); return; }

        try {
            setLoading(true); setError(null);
            const res = await fetch(`${API_BASE}/api/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: username.trim(), full_name: fullName.trim(),
                    email: email.trim(), password, role: 'individual',
                }),
            });
            if (!res.ok) {
                const b = await res.json().catch(() => ({}));
                throw new Error(b.detail || b.message || 'Registration failed');
            }
            const data = await res.json();

            // If email verification was skipped, account is already created
            if (data.verified && data.token) {
                setStep('success');
                setTimeout(() => {
                    if (onRegisterSuccess) onRegisterSuccess(data);
                    else window.location.href = '/login';
                }, 1500);
                return;
            }

            setStep('otp'); setOtp('');
        } catch (err) {
            setError(err.message || 'Registration failed. Please try again.');
        } finally { setLoading(false); }
    };

    // ── Step 2: verify OTP → create account ──
    const handleOTPSubmit = async (e) => {
        e.preventDefault();
        const cleanOtp = otp.replace(/\s/g, '');
        if (cleanOtp.length !== 4) { setError('Please enter the complete 4-digit code.'); return; }

        try {
            setLoading(true); setError(null);
            const res = await fetch(`${API_BASE}/api/auth/register/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email.trim(), otp: cleanOtp }),
            });
            if (!res.ok) {
                const b = await res.json().catch(() => ({}));
                throw new Error(b.detail || b.message || 'Verification failed');
            }
            const data = await res.json();
            setStep('success');
            clearInterval(timerRef.current);
            setTimeout(() => {
                if (onRegisterSuccess) onRegisterSuccess(data);
                else window.location.href = '/login';
            }, 2000);
        } catch (err) {
            setError(err.message || 'Verification failed. Please try again.');
            setOtp('');
        } finally { setLoading(false); }
    };

    // ── Resend OTP ──
    const handleResend = async () => {
        try {
            setLoading(true); setError(null); setOtp('');
            const res = await fetch(`${API_BASE}/api/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: username.trim(), full_name: fullName.trim(),
                    email: email.trim(), password, role: 'individual',
                }),
            });
            if (!res.ok) {
                const b = await res.json().catch(() => ({}));
                throw new Error(b.detail || 'Could not resend OTP.');
            }
            // Restart OTP step + timer
            setStep('form');
            setTimeout(() => setStep('otp'), 50);
        } catch (err) {
            setError(err.message || 'Could not resend OTP. Please try again.');
        } finally { setLoading(false); }
    };

    return (
        <div className="min-h-screen bg-black flex items-center justify-center relative overflow-hidden">
            <div
                className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full blur-3xl opacity-10 pointer-events-none"
                style={{ background: 'radial-gradient(ellipse, #ff7300, transparent 70%)' }}
            />
            <GridBg />

            <style>{`
        @keyframes fadeUp {
          from { opacity:0; transform:translateY(20px); }
          to   { opacity:1; transform:translateY(0); }
        }
        .fade-up   { animation: fadeUp 0.45s ease both; }
        .fade-up-1 { animation: fadeUp 0.45s ease 0.05s both; }
        .fade-up-2 { animation: fadeUp 0.45s ease 0.10s both; }
        .fade-up-3 { animation: fadeUp 0.45s ease 0.15s both; }
        .fade-up-4 { animation: fadeUp 0.45s ease 0.20s both; }
        .fade-up-5 { animation: fadeUp 0.45s ease 0.25s both; }
        .fade-up-6 { animation: fadeUp 0.45s ease 0.30s both; }
        .input-field {
          width:100%; padding:0.65rem 0.875rem 0.65rem 2.5rem;
          background:#0a0a0a; border:1px solid #1f1f1f; border-radius:0.625rem;
          color:#fff; font-size:0.875rem; outline:none; transition:border-color 0.2s;
        }
        .input-field::placeholder { color:#3f3f3f; }
        .input-field:focus { border-color:#ff7300; }
        .primary-btn {
          width:100%; padding:0.7rem; background:#ff7300; color:#fff;
          font-size:0.875rem; font-weight:700; border:none; border-radius:0.625rem;
          cursor:pointer; transition:background 0.2s, transform 0.1s;
          display:flex; align-items:center; justify-content:center; gap:0.5rem;
        }
        .primary-btn:hover:not(:disabled) { background:#e66a00; }
        .primary-btn:active:not(:disabled) { transform:scale(0.98); }
        .primary-btn:disabled { background:#4a3000; cursor:not-allowed; }
      `}</style>

            <div className="relative z-10 w-full max-w-sm mx-4">

                {/* Logo */}
                <div className="text-center mb-8 fade-up">
                    <div className="w-14 h-14 rounded-2xl bg-orange-500/15 border border-orange-500/30 flex items-center justify-center mx-auto mb-4">
                        <Shield className="w-7 h-7 text-orange-500" />
                    </div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">ctfWithAi</h1>
                    <p className="text-gray-600 text-sm mt-1">
                        {step === 'form' && 'Create your account'}
                        {step === 'otp' && 'Verify your email'}
                        {step === 'success' && 'Account created!'}
                    </p>
                </div>

                {/* ── SUCCESS ── */}
                {step === 'success' && (
                    <div className="rounded-2xl border border-gray-900 bg-gray-950/70 backdrop-blur px-6 py-10 text-center space-y-4 fade-up">
                        <div className="w-16 h-16 rounded-full bg-green-500/10 border border-green-500/25 flex items-center justify-center mx-auto">
                            <CheckCircle className="w-8 h-8 text-green-500" />
                        </div>
                        <div>
                            <p className="text-white font-semibold">Email verified!</p>
                            <p className="text-gray-500 text-xs mt-2 leading-relaxed">
                                Your account has been created successfully.<br />
                                Redirecting you to sign in…
                            </p>
                        </div>
                    </div>
                )}

                {/* ── OTP SCREEN ── */}
                {step === 'otp' && (
                    <div className="rounded-2xl border border-gray-900 bg-gray-950/70 backdrop-blur px-6 py-7 space-y-5 fade-up">

                        <div className="text-center">
                            <p className="text-gray-400 text-xs leading-relaxed">
                                We sent a 4-digit code to<br />
                                <span className="text-orange-500 font-semibold">{email}</span>
                            </p>
                        </div>

                        {error && (
                            <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/25">
                                <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                                <p className="text-red-400 text-xs">{error}</p>
                            </div>
                        )}

                        <form onSubmit={handleOTPSubmit} className="space-y-5">
                            <OTPInput value={otp} onChange={v => { setOtp(v); setError(null); }} disabled={loading} />

                            <p className="text-center text-xs text-gray-600">
                                {countdown > 0
                                    ? <>Code expires in <span className="text-orange-500 font-semibold">{fmt(countdown)}</span></>
                                    : <span className="text-red-400">Code expired — please resend</span>
                                }
                            </p>

                            <button
                                type="submit"
                                disabled={loading || otp.replace(/\s/g, '').length !== 4 || countdown === 0}
                                className="primary-btn"
                            >
                                {loading
                                    ? <><Loader className="w-4 h-4 animate-spin" /> Verifying…</>
                                    : 'Verify & Create Account'
                                }
                            </button>
                        </form>

                        <div className="text-center space-y-2 pt-1">
                            {canResend
                                ? <button type="button" onClick={handleResend} disabled={loading}
                                    className="text-xs text-orange-500 hover:text-orange-400 transition-colors">
                                    Resend code
                                </button>
                                : <p className="text-xs text-gray-700">Didn't receive it? Wait for the timer to resend.</p>
                            }
                            <br />
                            <button type="button"
                                onClick={() => { setStep('form'); setError(null); setOtp(''); }}
                                className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
                                ← Change details
                            </button>
                        </div>
                    </div>
                )}

                {/* ── SIGNUP FORM ── */}
                {step === 'form' && (
                    <div className="rounded-2xl border border-gray-900 bg-gray-950/70 backdrop-blur px-6 py-7 space-y-4">

                        {error && (
                            <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/25 fade-up">
                                <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                                <p className="text-red-400 text-xs">{error}</p>
                            </div>
                        )}

                        <form onSubmit={handleFormSubmit} className="space-y-4">

                            <div className="fade-up-1">
                                <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">Username</label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                                    <input type="text" autoComplete="username" placeholder="hackerman42"
                                        value={username} onChange={e => { setUsername(e.target.value); setError(null); }}
                                        className="input-field" />
                                </div>
                            </div>

                            <div className="fade-up-2">
                                <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">Full Name</label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                                    <input type="text" autoComplete="name" placeholder="John Doe"
                                        value={fullName} onChange={e => { setFullName(e.target.value); setError(null); }}
                                        className="input-field" />
                                </div>
                            </div>

                            <div className="fade-up-3">
                                <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">Email</label>
                                <div className="relative">
                                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                                    <input type="email" autoComplete="email" placeholder="you@example.com"
                                        value={email} onChange={e => { setEmail(e.target.value); setError(null); }}
                                        className="input-field" />
                                </div>
                            </div>

                            <div className="fade-up-4">
                                <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">Password</label>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                                    <input type={showPwd ? 'text' : 'password'} autoComplete="new-password" placeholder="••••••••"
                                        value={password} onChange={e => { setPassword(e.target.value); setError(null); }}
                                        className="input-field" style={{ paddingRight: '2.5rem' }} />
                                    <button type="button" onClick={() => setShowPwd(v => !v)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 transition-colors">
                                        {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                            </div>

                            <div className="fade-up-5 pt-1">
                                <button type="submit" disabled={loading} className="primary-btn">
                                    {loading
                                        ? <><Loader className="w-4 h-4 animate-spin" /> Sending code…</>
                                        : 'Sign Up'
                                    }
                                </button>
                            </div>

                        </form>
                    </div>
                )}

                {step === 'form' && (
                    <div className="text-center mt-5 fade-up-6">
                        <span className="text-xs text-gray-600">Already have an account?</span>
                        <span className="text-gray-800 mx-2">·</span>
                        <a href="/login" className="text-xs text-gray-600 hover:text-orange-500 transition-colors">Sign in</a>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Register;