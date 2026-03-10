import React, { useState } from "react";
import {
  Shield,
  Lock,
  Mail,
  Eye,
  EyeOff,
  Loader,
  AlertCircle,
  Building2,
  Skull,
  GraduationCap,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

// ─── Particle grid background ────────────────────────────────────────────────
const GridBg = () => (
  <svg
    className="absolute inset-0 w-full h-full opacity-[0.04] pointer-events-none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <defs>
      <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path
          d="M 40 0 L 0 0 0 40"
          fill="none"
          stroke="#ff7300"
          strokeWidth="0.5"
        />
      </pattern>
    </defs>
    <rect width="100%" height="100%" fill="url(#grid)" />
  </svg>
);

// ─── Login Page ───────────────────────────────────────────────────────────────
const Login = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // ── Portal toggle ──
  const [portal, setPortal] = useState("individual"); // 'individual' | 'enterprise'
  const [studentLogin, setStudentLogin] = useState(false);       // student ID mode

  const navigate = useNavigate();

  // ── Submit ──
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }
    try {
      setLoading(true);
      setError(null);

      let data;

      if (studentLogin) {
        // ── Student login path ──
        const response = await fetch(`${API_BASE}/api/auth/student-login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ account_id: email, password }),
        });
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || body.message || "Invalid credentials");
        }
        data = await response.json();
      } else {
        // ── Normal login path ──
        const response = await fetch(`${API_BASE}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, portal }),
        });
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || body.message || "Invalid credentials");
        }
        data = await response.json();
      }

      // Store user data in localStorage
      if (data.token) localStorage.setItem("token", data.token);
      if (data.userId) localStorage.setItem("userId", data.userId);
      if (data.username) localStorage.setItem("username", data.username);
      if (data.role) localStorage.setItem("role", data.role);

      // Student-specific data
      if (data.instance_id) localStorage.setItem("instance_id", data.instance_id);
      if (data.assignment_id) localStorage.setItem("assignment_id", data.assignment_id);
      if (data.machine_id) localStorage.setItem("machine_id", data.machine_id);

      // ── Role-based redirection using React Router (no full page reload) ──
      const redirectUrl = data.redirect_url || "/dashboard";
      if (onLoginSuccess) {
        onLoginSuccess(data);
      }
      navigate(redirectUrl);

    } catch (err) {
      setError(err.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── Switch portal and reset state ──
  const switchPortal = (type) => {
    setPortal(type);
    setStudentLogin(false);
    setError(null);
  };

  const isEnterprise = portal === "enterprise";

  return (
    <div className="min-h-screen bg-black flex items-center justify-center relative overflow-hidden">

      {/* Ambient glow — color changes per mode */}
      <div
        className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full blur-3xl opacity-10 pointer-events-none"
        style={{
          background: `radial-gradient(ellipse, ${studentLogin ? "#ef4444" : isEnterprise ? "#3b82f6" : "#ff7300"
            }, transparent 70%)`,
        }}
      />
      <GridBg />

      {/*
        ── WHY THE <style> TAG MUST STAY HERE ───────────────────────────────
        The CSS classes below (.input-field, .login-btn, .tab-btn) use
        dynamic JavaScript values — isEnterprise and studentLogin state —
        to switch colors at runtime (e.g. orange vs blue vs red).

        These CANNOT be moved to a global CSS file (index.css) because
        static CSS files cannot read React state.

        This is the correct and intentional pattern. Do NOT remove this block.
        ─────────────────────────────────────────────────────────────────────
      */}
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
        .input-field:focus {
          border-color: ${studentLogin ? "#ef4444" : isEnterprise ? "#3b82f6" : "#ff7300"};
        }

        .login-btn {
          width: 100%;
          padding: 0.7rem;
          background: ${studentLogin ? "#ef4444" : isEnterprise ? "#3b82f6" : "#ff7300"};
          color: #fff;
          font-size: 0.875rem;
          font-weight: 700;
          border: none;
          border-radius: 0.625rem;
          cursor: pointer;
          transition: background 0.2s, transform 0.1s;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.5rem;
        }
        .login-btn:hover:not(:disabled) {
          background: ${studentLogin ? "#dc2626" : isEnterprise ? "#2563eb" : "#e66a00"};
        }
        .login-btn:active:not(:disabled) { transform: scale(0.98); }
        .login-btn:disabled {
          background: ${studentLogin ? "#5a1a1a" : isEnterprise ? "#1e3a5f" : "#4a3000"};
          cursor: not-allowed;
        }

        .tab-btn {
          flex: 1;
          padding: 0.6rem 0.5rem;
          font-size: 0.75rem;
          font-weight: 600;
          border: 1px solid transparent;
          border-radius: 0.5rem;
          cursor: pointer;
          transition: all 0.25s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.4rem;
          background: transparent;
          color: #555;
        }
        .tab-btn:hover { color: #999; background: #111; }
        .tab-btn.active-individual {
          background: rgba(255, 115, 0, 0.1);
          color: #ff7300;
          border-color: rgba(255, 115, 0, 0.3);
        }
        .tab-btn.active-enterprise {
          background: rgba(59, 130, 246, 0.1);
          color: #3b82f6;
          border-color: rgba(59, 130, 246, 0.3);
        }
      `}</style>

      {/* Card */}
      <div className="relative z-10 w-full max-w-sm mx-4">

        {/* Logo / Brand */}
        <div className="text-center mb-6 fade-up">
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{
              background: isEnterprise
                ? "rgba(59, 130, 246, 0.12)"
                : "rgba(255, 115, 0, 0.12)",
              border: `1px solid ${isEnterprise
                  ? "rgba(59, 130, 246, 0.3)"
                  : "rgba(255, 115, 0, 0.3)"
                }`,
            }}
          >
            <Shield
              className="w-7 h-7"
              style={{ color: isEnterprise ? "#3b82f6" : "#ff7300" }}
            />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            ctfWithAi
          </h1>
          <p className="text-gray-600 text-sm mt-1">
            {studentLogin
              ? "Student sign in"
              : isEnterprise
                ? "Enterprise sign in"
                : "Sign in to your account"}
          </p>
        </div>

        {/* ── Portal Type Tabs ── */}
        <div className="flex gap-2 mb-4 fade-up">
          <button
            type="button"
            onClick={() => switchPortal("individual")}
            className={`tab-btn ${portal === "individual" ? "active-individual" : ""
              }`}
          >
            <Skull className="w-3.5 h-3.5" />
            Join as Hacker
          </button>
          <button
            type="button"
            onClick={() => switchPortal("enterprise")}
            className={`tab-btn ${portal === "enterprise" ? "active-enterprise" : ""
              }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            ctfWithAi for Business
          </button>
        </div>

        {/* ── Student Login Toggle — only visible on enterprise portal ── */}
        {isEnterprise && (
          <div className="mb-4 fade-up">
            <button
              type="button"
              onClick={() => {
                setStudentLogin((v) => !v);
                setError(null);
              }}
              className={`w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs font-semibold border transition-all ${studentLogin
                  ? "bg-red-500/10 text-red-400 border-red-500/30"
                  : "bg-gray-900/50 text-gray-500 border-gray-800 hover:border-gray-700 hover:text-gray-400"
                }`}
            >
              <GraduationCap className="w-3.5 h-3.5" />
              {studentLogin
                ? "← Back to Staff / Admin Login"
                : "Sign in with Student ID"}
            </button>
          </div>
        )}

        {/* Form card */}
        <div className="rounded-2xl border border-gray-900 bg-gray-950/70 backdrop-blur px-6 py-7 space-y-4">

          {/* Error banner */}
          {error && (
            <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/25 fade-up">
              <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
              <p className="text-red-400 text-xs">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">

            {/* Email / Student ID */}
            <div className="fade-up-1">
              <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
                {studentLogin ? "Student ID" : "Email"}
              </label>
              <div className="relative">
                {studentLogin ? (
                  <GraduationCap className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                ) : (
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                )}
                <input
                  type={studentLogin ? "text" : "email"}
                  autoComplete={studentLogin ? "username" : "email"}
                  placeholder={
                    studentLogin
                      ? "Enter your roll number"
                      : isEnterprise
                        ? "admin@company.com"
                        : "you@example.com"
                  }
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setError(null);
                  }}
                  className="input-field"
                />
              </div>
            </div>

            {/* Password */}
            <div className="fade-up-2">
              <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
                <input
                  type={showPwd ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setError(null);
                  }}
                  className="input-field"
                  style={{ paddingRight: "2.5rem" }}
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 transition-colors"
                >
                  {showPwd ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Submit */}
            <div className="fade-up-3 pt-1">
              <button type="submit" disabled={loading} className="login-btn">
                {loading ? (
                  <>
                    <Loader className="w-4 h-4 animate-spin" /> Signing in…
                  </>
                ) : (
                  "Sign In"
                )}
              </button>
            </div>

          </form>
        </div>

        {/* Footer links */}
        <div className="text-center mt-5 fade-up-4">
          {portal === "individual" ? (
            <>
              <a
                href="/forgot-password"
                className="text-xs text-gray-600 hover:text-orange-500 transition-colors"
              >
                Forgot password?
              </a>
              <span className="text-gray-800 mx-2">·</span>
              <a
                href="/register"
                className="text-xs text-gray-600 hover:text-orange-500 transition-colors"
              >
                Create account
              </a>
            </>
          ) : (
            <div className="mt-1 px-4 py-2.5 rounded-lg border border-gray-900 bg-gray-950/50">
              <p className="text-xs text-gray-600 leading-relaxed">
                <span className="text-blue-400 font-semibold">
                  Enterprise user?
                </span>{" "}
                Please contact your organization administrator for credentials
                or password resets.
              </p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
};

export default Login;