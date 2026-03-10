// src/components/Assignments.jsx
import React, { useState, useEffect } from "react";
import {
    ClipboardList,
    Server,
    Shield,
    Users,
    Clock,
    CheckCircle,
    ChevronDown,
    ChevronUp,
    Download,
    Copy,
    Loader,
    Eye,
    EyeOff,
    X,
} from "lucide-react";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const DIFF_COLORS = { easy: "#10b981", medium: "#f59e0b", hard: "#ef4444" };

const Assignments = () => {
    const [assignments, setAssignments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState(null);
    const [detailData, setDetailData] = useState({});
    const [loadingDetail, setLoadingDetail] = useState({});

    // Credentials modal
    const [credModal, setCredModal] = useState(null);
    const [credData, setCredData] = useState(null);
    const [loadingCreds, setLoadingCreds] = useState(false);
    const [copied, setCopied] = useState(false);

    const token = localStorage.getItem("token");
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

    useEffect(() => {
        fetchAssignments();
    }, []);

    const fetchAssignments = async () => {
        try {
            setLoading(true);
            const res = await fetch(`${API_BASE}/api/enterprise/assignments/`, { headers });
            if (res.ok) {
                const data = await res.json();
                setAssignments(data.assignments || []);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const toggleDetails = async (assignmentId) => {
        if (expandedId === assignmentId) {
            setExpandedId(null);
            return;
        }
        setExpandedId(assignmentId);
        if (!detailData[assignmentId]) {
            try {
                setLoadingDetail((p) => ({ ...p, [assignmentId]: true }));
                const res = await fetch(`${API_BASE}/api/enterprise/assignments/${assignmentId}/details`, { headers });
                if (res.ok) {
                    const data = await res.json();
                    setDetailData((p) => ({ ...p, [assignmentId]: data }));
                }
            } catch (err) {
                console.error(err);
            } finally {
                setLoadingDetail((p) => ({ ...p, [assignmentId]: false }));
            }
        }
    };

    const openCredentials = async (assignmentId) => {
        setCredModal(assignmentId);
        setCopied(false);
        try {
            setLoadingCreds(true);
            const res = await fetch(`${API_BASE}/api/enterprise/assignments/${assignmentId}/credentials`, { headers });
            if (res.ok) {
                const data = await res.json();
                setCredData(data);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingCreds(false);
        }
    };

    const downloadCSV = () => {
        if (!credData?.credentials) return;
        const rows = [["Student Name", "Roll No", "Account ID", "Password", "Port"]];
        credData.credentials.forEach((c) => {
            rows.push([c.student_name, c.roll_no, c.account_id, c.password, c.assigned_port || ""]);
        });
        const csv = rows.map((r) => r.map((v) => `"${v}"`).join(",")).join("\n");
        const blob = new Blob([csv], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `credentials_${credModal}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const copyAll = () => {
        if (!credData?.credentials) return;
        const text = credData.credentials
            .map((c) => `${c.student_name} | ${c.account_id} | ${c.password}`)
            .join("\n");
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-black flex items-center justify-center">
                <Loader className="w-8 h-8 text-blue-400 animate-spin" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-black text-white">
            <div
                className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-64 rounded-full blur-3xl opacity-10 pointer-events-none"
                style={{ background: "radial-gradient(ellipse, #3b82f6, transparent 70%)" }}
            />

            <style>{`
        @keyframes fadeUp { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:translateY(0); } }
        .anim-row { animation: fadeUp 0.4s ease both; }
      `}</style>

            <div className="relative z-10 max-w-5xl mx-auto px-5 py-7">
                {/* Header */}
                <div className="flex items-center gap-2 mb-6" style={{ animation: "fadeUp 0.35s ease both" }}>
                    <div className="w-7 h-7 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
                        <ClipboardList className="w-4 h-4 text-blue-400" />
                    </div>
                    <h1 className="text-xl font-bold text-white">Assignments</h1>
                    <span className="text-xs text-gray-600 ml-1">({assignments.length})</span>
                </div>

                {assignments.length === 0 ? (
                    <div className="rounded-xl border border-gray-800/60 bg-gray-950/50 p-12 text-center" style={{ animation: "fadeUp 0.4s ease both" }}>
                        <ClipboardList className="w-10 h-10 text-gray-700 mx-auto mb-3" />
                        <p className="text-gray-500 text-sm">No assignments yet. Assign a machine to a class from the Campaigns page.</p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {assignments.map((a, i) => {
                            const diffColor = DIFF_COLORS[a.difficulty] || "#6b7280";
                            const solved = a.solved_count || 0;
                            const total = a.total_students || 1;
                            const pct = Math.round((solved / total) * 100);
                            const isExpanded = expandedId === a.assignment_id;
                            const detail = detailData[a.assignment_id];

                            return (
                                <div key={a.assignment_id} className="rounded-xl border border-gray-800/60 bg-gray-950/50 overflow-hidden anim-row" style={{ animationDelay: `${i * 60}ms` }}>
                                    {/* Card header */}
                                    <div className="p-4">
                                        <div className="flex items-start justify-between mb-3">
                                            <div>
                                                <div className="flex items-center gap-2 mb-1">
                                                    <Shield className="w-4 h-4 text-blue-400" />
                                                    <span className="text-sm font-semibold text-white">{a.machine_name || a.machine_id}</span>
                                                </div>
                                                <div className="flex items-center gap-3 text-xs text-gray-500">
                                                    <span className="flex items-center gap-1"><Users className="w-3 h-3" />{a.class_name}</span>
                                                    <span className="text-gray-700">·</span>
                                                    <span>{a.total_students} students</span>
                                                    {a.assigned_at && (
                                                        <>
                                                            <span className="text-gray-700">·</span>
                                                            <span className="flex items-center gap-1"><Clock className="w-2.5 h-2.5" />{new Date(a.assigned_at).toLocaleDateString()}</span>
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Progress bar */}
                                        <div className="mb-3">
                                            <div className="flex items-center justify-between text-xs mb-1">
                                                <span className="text-gray-500">{solved} / {total} solved</span>
                                                <span className="text-gray-600">{pct}%</span>
                                            </div>
                                            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                                <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
                                            </div>
                                        </div>

                                        {/* Action buttons */}
                                        <div className="flex items-center gap-2">
                                            <button onClick={() => toggleDetails(a.assignment_id)}
                                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-blue-400 bg-blue-500/10 border border-blue-500/25 hover:bg-blue-500/20 transition-all">
                                                {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                                {isExpanded ? "Hide Details" : "View Details"}
                                            </button>
                                            <button onClick={() => openCredentials(a.assignment_id)}
                                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/25 hover:bg-amber-500/20 transition-all">
                                                <Eye className="w-3 h-3" /> Credentials
                                            </button>
                                        </div>
                                    </div>

                                    {/* Expanded details table */}
                                    {isExpanded && (
                                        <div className="border-t border-gray-800/40 bg-gray-900/30 p-4">
                                            {loadingDetail[a.assignment_id] ? (
                                                <div className="flex items-center justify-center py-6">
                                                    <Loader className="w-5 h-5 text-blue-400 animate-spin" />
                                                </div>
                                            ) : detail?.instances ? (
                                                <div className="overflow-x-auto">
                                                    <table className="w-full text-xs">
                                                        <thead>
                                                            <tr className="text-gray-500 border-b border-gray-800/40">
                                                                <th className="text-left py-2 px-3 font-semibold">Student</th>
                                                                <th className="text-left py-2 px-3 font-semibold">Roll No</th>
                                                                <th className="text-left py-2 px-3 font-semibold">Status</th>
                                                                <th className="text-left py-2 px-3 font-semibold">Attempts</th>
                                                                <th className="text-left py-2 px-3 font-semibold">Port</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {detail.instances.map((inst) => (
                                                                <tr key={inst.instance_id} className="border-b border-gray-800/20 hover:bg-gray-800/20">
                                                                    <td className="py-2 px-3 text-gray-300">{inst.student_name}</td>
                                                                    <td className="py-2 px-3 text-gray-500 font-mono">{inst.student_roll_no}</td>
                                                                    <td className="py-2 px-3">
                                                                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold ${inst.status === "solved"
                                                                                ? "text-emerald-400 bg-emerald-400/10"
                                                                                : inst.status === "started"
                                                                                    ? "text-sky-400 bg-sky-400/10"
                                                                                    : "text-gray-500 bg-gray-500/10"
                                                                            }`}>
                                                                            {inst.status === "solved" && <CheckCircle className="w-2.5 h-2.5" />}
                                                                            {inst.status}
                                                                        </span>
                                                                    </td>
                                                                    <td className="py-2 px-3 text-gray-500">{inst.attempts || 0}</td>
                                                                    <td className="py-2 px-3 text-gray-500 font-mono">{inst.assigned_port || "—"}</td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            ) : (
                                                <p className="text-gray-600 text-sm text-center py-4">Failed to load details.</p>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Credentials Modal */}
            {credModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "#333 transparent" }}>
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-bold text-white">Student Credentials</h3>
                            <button onClick={() => { setCredModal(null); setCredData(null); }} className="text-gray-500 hover:text-white transition-colors">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {loadingCreds ? (
                            <div className="flex items-center justify-center py-10">
                                <Loader className="w-6 h-6 text-blue-400 animate-spin" />
                            </div>
                        ) : credData?.credentials ? (
                            <>
                                <div className="flex gap-2 mb-4">
                                    <button onClick={downloadCSV}
                                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 hover:bg-emerald-500/20 transition-all">
                                        <Download className="w-3 h-3" /> Download CSV
                                    </button>
                                    <button onClick={copyAll}
                                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold text-blue-400 bg-blue-500/10 border border-blue-500/25 hover:bg-blue-500/20 transition-all">
                                        <Copy className="w-3 h-3" /> {copied ? "Copied!" : "Copy All"}
                                    </button>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-xs">
                                        <thead>
                                            <tr className="text-gray-500 border-b border-gray-800/40">
                                                <th className="text-left py-2 px-3 font-semibold">Student</th>
                                                <th className="text-left py-2 px-3 font-semibold">Account ID</th>
                                                <th className="text-left py-2 px-3 font-semibold">Password</th>
                                                <th className="text-left py-2 px-3 font-semibold">Port</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {credData.credentials.map((c, i) => (
                                                <tr key={i} className="border-b border-gray-800/20 hover:bg-gray-800/20">
                                                    <td className="py-2 px-3 text-gray-300">{c.student_name}</td>
                                                    <td className="py-2 px-3 text-blue-400 font-mono">{c.account_id}</td>
                                                    <td className="py-2 px-3 text-amber-400 font-mono">{c.password}</td>
                                                    <td className="py-2 px-3 text-gray-500 font-mono">{c.assigned_port || "—"}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </>
                        ) : (
                            <p className="text-gray-600 text-center py-6">Failed to load credentials.</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default Assignments;
