import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import {
  Loader,
  Clock,
  ArrowUpRight,
  X,
  Trash2,
  Send,
  Server,
  Shield,
  ExternalLink,
  CheckCircle,
} from "lucide-react";

// ─── Campaigns Page ──────────────────────────────────────────────────────────
const Campaigns = () => {
  const navigate = useNavigate();
  const [userId] = useState(() => localStorage.getItem("userId") || "");

  const [error, setError] = useState(null);

  // Staff machines
  const [staffMachines, setStaffMachines] = useState([]);
  const [loadingMachines, setLoadingMachines] = useState(false);

  // Assign modal
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [assignMachineId, setAssignMachineId] = useState(null);
  const [classes, setClasses] = useState([]);
  const [loadingClasses, setLoadingClasses] = useState(false);
  const [selectedClass, setSelectedClass] = useState(null);
  const [assigning, setAssigning] = useState(false);
  const [assignSuccess, setAssignSuccess] = useState(null);

  // Delete confirm
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchStaffMachines();
  }, []);

  // Guard: if userId is missing the user is not properly logged in
  useEffect(() => {
    if (!userId) {
      window.location.href = "/login";
    }
  }, [userId]);

  // ── Staff machine methods ──
  const fetchStaffMachines = async () => {
    try {
      setLoadingMachines(true);
      const res = await api.getStaffMachines();
      setStaffMachines(res.machines || []);
    } catch (err) {
      console.error("Failed to fetch staff machines:", err);
    } finally {
      setLoadingMachines(false);
    }
  };

  const handleDeleteMachine = async (machineId) => {
    try {
      setDeleting(true);
      await api.deleteMachine(machineId);
      setDeleteTarget(null);
      fetchStaffMachines();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  };

  const openAssignModal = async (machineId) => {
    setAssignMachineId(machineId);
    setShowAssignModal(true);
    setSelectedClass(null);
    setAssignSuccess(null);
    try {
      setLoadingClasses(true);
      const token = localStorage.getItem("token");
      const res = await fetch(
        `${process.env.REACT_APP_API_URL || "http://localhost:8000"}/api/enterprise/students/classes`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setClasses(data.classes || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingClasses(false);
    }
  };

  const handleAssign = async () => {
    if (!selectedClass || !assignMachineId) return;
    try {
      setAssigning(true);
      const res = await api.assignMachine(assignMachineId, selectedClass);
      setAssignSuccess(res.message);
      fetchStaffMachines();
    } catch (err) {
      setError(err.message);
    } finally {
      setAssigning(false);
    }
  };



  return (
    <div className="min-h-screen bg-black text-white relative">
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-64 rounded-full blur-3xl opacity-10 pointer-events-none"
        style={{
          background: "radial-gradient(ellipse, #ff7300, transparent 70%)",
        }}
      />



      <div className="relative z-10 max-w-7xl mx-auto px-5 py-7">
        {/* ══════════════ Generated Machines ══════════════ */}
        <div style={{ animation: "fadeUp 0.5s ease 0.15s both" }}>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-6 h-6 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
              <Server className="w-3.5 h-3.5 text-blue-400" />
            </div>
            <h2 className="text-lg font-bold text-white">Generated Machines</h2>
            <span className="text-xs text-gray-600 ml-1">({staffMachines.length})</span>
          </div>

          {loadingMachines ? (
            <div className="flex items-center justify-center py-12">
              <Loader className="w-6 h-6 text-blue-400 animate-spin" />
            </div>
          ) : staffMachines.length === 0 ? (
            <div className="rounded-xl border border-gray-800/60 bg-gray-950/50 p-8 text-center">
              <Server className="w-8 h-8 text-gray-700 mx-auto mb-2" />
              <p className="text-gray-600 text-sm">No generated machines yet. Use the Vuln AI to generate machines.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {staffMachines.map((machine) => {
                const isRunning = machine.container?.status === "running";
                const isAssigned = machine.assigned;
                const diffMap = { easy: "#10b981", medium: "#f59e0b", hard: "#ef4444" };
                const diffColor = diffMap[machine.difficulty] || "#6b7280";

                return (
                  <div key={machine.machine_id}
                    className="rounded-xl border border-gray-800/60 bg-gray-950/50 hover:border-gray-700/60 transition-all p-4 anim-row">
                    {/* Top: CVE + Status */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Shield className="w-4 h-4 text-blue-400" />
                        <span className="text-sm font-semibold text-white">{machine.cve_id || "Unknown"}</span>
                      </div>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${isRunning
                        ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/30"
                        : "text-gray-500 bg-gray-500/10 border-gray-500/30"
                        }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${isRunning ? "bg-emerald-400" : "bg-gray-600"}`} />
                        {isRunning ? "Running" : "Stopped"}
                      </span>
                    </div>

                    {/* Info row */}
                    <div className="flex items-center gap-3 text-xs text-gray-500 mb-3">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase" style={{ color: diffColor, background: `${diffColor}15`, border: `1px solid ${diffColor}30` }}>
                        {machine.difficulty || "medium"}
                      </span>
                      <span className="text-gray-700">·</span>
                      <span className="font-mono text-gray-600">{machine.machine_id?.slice(0, 16)}</span>
                      {machine.created_at && (
                        <>
                          <span className="text-gray-700">·</span>
                          <span className="flex items-center gap-1"><Clock className="w-2.5 h-2.5" />{new Date(machine.created_at).toLocaleDateString()}</span>
                        </>
                      )}
                    </div>

                    {/* Port + URL */}
                    {machine.port && (
                      <div className="text-xs text-gray-600 mb-3 flex items-center gap-1 font-mono">
                        <ExternalLink className="w-3 h-3" /> Port {machine.port}
                      </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex items-center gap-2 mt-auto pt-2 border-t border-gray-800/40">
                      {isAssigned ? (
                        <button onClick={() => navigate("/assignments")}
                          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold text-blue-400 bg-blue-500/10 border border-blue-500/25 hover:bg-blue-500/20 transition-all">
                          VIEW ASSIGNMENT <ArrowUpRight className="w-3 h-3" />
                        </button>
                      ) : (
                        <button onClick={() => openAssignModal(machine.machine_id)}
                          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 hover:bg-emerald-500/20 transition-all">
                          <Send className="w-3 h-3" /> Assign
                        </button>
                      )}
                      <button onClick={() => setDeleteTarget(machine.machine_id)}
                        className="flex items-center justify-center gap-1 px-3 py-2 rounded-lg text-xs font-semibold text-red-400 bg-red-500/10 border border-red-500/25 hover:bg-red-500/20 transition-all">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── Delete Confirm Overlay ── */}
        {deleteTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
            <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 max-w-sm w-full mx-4">
              <h3 className="text-lg font-bold text-white mb-2">Delete Machine?</h3>
              <p className="text-gray-500 text-sm mb-5">This will stop the container and remove all files. This action cannot be undone.</p>
              <div className="flex gap-3">
                <button onClick={() => setDeleteTarget(null)}
                  className="flex-1 px-4 py-2.5 rounded-lg text-sm font-semibold text-gray-400 bg-gray-800 hover:bg-gray-700 transition-colors">Cancel</button>
                <button onClick={() => handleDeleteMachine(deleteTarget)} disabled={deleting}
                  className="flex-1 px-4 py-2.5 rounded-lg text-sm font-semibold text-white bg-red-600 hover:bg-red-500 transition-colors disabled:opacity-50">
                  {deleting ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Assign Modal ── */}
        {showAssignModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
            <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 max-w-md w-full mx-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-white">Assign to Class</h3>
                <button onClick={() => { setShowAssignModal(false); setAssignSuccess(null); }}
                  className="text-gray-500 hover:text-white transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>

              {assignSuccess ? (
                <div className="text-center py-6">
                  <CheckCircle className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
                  <p className="text-emerald-400 font-semibold mb-1">Assignment Created!</p>
                  <p className="text-gray-500 text-sm">{assignSuccess}</p>
                  <button onClick={() => { setShowAssignModal(false); setAssignSuccess(null); }}
                    className="mt-4 px-6 py-2 rounded-lg text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-colors">Done</button>
                </div>
              ) : loadingClasses ? (
                <div className="flex items-center justify-center py-10">
                  <Loader className="w-6 h-6 text-blue-400 animate-spin" />
                </div>
              ) : classes.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-gray-500 text-sm">No classes found. Create a class first in the Students page.</p>
                </div>
              ) : (
                <>
                  <p className="text-gray-500 text-sm mb-3">Select a class to assign this machine to:</p>
                  <div className="space-y-2 max-h-60 overflow-y-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "#333 transparent" }}>
                    {classes.map((cls) => (
                      <button key={cls.class_name}
                        onClick={() => setSelectedClass(cls.class_name)}
                        className={`w-full text-left px-4 py-3 rounded-xl border transition-all ${selectedClass === cls.class_name
                          ? "bg-blue-500/10 border-blue-500/40 text-white"
                          : "bg-gray-900/50 border-gray-800 text-gray-400 hover:border-gray-700"
                          }`}>
                        <span className="font-semibold text-sm">{cls.class_name}</span>
                        <span className="text-xs text-gray-600 ml-2">{cls.student_count} students</span>
                      </button>
                    ))}
                  </div>
                  <button onClick={handleAssign} disabled={!selectedClass || assigning}
                    className="w-full mt-4 px-4 py-2.5 rounded-lg text-sm font-bold text-white bg-emerald-600 hover:bg-emerald-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2">
                    {assigning ? <><Loader className="w-4 h-4 animate-spin" /> Assigning...</> : <>Assign Machine</>}
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Campaigns;
