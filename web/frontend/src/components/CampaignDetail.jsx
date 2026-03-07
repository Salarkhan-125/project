import React, { useState, useEffect } from "react";
import {
  Target,
  Shield,
  Play,
  Square,
  RefreshCw,
  Trash2,
  Loader,
  AlertCircle,
  CheckCircle,
  ArrowLeft,
  Send,
  FileText,
  Activity,
  Trophy,
  ExternalLink,
  X,
  Cpu,
  Copy,
  ChevronDown,
} from "lucide-react";

const DIFF_COLORS = {
  1: "#10b981",
  2: "#3b82f6",
  3: "#f59e0b",
  4: "#f97316",
  5: "#ef4444",
};
const getDiffColor = (l) => DIFF_COLORS[l] || "#ff7300";

// ─── Stat card (top row) ─────────────────────────────────────────────────────
const StatBadge = ({ icon: Icon, label, value, color, sub }) => (
  <div className="rounded-xl border border-gray-900 bg-gray-950/70 px-4 py-3.5">
    <div className="flex items-center gap-2.5 mb-1.5">
      <div className="p-1.5 rounded-lg" style={{ background: color + "15" }}>
        <Icon className="w-4 h-4" style={{ color }} />
      </div>
      <span className="text-xs text-gray-600 font-medium">{label}</span>
    </div>
    <p className="text-2xl font-bold text-white tabular-nums">{value}</p>
    {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
  </div>
);

// ─── Toast (inline per-machine) ──────────────────────────────────────────────
const Toast = ({ msg }) => {
  if (!msg) return null;
  const bg =
    msg.type === "success"
      ? "bg-green-500"
      : msg.type === "error"
        ? "bg-red-500"
        : "bg-yellow-500";
  const tc = msg.type === "warning" ? "text-black" : "text-white";
  return (
    <div
      className={`absolute top-3 right-3 z-10 ${bg} ${tc} text-xs font-semibold px-3 py-1.5 rounded-lg shadow-lg`}
      style={{ animation: "fadeUp 0.25s ease both" }}
    >
      {msg.message}
    </div>
  );
};

// ─── CampaignDetail ──────────────────────────────────────────────────────────
const CampaignDetail = ({ campaignId: propCampaignId, onBack }) => {
  // CHANGED: read the real userId from localStorage instead of hardcoding 'user_default'
  const [userId] = useState(() => localStorage.getItem("userId") || "");
  const [campaignId, setCampaignId] = useState(propCampaignId);

  useEffect(() => {
    if (!propCampaignId) {
      const m = window.location.pathname.match(/\/campaigns\/([^/]+)/);
      if (m) setCampaignId(m[1]);
    } else setCampaignId(propCampaignId);
  }, [propCampaignId]);

  // Guard: redirect to login if userId is missing
  useEffect(() => {
    if (!userId) {
      window.location.href = "/login";
    }
  }, [userId]);

  const [campaign, setCampaign] = useState(null);
  const [containers, setContainers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState({});
  const [actionMessages, setActionMessages] = useState({});

  // Flag
  const [selectedMachine, setSelectedMachine] = useState(null);
  const [flagInput, setFlagInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState(null);

  // Logs modal
  const [containerLogs, setContainerLogs] = useState(null);

  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Expanded machine detail
  const [expandedMachine, setExpandedMachine] = useState(null);

  const [api, setApi] = useState(null);
  useEffect(() => {
    import("../services/api").then((m) => setApi(m.default));
  }, [fetchCampaignData, fetchContainers]);

  useEffect(() => {
    if (api && campaignId) {
      fetchCampaignData();
      const iv = setInterval(fetchContainers, 3000);
      return () => clearInterval(iv);
    }
  }, [campaignId, api]);

  const fetchCampaignData = async () => {
    if (!api) return;
    try {
      setIsLoading(true);
      setCampaign(await api.getCampaign(campaignId));
      await fetchContainers();
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchContainers = async () => {
    if (!api) return;
    try {
      const d = await api.getCampaignContainers(campaignId);
      setContainers(d.containers || []);
    } catch (e) {
      console.error(e);
    }
  };

  const showMsg = (machineId, message, type = "success") => {
    setActionMessages((p) => ({ ...p, [machineId]: { message, type } }));
    setTimeout(
      () =>
        setActionMessages((p) => {
          const n = { ...p };
          delete n[machineId];
          return n;
        }),
      2800,
    );
  };

  const handleAction = async (containerId, action, machineName, machineId) => {
    const key = `${action}-${containerId}`;
    try {
      setActionLoading((p) => ({ ...p, [key]: true }));
      if (action === "remove" && !window.confirm(`Remove ${machineName}?`)) {
        setActionLoading((p) => ({ ...p, [key]: false }));
        return;
      }
      const map = {
        start: api.startContainer,
        stop: api.stopContainer,
        restart: api.restartContainer,
        remove: api.removeContainer,
      };
      await map[action](containerId);
      showMsg(machineId, `${machineName} ${action}ed`, "success");
      setTimeout(() => {
        fetchContainers();
        setActionLoading((p) => ({ ...p, [key]: false }));
      }, 1800);
    } catch (e) {
      showMsg(machineId, `Failed: ${e.message}`, "error");
      setActionLoading((p) => ({ ...p, [key]: false }));
    }
  };

  const handleViewLogs = async (containerId, name) => {
    try {
      const logs = await api.getContainerLogs(containerId);
      setContainerLogs({ name, logs: logs.logs || "No logs available" });
    } catch (e) {
      setError(`Logs failed: ${e.message}`);
    }
  };

  const handleSubmitFlag = async (machineId) => {
    if (!flagInput.trim()) {
      showMsg(machineId, "⚠ Enter a flag first", "warning");
      return;
    }
    try {
      setSubmitting(true);
      setSubmitResult(null);
      const result = await api.validateFlag(machineId, flagInput, userId);
      setSubmitResult(result);
      if (result.correct) {
        setFlagInput("");
        setTimeout(fetchCampaignData, 1800);
      }
    } catch (e) {
      setSubmitResult({ correct: false, message: e.message, points: 0 });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteCampaign = async () => {
    try {
      setDeleting(true);
      await api.deleteCampaign(campaignId);
      setShowDeleteModal(false);
      onBack ? onBack() : (window.location.href = "/campaigns");
    } catch (e) {
      setError(`Delete failed: ${e.message}`);
      setDeleting(false);
      setShowDeleteModal(false);
    }
  };

  const getContainer = (machineId) =>
    containers.find((c) => c.machine_id === machineId);

  const getContainerUrl = (container) => {
    if (!container || container.State !== "running") return null;
    try {
      if (container.Ports?.length) {
        const p = container.Ports.find((x) => x.PublicPort);
        if (p)
          return `http://${process.env.REACT_APP_SERVER_HOST || "localhost"}:${p.PublicPort}`;
      }
      if (container.NetworkSettings?.Ports) {
        for (const [, bindings] of Object.entries(
          container.NetworkSettings.Ports,
        )) {
          if (bindings?.[0]?.HostPort)
            return `http://${process.env.REACT_APP_SERVER_HOST || "localhost"}:${bindings[0].HostPort}`;
        }
      }
    } catch {}
    return null;
  };

  const navigateBack = () =>
    onBack ? onBack() : (window.location.href = "/campaigns");

  if (!api || isLoading || !campaignId)
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <div className="relative w-12 h-12 mx-auto mb-3">
            <div className="absolute inset-0 rounded-full border-2 border-orange-500/20" />
            <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-orange-500 animate-spin" />
          </div>
          <p className="text-gray-600 text-xs">
            {!campaignId ? "Resolving campaign…" : "Loading…"}
          </p>
        </div>
      </div>
    );

  if (error && !campaign)
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-6">
        <div className="max-w-sm w-full bg-red-950/20 border border-red-500/30 rounded-xl p-8 text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-white mb-1">Error</h2>
          <p className="text-gray-500 text-sm mb-5">{error}</p>
          <button
            onClick={navigateBack}
            className="px-5 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm rounded-lg font-semibold transition-colors"
          >
            Back
          </button>
        </div>
      </div>
    );

  const runningCount = containers.filter((c) => c.State === "running").length;
  const solvedCount = campaign?.progress?.solved || 0;
  const totalMachines =
    campaign?.progress?.total || campaign?.machine_count || 0;
  const pct = totalMachines
    ? Math.round((solvedCount / totalMachines) * 100)
    : 0;

  return (
    <div className="min-h-screen bg-black text-white relative">
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-64 rounded-full blur-3xl opacity-10 pointer-events-none"
        style={{
          background: "radial-gradient(ellipse, #ff7300, transparent 70%)",
        }}
      />

      <style>{`
        @keyframes fadeUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
        .machine-card { animation: fadeUp 0.4s ease both; }
      `}</style>

      <div className="relative z-10 max-w-7xl mx-auto px-5 py-7">
        {/* ── Top nav ── */}
        <div
          className="flex items-center justify-between mb-5"
          style={{ animation: "fadeUp 0.3s ease both" }}
        >
          <button
            onClick={navigateBack}
            className="flex items-center gap-2 text-gray-500 hover:text-gray-200 text-sm transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Campaigns
          </button>
          <button
            onClick={() => setShowDeleteModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 text-xs font-semibold rounded-lg transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" /> Delete
          </button>
        </div>

        {/* ── Title ── */}
        <div
          className="mb-5"
          style={{ animation: "fadeUp 0.35s ease 0.04s both" }}
        >
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-orange-500/15 border border-orange-500/30 flex items-center justify-center">
              <Shield className="w-4 h-4 text-orange-500" />
            </div>
            <h1 className="text-xl font-bold text-white">
              {campaign?.campaign_name || "Campaign Details"}
            </h1>
          </div>
          <p className="text-gray-600 text-xs mt-1 ml-10.5">
            Difficulty Level {campaign?.difficulty} · {totalMachines} machines ·
            Created{" "}
            {campaign?.created_at
              ? new Date(campaign.created_at).toLocaleDateString()
              : "—"}
          </p>
        </div>

        {/* ── Error banner ── */}
        {error && (
          <div
            className="flex items-center gap-2.5 px-4 py-2.5 rounded-lg bg-red-500/8 border border-red-500/25 mb-4"
            style={{ animation: "fadeUp 0.3s ease both" }}
          >
            <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
            <p className="text-red-400 text-xs flex-1">{error}</p>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-300"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* ── Stats row ── */}
        <div
          className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6"
          style={{ animation: "fadeUp 0.4s ease 0.08s both" }}
        >
          <StatBadge
            icon={Target}
            label="Progress"
            value={`${solvedCount}/${totalMachines}`}
            color="#ff7300"
            sub={`${pct}% complete`}
          />
          <StatBadge
            icon={Trophy}
            label="Points"
            value={campaign?.progress?.total_points || 0}
            color="#f59e0b"
            sub="Total earned"
          />
          <StatBadge
            icon={Activity}
            label="Running"
            value={runningCount}
            color="#10b981"
            sub="Active containers"
          />
          <StatBadge
            icon={Cpu}
            label="Machines"
            value={totalMachines}
            color="#60a5fa"
            sub={`${containers.length} containers`}
          />
        </div>

        {/* ── Progress bar ── */}
        <div
          className="rounded-xl border border-gray-900 bg-gray-950/60 px-5 py-3 mb-6 flex items-center gap-4"
          style={{ animation: "fadeUp 0.4s ease 0.12s both" }}
        >
          <div className="flex-1 h-2 rounded-full bg-gray-800 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${pct}%`,
                background:
                  pct >= 100
                    ? "#10b981"
                    : "linear-gradient(90deg, #ff7300, #ff9500)",
              }}
            />
          </div>
          <span className="text-xs font-bold text-gray-400 tabular-nums w-10 text-right">
            {pct}%
          </span>
        </div>

        {/* ── Machines List ── */}
        <div style={{ animation: "fadeUp 0.4s ease 0.16s both" }}>
          {campaign?.machines?.map((machine, index) => {
            const container = getContainer(machine.machine_id);
            const isRunning = container?.State === "running";
            const containerId = container?.Id || "";
            const containerUrl = getContainerUrl(container);
            const msg = actionMessages[machine.machine_id];
            const isExpanded = expandedMachine === machine.machine_id;
            const diffColor = getDiffColor(machine.difficulty);

            return (
              <div
                key={machine.machine_id}
                className="machine-card mb-3"
                style={{ animationDelay: `${index * 0.05}s` }}
              >
                <div className="rounded-xl border border-gray-900 bg-gray-950/60 overflow-hidden hover:border-gray-800 transition-colors">
                  <div
                    className="flex items-center gap-4 px-5 py-4 cursor-pointer relative"
                    onClick={() =>
                      setExpandedMachine(isExpanded ? null : machine.machine_id)
                    }
                  >
                    <Toast msg={msg} />
                    <div
                      className="w-9 h-9 rounded-lg flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
                      style={{ background: diffColor }}
                    >
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-sm font-bold text-gray-100">
                          {machine.variant}
                        </h3>
                        <span
                          className="text-xs font-semibold px-2 py-0.5 rounded-full"
                          style={{
                            color: diffColor,
                            background: diffColor + "18",
                          }}
                        >
                          Lv {machine.difficulty}
                        </span>
                        {machine.solved && (
                          <span className="text-xs text-green-500 font-semibold flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" /> Solved
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {container ? (
                        <span
                          className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full
                          ${isRunning ? "bg-green-500/10 text-green-400" : "bg-gray-800 text-gray-500"}`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${isRunning ? "bg-green-400 animate-pulse" : "bg-gray-600"}`}
                          />
                          {container.State}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-700 bg-gray-900 px-2.5 py-1 rounded-full">
                          No container
                        </span>
                      )}
                      <ChevronDown
                        className={`w-4 h-4 text-gray-600 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                      />
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-gray-900 px-5 py-4 space-y-4">
                      {container ? (
                        <>
                          <div className="flex items-center gap-2 flex-wrap">
                            {!isRunning ? (
                              <button
                                onClick={() =>
                                  handleAction(
                                    containerId,
                                    "start",
                                    machine.variant,
                                    machine.machine_id,
                                  )
                                }
                                disabled={actionLoading[`start-${containerId}`]}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-green-500/12 hover:bg-green-500/22 border border-green-500/30 text-green-400 text-xs font-semibold rounded-lg transition-colors disabled:opacity-50"
                              >
                                {actionLoading[`start-${containerId}`] ? (
                                  <Loader className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                  <Play className="w-3.5 h-3.5" />
                                )}{" "}
                                Start
                              </button>
                            ) : (
                              <button
                                onClick={() =>
                                  handleAction(
                                    containerId,
                                    "stop",
                                    machine.variant,
                                    machine.machine_id,
                                  )
                                }
                                disabled={actionLoading[`stop-${containerId}`]}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/12 hover:bg-red-500/22 border border-red-500/30 text-red-400 text-xs font-semibold rounded-lg transition-colors disabled:opacity-50"
                              >
                                {actionLoading[`stop-${containerId}`] ? (
                                  <Loader className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                  <Square className="w-3.5 h-3.5" />
                                )}{" "}
                                Stop
                              </button>
                            )}
                            <button
                              onClick={() =>
                                handleAction(
                                  containerId,
                                  "restart",
                                  machine.variant,
                                  machine.machine_id,
                                )
                              }
                              disabled={actionLoading[`restart-${containerId}`]}
                              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/12 hover:bg-blue-500/22 border border-blue-500/30 text-blue-400 text-xs font-semibold rounded-lg transition-colors disabled:opacity-50"
                            >
                              {actionLoading[`restart-${containerId}`] ? (
                                <Loader className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <RefreshCw className="w-3.5 h-3.5" />
                              )}{" "}
                              Restart
                            </button>
                            <button
                              onClick={() =>
                                handleViewLogs(containerId, container.Name)
                              }
                              className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/12 hover:bg-purple-500/22 border border-purple-500/30 text-purple-400 text-xs font-semibold rounded-lg transition-colors"
                            >
                              <FileText className="w-3.5 h-3.5" /> Logs
                            </button>
                            <button
                              onClick={() =>
                                handleAction(
                                  containerId,
                                  "remove",
                                  machine.variant,
                                  machine.machine_id,
                                )
                              }
                              disabled={actionLoading[`remove-${containerId}`]}
                              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700/40 hover:bg-gray-700/60 border border-gray-700 text-gray-400 text-xs font-semibold rounded-lg transition-colors disabled:opacity-50"
                            >
                              {actionLoading[`remove-${containerId}`] ? (
                                <Loader className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Trash2 className="w-3.5 h-3.5" />
                              )}{" "}
                              Remove
                            </button>
                          </div>

                          {containerUrl && isRunning ? (
                            <div className="flex items-center gap-2 px-3.5 py-2.5 rounded-lg bg-green-500/6 border border-green-500/20">
                              <ExternalLink className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                              <a
                                href={containerUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-green-400 text-xs font-mono hover:text-green-300 transition-colors flex-1 truncate"
                              >
                                {containerUrl}
                              </a>
                              <button
                                onClick={() =>
                                  navigator.clipboard.writeText(containerUrl)
                                }
                                className="text-gray-600 hover:text-gray-300 transition-colors"
                              >
                                <Copy className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          ) : isRunning ? (
                            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-yellow-500/6 border border-yellow-500/20">
                              <AlertCircle className="w-3.5 h-3.5 text-yellow-500" />
                              <p className="text-yellow-400 text-xs">
                                Running but no port exposed
                              </p>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-900/50 border border-gray-800">
                              <AlertCircle className="w-3.5 h-3.5 text-gray-600" />
                              <p className="text-gray-600 text-xs">
                                Start the container to get access URL
                              </p>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-yellow-500/6 border border-yellow-500/20">
                          <AlertCircle className="w-3.5 h-3.5 text-yellow-500" />
                          <p className="text-yellow-400 text-xs">
                            No container found for this machine
                          </p>
                        </div>
                      )}

                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-600">
                          Machine ID
                        </span>
                        <code className="text-orange-500 text-xs font-mono">
                          {machine.machine_id}
                        </code>
                      </div>
                      {container && (
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-gray-600">
                            Container
                          </span>
                          <code className="text-gray-500 text-xs font-mono">
                            {containerId.slice(0, 16)}…
                          </code>
                        </div>
                      )}

                      {!machine.solved && (
                        <div className="pt-2 border-t border-gray-900">
                          <p className="text-xs text-gray-600 mb-2 font-semibold uppercase tracking-wider">
                            Submit Flag
                          </p>
                          <div className="flex gap-2">
                            <input
                              type="text"
                              placeholder="HACKFORGE{...}"
                              value={
                                selectedMachine === machine.machine_id
                                  ? flagInput
                                  : ""
                              }
                              onFocus={() => {
                                setSelectedMachine(machine.machine_id);
                                setSubmitResult(null);
                              }}
                              onChange={(e) => {
                                setSelectedMachine(machine.machine_id);
                                setFlagInput(e.target.value);
                                setSubmitResult(null);
                              }}
                              onKeyPress={(e) => {
                                if (e.key === "Enter")
                                  handleSubmitFlag(machine.machine_id);
                              }}
                              className="flex-1 px-3 py-2 bg-black border border-gray-800 rounded-lg text-white text-xs font-mono focus:outline-none focus:border-orange-500 placeholder-gray-700"
                            />
                            <button
                              onClick={() =>
                                handleSubmitFlag(machine.machine_id)
                              }
                              disabled={submitting || !flagInput.trim()}
                              className="px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-800 text-white rounded-lg transition-colors flex items-center gap-1.5 text-xs font-semibold"
                            >
                              {submitting &&
                              selectedMachine === machine.machine_id ? (
                                <Loader className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Send className="w-3.5 h-3.5" />
                              )}
                              Submit
                            </button>
                          </div>

                          {submitResult &&
                            selectedMachine === machine.machine_id && (
                              <div
                                className={`mt-2 flex items-center gap-2 px-3 py-2 rounded-lg border
                              ${submitResult.correct ? "bg-green-500/8 border-green-500/25" : "bg-red-500/8 border-red-500/25"}`}
                              >
                                {submitResult.correct ? (
                                  <CheckCircle className="w-4 h-4 text-green-500" />
                                ) : (
                                  <AlertCircle className="w-4 h-4 text-red-500" />
                                )}
                                <div>
                                  <p
                                    className={`text-xs font-semibold ${submitResult.correct ? "text-green-400" : "text-red-400"}`}
                                  >
                                    {submitResult.message}
                                  </p>
                                  {submitResult.points > 0 && (
                                    <p className="text-xs text-gray-600">
                                      +{submitResult.points} points
                                    </p>
                                  )}
                                </div>
                              </div>
                            )}
                        </div>
                      )}

                      {(machine.attempts > 0 || machine.points_earned > 0) && (
                        <div className="flex items-center gap-4 pt-2 border-t border-gray-900">
                          {machine.attempts > 0 && (
                            <span className="text-xs text-gray-600">
                              Attempts:{" "}
                              <span className="text-gray-400">
                                {machine.attempts}
                              </span>
                            </span>
                          )}
                          {machine.points_earned > 0 && (
                            <span className="text-xs text-gray-600">
                              Points:{" "}
                              <span className="text-orange-500 font-semibold">
                                +{machine.points_earned}
                              </span>
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Logs Modal ── */}
      {containerLogs && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-6">
          <div
            className="bg-gray-950 border border-gray-800 rounded-xl w-full max-w-3xl max-h-[75vh] flex flex-col"
            style={{ animation: "fadeUp 0.25s ease both" }}
          >
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-900">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-purple-500" />
                <h3 className="text-sm font-bold text-white">Container Logs</h3>
                <span className="text-xs text-gray-600">
                  {containerLogs.name}
                </span>
              </div>
              <button
                onClick={() => setContainerLogs(null)}
                className="text-gray-600 hover:text-gray-300 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              <pre className="text-xs text-green-400 font-mono bg-black/60 p-4 rounded-lg whitespace-pre-wrap overflow-x-auto">
                {containerLogs.logs}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete Modal ── */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-6">
          <div
            className="bg-gray-950 border border-red-500/30 rounded-xl max-w-sm w-full p-6 text-center"
            style={{ animation: "fadeUp 0.25s ease both" }}
          >
            <div className="w-12 h-12 bg-red-500/15 rounded-full flex items-center justify-center mx-auto mb-3">
              <Trash2 className="w-6 h-6 text-red-500" />
            </div>
            <h3 className="text-lg font-bold text-white mb-1">
              Delete Campaign?
            </h3>
            <p className="text-gray-500 text-xs mb-5">
              This will stop and remove all containers. This action cannot be
              undone.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setShowDeleteModal(false)}
                disabled={deleting}
                className="flex-1 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-sm rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteCampaign}
                disabled={deleting}
                className="flex-1 px-4 py-2 bg-red-500 hover:bg-red-600 disabled:bg-red-800 text-white text-sm font-semibold rounded-lg transition-colors flex items-center justify-center gap-1.5"
              >
                {deleting ? (
                  <>
                    <Loader className="w-3.5 h-3.5 animate-spin" /> Deleting…
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CampaignDetail;
