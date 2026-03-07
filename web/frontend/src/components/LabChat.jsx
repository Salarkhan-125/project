// src/components/LabChat.jsx
import React, { useState, useRef, useEffect, useCallback } from "react";
import { Send, ExternalLink, Loader2, CheckCircle, XCircle, Clock, Zap, Shield, Terminal } from "lucide-react";
import hackforgeLogo from "../assets/logo.png";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";
const POLL_INTERVAL_MS = 5000;
const randomId = () => Math.random().toString(36).slice(2, 10);
const TS = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

const SpinLogo = ({ spin = false, size = 32 }) => (
  <img
    src={hackforgeLogo}
    alt="VulnAI"
    width={size}
    height={size}
    className={`object-contain flex-shrink-0 ${spin ? "animate-spin" : ""}`}
    style={spin ? { animationDuration: "1s" } : {}}
  />
);

const StatusBadge = ({ status }) => {
  const cfg = {
    pending:    { Icon: Clock,       cls: "text-amber-400   bg-amber-400/10   border-amber-400/30",   label: "Queued"   },
    generating: { Icon: Loader2,     cls: "text-sky-400     bg-sky-400/10     border-sky-400/30",     label: "Building" },
    done:       { Icon: CheckCircle, cls: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30", label: "Ready"    },
    failed:     { Icon: XCircle,     cls: "text-red-400     bg-red-400/10     border-red-400/30",     label: "Failed"   },
  }[status] || { Icon: Clock, cls: "text-amber-400 bg-amber-400/10 border-amber-400/30", label: "Queued" };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold tracking-wide border ${cfg.cls}`}>
      <cfg.Icon className={`w-3 h-3 ${status === "generating" ? "animate-spin" : ""}`} />
      {cfg.label}
    </span>
  );
};

const JobCard = ({ job }) => (
  <div className="mt-2 rounded-lg border border-orange-500/20 bg-[#0d0d0d] p-3 space-y-2 font-mono text-xs">
    <div className="flex items-center justify-between">
      <span className="text-gray-500">JOB <span className="text-orange-400">{job.id?.slice(0, 12)}</span></span>
      <StatusBadge status={job.status} />
    </div>
    {job.status === "done" && job.url && (
      <a href={job.url} target="_blank" rel="noopener noreferrer"
        className="flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 transition-colors">
        <ExternalLink className="w-3.5 h-3.5" />{job.url}
      </a>
    )}
    {job.status === "failed" && job.error && <p className="text-red-400">{job.error}</p>}
  </div>
);

const SUGGESTIONS = [
  { label: "CVE-2021-44228", sub: "Log4Shell RCE"   },
  { label: "CVE-2022-22965", sub: "Spring4Shell"    },
  { label: "SQL Injection",  sub: "MySQL target"    },
  { label: "SSRF Attack",    sub: "Internal pivot"  },
];

const WelcomeScreen = ({ onSuggest }) => (
  <div className="flex flex-col items-center justify-center h-full pb-16 px-6 select-none">
    <div className="mb-6">
      <img src={hackforgeLogo} alt="VulnAI" className="w-16 h-16 object-contain" />
    </div>
    <h1 className="text-2xl font-bold text-white mb-1 tracking-tight">Vuln AI</h1>
    <p className="text-gray-500 text-sm mb-8 text-center max-w-xs leading-relaxed">
      Describe a CVE or vulnerability type and I'll spin up a live lab for you.
    </p>
    <div className="flex flex-wrap gap-2 justify-center mb-8">
      {[
        { icon: Terminal, text: "Real Docker Labs" },
        { icon: Shield,   text: "CVE Database"    },
        { icon: Zap,      text: "Instant Deploy"  },
      ].map(({ icon: Icon, text }) => (
        <div key={text} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-900 border border-gray-800 text-xs text-gray-400">
          <Icon className="w-3.5 h-3.5 text-orange-500" />{text}
        </div>
      ))}
    </div>
    <p className="text-[11px] text-gray-600 uppercase tracking-widest mb-3">Try asking about</p>
    <div className="grid grid-cols-2 gap-2 w-full max-w-sm">
      {SUGGESTIONS.map(s => (
        <button key={s.label} onClick={() => onSuggest(s.label)}
          className="text-left px-3 py-2.5 rounded-xl bg-gray-900/60 border border-gray-800 hover:border-orange-500/40 hover:bg-orange-500/5 transition-all group">
          <p className="text-sm text-gray-200 font-medium group-hover:text-orange-400 transition-colors">{s.label}</p>
          <p className="text-[11px] text-gray-600 mt-0.5">{s.sub}</p>
        </button>
      ))}
    </div>
  </div>
);

const Message = ({ msg, jobMap }) => {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 group ${isUser ? "flex-row-reverse" : "flex-row"}`}
      style={{ animation: "msgIn 0.2s ease both" }}>
      {!isUser && <div className="flex-shrink-0 mt-0.5"><SpinLogo size={26} /></div>}
      <div className={`flex flex-col gap-1 max-w-[75%] ${isUser ? "items-end" : "items-start"}`}>
        {!isUser && <span className="text-[11px] text-orange-500 font-semibold tracking-wide px-1">VULN AI</span>}
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-orange-500 text-white rounded-tr-sm shadow-lg shadow-orange-500/20"
            : "bg-[#111] border border-gray-800/80 text-gray-100 rounded-tl-sm"
        }`}>
          {msg.text}
        </div>
        {msg.jobId && jobMap[msg.jobId] && <JobCard job={jobMap[msg.jobId]} />}
        <span className="text-[10px] text-gray-700 px-1 opacity-0 group-hover:opacity-100 transition-opacity">{msg.ts}</span>
      </div>
    </div>
  );
};

const TypingIndicator = () => (
  <div className="flex gap-3 items-start" style={{ animation: "msgIn 0.2s ease both" }}>
    <div className="flex-shrink-0 mt-0.5"><SpinLogo spin size={26} /></div>
    <div className="bg-[#111] border border-gray-800/80 rounded-2xl rounded-tl-sm px-4 py-3">
      <div className="flex gap-1 items-center h-4">
        {[0, 1, 2].map(i => (
          <span key={i} className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-bounce"
            style={{ animationDelay: `${i * 120}ms`, animationDuration: "0.8s" }} />
        ))}
      </div>
    </div>
  </div>
);

export default function LabChat() {
  const sessionId   = useRef(localStorage.getItem("userId") || "session_" + randomId());
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [jobMap, setJobMap]     = useState({});
  const pollingRef  = useRef({});
  const bottomRef   = useRef(null);
  const textareaRef = useRef(null);

  const hasUserMessage = messages.some(m => m.role === "user");

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  const pollJob = useCallback((jobId) => {
    if (pollingRef.current[jobId]) return;
    const tick = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/lab/status/${jobId}`, {
          headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        setJobMap(prev => ({ ...prev, [jobId]: data }));
        if (data.status === "done" || data.status === "failed") {
          clearInterval(pollingRef.current[jobId]);
          delete pollingRef.current[jobId];
          const note = data.status === "done"
            ? `✅ Lab is live! Access it at: ${data.url || `http://${process.env.REACT_APP_SERVER_HOST || "localhost"}:${data.port}`}`
            : `❌ Lab failed: ${data.error || "unknown error"}`;
          setMessages(prev => [...prev, { id: randomId(), role: "assistant", ts: TS(), text: note, jobId }]);
        }
      } catch (_) {}
    };
    tick();
    pollingRef.current[jobId] = setInterval(tick, POLL_INTERVAL_MS);
  }, []);

  useEffect(() => {
    const refs = pollingRef.current;
    return () => Object.values(refs).forEach(clearInterval);
  }, []);

  const sendMessage = async (override) => {
    const text = (override !== undefined ? override : input).trim();
    if (!text || loading) return;
    setMessages(prev => [...prev, { id: randomId(), role: "user", ts: TS(), text }]);
    setInput("");
    setLoading(true);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    try {
      const res = await fetch(`${API_BASE}/api/lab/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token") || ""}`,
        },
        body: JSON.stringify({ message: text, session_id: sessionId.current }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setMessages(prev => [...prev, {
        id: randomId(), role: "assistant", ts: TS(),
        text: data.response || "…", jobId: data.job_id || null,
      }]);
      if (data.job_id) {
        setJobMap(prev => ({ ...prev, [data.job_id]: { id: data.job_id, status: "pending" } }));
        pollJob(data.job_id);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: randomId(), role: "assistant", ts: TS(),
        text: `⚠️ ${err.message || "Could not reach the server."}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-73px)] bg-[#080808]">
      <style>{`
        @keyframes msgIn {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>



      {/* messages / welcome */}
      <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "#222 transparent" }}>
        {!hasUserMessage ? (
          <WelcomeScreen onSuggest={(txt) => sendMessage(txt)} />
        ) : (
          <div className="max-w-3xl mx-auto px-5 py-6 space-y-5">
            {messages.map(msg => <Message key={msg.id} msg={msg} jobMap={jobMap} />)}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* input */}
      <div className="border-t border-gray-900/80 bg-black/40 backdrop-blur-sm px-5 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex gap-2 items-end bg-[#111] border border-gray-800 focus-within:border-orange-500/50 rounded-2xl px-4 py-3 transition-colors shadow-xl shadow-black/40">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about a CVE or describe a vulnerability…"
              rows={1}
              disabled={loading}
              className="flex-1 resize-none bg-transparent text-sm text-gray-100 placeholder-gray-600 outline-none disabled:opacity-40 leading-relaxed"
              style={{ maxHeight: "100px", overflowY: "auto" }}
              onInput={e => {
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 100) + "px";
              }}
            />
            <button onClick={() => sendMessage()}
              disabled={loading || !input.trim()}
              className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all disabled:opacity-30 disabled:cursor-not-allowed bg-orange-500 hover:bg-orange-400 shadow-lg shadow-orange-500/30">
              {loading ? <Loader2 className="w-4 h-4 text-white animate-spin" /> : <Send className="w-4 h-4 text-white" />}
            </button>
          </div>
          <p className="text-[10px] text-gray-700 mt-2 text-center tracking-wide">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}
