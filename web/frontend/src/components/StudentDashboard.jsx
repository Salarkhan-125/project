// src/components/StudentDashboard.jsx
import React, { useState, useEffect } from "react";
import {
    Shield,
    Play,
    Square,
    Flag,
    CheckCircle,
    XCircle,
    Loader,
    ExternalLink,
    AlertCircle,
} from "lucide-react";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const StudentDashboard = () => {
    const [instance, setInstance] = useState(null);
    const [assignment, setAssignment] = useState(null);
    const [loading, setLoading] = useState(true);
    const [starting, setStarting] = useState(false);
    const [stopping, setStopping] = useState(false);
    const [flagInput, setFlagInput] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [flagResult, setFlagResult] = useState(null);

    const token = localStorage.getItem("token");
    const instanceId = localStorage.getItem("instance_id");
    const assignmentId = localStorage.getItem("assignment_id");
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            setLoading(true);
            if (!assignmentId || !instanceId) return;
            const res = await fetch(
                `${API_BASE}/api/enterprise/assignments/${assignmentId}/details`,
                { headers }
            );
            if (res.ok) {
                const data = await res.json();
                setAssignment(data.assignment);
                const myInstance = (data.instances || []).find(
                    (i) => i.instance_id === instanceId
                );
                setInstance(myInstance || null);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleStart = async () => {
        try {
            setStarting(true);
            const res = await fetch(
                `${API_BASE}/api/enterprise/assignments/${assignmentId}/instances/${instanceId}/start`,
                { method: "POST", headers }
            );
            if (res.ok) {
                await fetchData();
            } else {
                const err = await res.json();
                alert(err.detail || "Failed to start machine");
            }
        } catch (err) {
            alert("Failed to start machine");
        } finally {
            setStarting(false);
        }
    };

    const handleStop = async () => {
        try {
            setStopping(true);
            const res = await fetch(
                `${API_BASE}/api/enterprise/assignments/${assignmentId}/instances/${instanceId}/stop`,
                { method: "POST", headers }
            );
            if (res.ok) {
                await fetchData();
            }
        } catch (err) {
            console.error(err);
        } finally {
            setStopping(false);
        }
    };

    const handleSubmitFlag = async () => {
        if (!flagInput.trim()) return;
        try {
            setSubmitting(true);
            setFlagResult(null);
            const res = await fetch(
                `${API_BASE}/api/enterprise/assignments/${instanceId}/submit-flag`,
                {
                    method: "POST",
                    headers,
                    body: JSON.stringify({ flag: flagInput.trim() }),
                }
            );
            if (res.ok) {
                const data = await res.json();
                setFlagResult(data);
                if (data.correct) {
                    await fetchData();
                }
            }
        } catch (err) {
            setFlagResult({ correct: false, message: "Failed to submit flag." });
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-black flex items-center justify-center">
                <Loader className="w-8 h-8 text-red-400 animate-spin" />
            </div>
        );
    }

    if (!instance) {
        return (
            <div className="min-h-screen bg-black flex items-center justify-center text-center">
                <div>
                    <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
                    <p className="text-gray-400">No assignment found. Contact your teacher.</p>
                </div>
            </div>
        );
    }

    const isSolved = instance.status === "solved";
    const isRunning = instance.status === "started";
    const diffColors = { easy: "#10b981", medium: "#f59e0b", hard: "#ef4444" };
    const machDiff = assignment?.difficulty || "medium";
    const diffColor = diffColors[machDiff] || "#6b7280";

    return (
        <div className="min-h-screen bg-black text-white">
            <div
                className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-64 rounded-full blur-3xl opacity-10 pointer-events-none"
                style={{ background: "radial-gradient(ellipse, #ef4444, transparent 70%)" }}
            />

            <style>{`
        @keyframes fadeUp { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:translateY(0); } }
      `}</style>

            <div className="relative z-10 max-w-2xl mx-auto px-5 py-7">
                {/* Header */}
                <div className="flex items-center gap-2 mb-6" style={{ animation: "fadeUp 0.35s ease both" }}>
                    <div className="w-7 h-7 rounded-lg bg-red-500/15 border border-red-500/30 flex items-center justify-center">
                        <Shield className="w-4 h-4 text-red-400" />
                    </div>
                    <h1 className="text-xl font-bold text-white">My Assignment</h1>
                </div>

                {/* Machine Card */}
                <div
                    className="rounded-xl border border-gray-800/60 bg-gray-950/50 p-5"
                    style={{ animation: "fadeUp 0.4s ease 0.1s both" }}
                >
                    <div className="flex items-start justify-between mb-4">
                        <div>
                            <h2 className="text-lg font-bold text-white mb-1">
                                {assignment?.machine_name || "Assigned Machine"}
                            </h2>
                            <div className="flex items-center gap-3 text-xs text-gray-500">
                                <span
                                    className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase"
                                    style={{ color: diffColor, background: `${diffColor}15`, border: `1px solid ${diffColor}30` }}
                                >
                                    {machDiff}
                                </span>
                                <span className="text-gray-700">·</span>
                                <span>Assigned by: {assignment?.staff_user_id?.slice(0, 8) || "Teacher"}</span>
                            </div>
                        </div>
                        <span
                            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${isSolved
                                    ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/30"
                                    : isRunning
                                        ? "text-sky-400 bg-sky-400/10 border-sky-400/30"
                                        : "text-gray-500 bg-gray-500/10 border-gray-500/30"
                                }`}
                        >
                            {isSolved && <CheckCircle className="w-3 h-3" />}
                            {isSolved ? "Solved" : isRunning ? "Running" : "Not Started"}
                        </span>
                    </div>

                    {/* Port info */}
                    {instance.assigned_port && isRunning && (
                        <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-900/60 border border-gray-800/60">
                            <ExternalLink className="w-3.5 h-3.5 text-blue-400" />
                            <span className="text-sm text-gray-400">
                                Access URL:{" "}
                                <a
                                    href={`http://${window.location.hostname}:${instance.assigned_port}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-blue-400 hover:text-blue-300 font-mono"
                                >
                                    {window.location.hostname}:{instance.assigned_port}
                                </a>
                            </span>
                        </div>
                    )}

                    {/* Start / Stop buttons */}
                    {!isSolved && (
                        <div className="flex gap-3 mb-4">
                            {!isRunning ? (
                                <button
                                    onClick={handleStart}
                                    disabled={starting}
                                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-bold text-white bg-emerald-600 hover:bg-emerald-500 transition-colors disabled:opacity-50"
                                >
                                    {starting ? (
                                        <><Loader className="w-4 h-4 animate-spin" /> Starting...</>
                                    ) : (
                                        <><Play className="w-4 h-4" /> Start Machine</>
                                    )}
                                </button>
                            ) : (
                                <button
                                    onClick={handleStop}
                                    disabled={stopping}
                                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-bold text-white bg-red-600 hover:bg-red-500 transition-colors disabled:opacity-50"
                                >
                                    {stopping ? (
                                        <><Loader className="w-4 h-4 animate-spin" /> Stopping...</>
                                    ) : (
                                        <><Square className="w-4 h-4" /> Stop Machine</>
                                    )}
                                </button>
                            )}
                        </div>
                    )}

                    {/* Flag submission */}
                    <div className="border-t border-gray-800/40 pt-4">
                        <h3 className="text-sm font-bold text-gray-400 mb-3 flex items-center gap-2">
                            <Flag className="w-4 h-4 text-amber-400" /> Submit Flag
                        </h3>

                        {isSolved ? (
                            <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                                <CheckCircle className="w-5 h-5 text-emerald-400" />
                                <span className="text-emerald-400 font-semibold text-sm">
                                    Flag submitted successfully! Solved on{" "}
                                    {instance.solved_at ? new Date(instance.solved_at).toLocaleString() : "—"}
                                </span>
                            </div>
                        ) : (
                            <>
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={flagInput}
                                        onChange={(e) => setFlagInput(e.target.value)}
                                        onKeyDown={(e) => e.key === "Enter" && handleSubmitFlag()}
                                        placeholder="CTFWITHAI{...}"
                                        className="flex-1 px-4 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-sm text-white placeholder-gray-600 outline-none focus:border-amber-500/50 transition-colors font-mono"
                                    />
                                    <button
                                        onClick={handleSubmitFlag}
                                        disabled={submitting || !flagInput.trim()}
                                        className="px-5 py-2.5 rounded-xl text-sm font-bold text-black bg-amber-500 hover:bg-amber-400 transition-colors disabled:opacity-40"
                                    >
                                        {submitting ? "..." : "Submit"}
                                    </button>
                                </div>

                                {flagResult && (
                                    <div className={`mt-3 flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${flagResult.correct
                                            ? "text-emerald-400 bg-emerald-400/10"
                                            : "text-red-400 bg-red-400/10"
                                        }`}>
                                        {flagResult.correct ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                                        {flagResult.message}
                                    </div>
                                )}

                                <p className="text-xs text-gray-600 mt-2">
                                    Attempts: {instance.attempts || 0}
                                </p>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StudentDashboard;
