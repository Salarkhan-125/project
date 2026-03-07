import React, { useState, useEffect } from 'react';
import {
  Server, Target, Loader, AlertCircle, CheckCircle,
  Send, ExternalLink, Play, Square, RotateCw, Trash2
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const Machines = () => {
  const [userId] = useState('user_default');
  const [machines, setMachines] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedMachine, setSelectedMachine] = useState(null);
  const [flagInput, setFlagInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState(null);
  const [containerAction, setContainerAction] = useState({});
  const navigate = useNavigate();
  const [actionMessages, setActionMessages] = useState({});

  useEffect(() => {
    fetchMachines();
    const interval = setInterval(fetchMachines, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchMachines = async () => {
    try {
      setIsLoading(true);
      const data = await api.getMachines();
      console.log('📦 Fetched machines:', data);

      // Debug: Log container info
      data.forEach(machine => {
        if (machine.container) {
          console.log(`Machine ${machine.machine_id}:`, {
            container_id: machine.container.container_id,
            status: machine.container.status,
            name: machine.container.container_name
          });
        }
      });

      setMachines(data);
      setError(null);
    } catch (err) {
      console.error('❌ Error fetching machines:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const showActionMessage = (containerId, message, type = 'success') => {
    console.log(`💬 Action message: ${message} (${type})`);
    setActionMessages(prev => ({
      ...prev,
      [containerId]: { message, type }
    }));

    setTimeout(() => {
      setActionMessages(prev => {
        const newMessages = { ...prev };
        delete newMessages[containerId];
        return newMessages;
      });
    }, 3000);
  };

  const handleContainerAction = async (containerId, action, machineName = 'container') => {
    if (!containerId) {
      console.error('❌ No container ID provided');
      showActionMessage('error', 'Container ID missing', 'error');
      return;
    }

    console.log(`🔧 Action: ${action} on container: ${containerId}`);
    setContainerAction(prev => ({ ...prev, [containerId]: action }));

    try {
      let result;

      switch (action) {
        case 'start':
          console.log('▶️ Starting container...');
          result = await api.startContainer(containerId);
          console.log('✅ Start result:', result);
          showActionMessage(containerId, `✓ ${machineName} started`, 'success');
          break;

        case 'stop':
          console.log('⏹️ Stopping container...');
          result = await api.stopContainer(containerId);
          console.log('✅ Stop result:', result);
          showActionMessage(containerId, `✓ ${machineName} stopped`, 'success');
          break;

        case 'restart':
          console.log('🔄 Restarting container...');
          result = await api.restartContainer(containerId);
          console.log('✅ Restart result:', result);
          showActionMessage(containerId, `✓ ${machineName} restarted`, 'success');
          break;

        case 'remove':
          if (!window.confirm(`Are you sure you want to remove ${machineName}?`)) {
            console.log('❌ Remove cancelled by user');
            setContainerAction(prev => ({ ...prev, [containerId]: null }));
            return;
          }
          console.log('🗑️ Removing container...');
          result = await api.removeContainer(containerId);
          console.log('✅ Remove result:', result);
          showActionMessage(containerId, `✓ ${machineName} removed`, 'success');
          break;

        default:
          console.error('❌ Unknown action:', action);
          showActionMessage(containerId, `Unknown action: ${action}`, 'error');
          return;
      }

      // Refresh machines after successful action
      console.log('🔄 Refreshing machines list in 2 seconds...');
      setTimeout(() => {
        fetchMachines();
      }, 2000);

    } catch (err) {
      console.error(`❌ Error ${action} container:`, err);
      showActionMessage(containerId, `Failed to ${action}: ${err.message}`, 'error');
    } finally {
      setContainerAction(prev => ({ ...prev, [containerId]: null }));
    }
  };

  const handleSubmitFlag = async (machineId) => {
    if (!flagInput.trim()) {
      showActionMessage(machineId, '⚠ Please enter a flag', 'warning');
      return;
    }

    console.log('🚩 Submitting flag for machine:', machineId);

    try {
      setSubmitting(true);
      setSubmitResult(null);

      const result = await api.validateFlag(machineId, flagInput, userId);
      console.log('✅ Flag validation result:', result);

      setSubmitResult(result);

      if (result.correct) {
        setFlagInput('');
        setTimeout(fetchMachines, 2000);
      }
    } catch (err) {
      console.error('❌ Flag submission error:', err);
      setSubmitResult({
        correct: false,
        message: err.message || 'Failed to validate flag',
        points: 0
      });
    } finally {
      setSubmitting(false);
    }
  };

  const getDifficultyColor = (level) => {
    const colors = {
      1: '#10b981', // green
      2: '#3b82f6', // blue
      3: '#f59e0b', // yellow
      4: '#f97316', // orange
      5: '#ef4444'  // red
    };
    return colors[level] || '#ff7300';
  };

  const getDifficultyLabel = (level) => {
    const labels = {
      1: 'Beginner',
      2: 'Easy',
      3: 'Medium',
      4: 'Hard',
      5: 'Expert'
    };
    return labels[level] || 'Unknown';
  };

  const getContainerStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'running':
        return '#10b981';
      case 'exited':
        return '#ef4444';
      case 'paused':
        return '#f59e0b';
      case 'created':
        return '#3b82f6';
      default:
        return '#6b7280';
    }
  };

  const getContainerStatusLabel = (status) => {
    if (!status) return 'Unknown';
    return status.charAt(0).toUpperCase() + status.slice(1);
  };

  if (isLoading && machines.length === 0) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <Loader className="w-12 h-12 text-orange-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading machines...</p>
        </div>
      </div>
    );
  }

  if (error && machines.length === 0) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-red-950/20 border border-red-500/50 rounded-2xl p-8 text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-white mb-2">Error Loading Machines</h2>
          <p className="text-gray-400 mb-6">{error}</p>
          <button
            onClick={fetchMachines}
            className="px-6 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-lg transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-white">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-white via-orange-500 to-orange-600 bg-clip-text text-transparent">
              Available Machines
            </h1>
            <p className="text-gray-400">
              {machines.length} machine{machines.length !== 1 ? 's' : ''} ready for exploitation
            </p>
          </div>
          <button
            onClick={fetchMachines}
            disabled={isLoading}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            <RotateCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {machines.length === 0 ? (
          <div className="text-center py-16">
            <Server className="w-24 h-24 text-gray-700 mx-auto mb-4" />
            <h3 className="text-2xl font-bold text-gray-600 mb-2">No Machines Available</h3>
            <p className="text-gray-500 mb-6">Create a campaign to generate machines</p>
            <button
              onClick={() => navigate('/vuln-ai')}
              className="px-6 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-lg transition-colors"
            >
              Generate with Vuln AI
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {machines.map((machine, index) => {
              const containerId = machine.container?.container_id;
              const containerStatus = machine.container?.status;
              const actionMsg = actionMessages[containerId];
              const isActionLoading = containerAction[containerId];

              // Debug log for each machine
              console.log(`Rendering machine ${machine.machine_id}:`, {
                has_container: !!machine.container,
                container_id: containerId,
                status: containerStatus,
                is_running: machine.is_running
              });

              return (
                <div
                  key={machine.machine_id}
                  className="group relative rounded-2xl border border-gray-900 bg-gradient-to-br from-gray-900/50 to-black/50 backdrop-blur p-6 hover:border-orange-500/50 transition-all duration-300"
                  style={{
                    animation: `slideUp 0.4s ease-out ${index * 0.1}s both`
                  }}
                >
                  {/* Action Message Toast */}
                  {actionMsg && (
                    <div
                      className={`absolute top-4 right-4 z-10 px-4 py-2 rounded-lg text-sm font-medium shadow-lg ${actionMsg.type === 'success'
                          ? 'bg-green-500 text-white'
                          : actionMsg.type === 'error'
                            ? 'bg-red-500 text-white'
                            : 'bg-yellow-500 text-black'
                        }`}
                      style={{ animation: 'slideDown 0.3s ease-out' }}
                    >
                      {actionMsg.message}
                    </div>
                  )}

                  {/* Machine Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div
                        className="p-3 rounded-xl"
                        style={{ backgroundColor: `${getDifficultyColor(machine.difficulty)}20` }}
                      >
                        <Target className="w-6 h-6" style={{ color: getDifficultyColor(machine.difficulty) }} />
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-white">{machine.variant}</h3>
                        {machine.campaign_name && (
                          <p className="text-xs text-orange-500 mt-1">
                            📁 {machine.campaign_name}
                          </p>
                        )}
                      </div>
                    </div>

                    <div
                      className="px-3 py-1 rounded-lg text-xs font-semibold"
                      style={{
                        backgroundColor: `${getDifficultyColor(machine.difficulty)}20`,
                        color: getDifficultyColor(machine.difficulty)
                      }}
                    >
                      {getDifficultyLabel(machine.difficulty)}
                    </div>
                  </div>

                  {/* Container Status & Controls */}
                  {machine.container ? (
                    <div className="mb-4 p-4 rounded-lg bg-black/30 border border-gray-800">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-2.5 h-2.5 rounded-full"
                            style={{
                              backgroundColor: getContainerStatusColor(containerStatus),
                              animation: containerStatus === 'running' ? 'pulse 2s infinite' : 'none'
                            }}
                          />
                          <span className="text-sm text-gray-300 font-medium">
                            {getContainerStatusLabel(containerStatus)}
                          </span>
                          <code className="text-xs text-gray-600 font-mono ml-2">
                            {containerId?.slice(0, 12)}
                          </code>
                        </div>

                        {/* Container Controls */}
                        <div className="flex gap-2">
                          {containerStatus !== 'running' ? (
                            <button
                              onClick={async () => {
                                setContainerAction(prev => ({ ...prev, [containerId]: 'start' }));
                                try {
                                  await api.startMachineContainer(machine.machine_id);
                                  showActionMessage(containerId, `✓ ${machine.variant} started`, 'success');
                                  setTimeout(fetchMachines, 3000);
                                } catch (err) {
                                  showActionMessage(containerId, `Failed: ${err.message}`, 'error');
                                } finally {
                                  setContainerAction(prev => ({ ...prev, [containerId]: null }));
                                }
                              }}
                              disabled={isActionLoading === 'start'}
                              className="p-2 bg-green-500/20 hover:bg-green-500/30 rounded-lg text-green-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                              title="Start Container"
                            >
                              {isActionLoading === 'start' ? (
                                <Loader className="w-4 h-4 animate-spin" />
                              ) : (
                                <Play className="w-4 h-4" />
                              )}
                            </button>
                          ) : (
                            <button
                              onClick={async () => {
                                setContainerAction(prev => ({ ...prev, [containerId]: 'stop' }));
                                try {
                                  await api.stopMachineContainer(machine.machine_id);
                                  showActionMessage(containerId, `✓ ${machine.variant} stopped`, 'success');
                                  setTimeout(fetchMachines, 3000);
                                } catch (err) {
                                  showActionMessage(containerId, `Failed: ${err.message}`, 'error');
                                } finally {
                                  setContainerAction(prev => ({ ...prev, [containerId]: null }));
                                }
                              }}
                              disabled={isActionLoading === 'stop'}
                              className="p-2 bg-red-500/20 hover:bg-red-500/30 rounded-lg text-red-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                              title="Stop Container"
                            >
                              {isActionLoading === 'stop' ? (
                                <Loader className="w-4 h-4 animate-spin" />
                              ) : (
                                <Square className="w-4 h-4" />
                              )}
                            </button>
                          )}

                          <button
                            onClick={async () => {
                              setContainerAction(prev => ({ ...prev, [containerId]: 'restart' }));
                              try {
                                await api.restartMachineContainer(machine.machine_id);
                                showActionMessage(containerId, `✓ ${machine.variant} restarted`, 'success');
                                setTimeout(fetchMachines, 3000);
                              } catch (err) {
                                showActionMessage(containerId, `Failed: ${err.message}`, 'error');
                              } finally {
                                setContainerAction(prev => ({ ...prev, [containerId]: null }));
                              }
                            }}
                            disabled={isActionLoading === 'restart'}
                            className="p-2 bg-blue-500/20 hover:bg-blue-500/30 rounded-lg text-blue-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            title="Restart Container"
                          >
                            {isActionLoading === 'restart' ? (
                              <Loader className="w-4 h-4 animate-spin" />
                            ) : (
                              <RotateCw className="w-4 h-4" />
                            )}
                          </button>

                          <button
                            onClick={() => handleContainerAction(containerId, 'remove', machine.variant)}
                            disabled={isActionLoading === 'remove'}
                            className="p-2 bg-gray-500/20 hover:bg-gray-500/30 rounded-lg text-gray-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            title="Remove Container"
                          >
                            {isActionLoading === 'remove' ? (
                              <Loader className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Container URL */}
                      {machine.url && machine.is_running && (
                        <a
                          href={machine.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-sm text-orange-500 hover:text-orange-400 transition-colors font-mono"
                        >
                          <ExternalLink className="w-4 h-4" />
                          {machine.url}
                        </a>
                      )}

                      {/* Status Message */}
                      {!machine.is_running && containerStatus === 'exited' && (
                        <p className="text-xs text-gray-500 mt-2 flex items-center gap-2">
                          <AlertCircle className="w-3 h-3" />
                          Container stopped. Click Play to start.
                        </p>
                      )}
                    </div>
                  ) : (
                    <div className="mb-4 p-4 rounded-lg bg-yellow-950/20 border border-yellow-500/50 flex items-center justify-between">
                      <p className="text-sm text-yellow-400 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" />
                        No container — click Launch to start
                      </p>
                      <button
                        onClick={async () => {
                          setContainerAction(prev => ({ ...prev, [machine.machine_id]: 'start' }));
                          try {
                            await api.startMachineContainer(machine.machine_id);
                            showActionMessage(machine.machine_id, `✓ ${machine.variant} launched`, 'success');
                            setTimeout(fetchMachines, 3000);
                          } catch (err) {
                            showActionMessage(machine.machine_id, `Failed: ${err.message}`, 'error');
                          } finally {
                            setContainerAction(prev => ({ ...prev, [machine.machine_id]: null }));
                          }
                        }}
                        disabled={containerAction[machine.machine_id] === 'start'}
                        className="p-2 bg-green-500/20 hover:bg-green-500/30 rounded-lg text-green-400 transition-colors disabled:opacity-50"
                        title="Launch Machine"
                      >
                        {containerAction[machine.machine_id] === 'start'
                          ? <Loader className="w-4 h-4 animate-spin" />
                          : <Play className="w-4 h-4" />}
                      </button>
                    </div>
                  )}
                  {/* Machine Info */}
                  <div className="space-y-3 mb-4">
                    <div className="p-3 rounded-lg bg-black/30 border border-gray-800">
                      <p className="text-xs text-gray-500 mb-1">Machine ID</p>
                      <code className="text-orange-500 text-sm font-mono">{machine.machine_id}</code>
                    </div>

                    {/* Progress Indicator */}
                    {machine.solved && (
                      <div className="p-3 rounded-lg bg-green-950/20 border border-green-500/50 flex items-center gap-2">
                        <CheckCircle className="w-5 h-5 text-green-500" />
                        <span className="text-sm text-green-400">
                          Solved! +{machine.points_earned} points
                        </span>
                      </div>
                    )}

                    {machine.attempts > 0 && !machine.solved && (
                      <div className="p-3 rounded-lg bg-orange-950/20 border border-orange-500/50">
                        <span className="text-xs text-orange-400">
                          {machine.attempts} attempt{machine.attempts !== 1 ? 's' : ''} made
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Flag Submission */}
                  <div className="space-y-3">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder="HACKFORGE{...}"
                        value={selectedMachine === machine.machine_id ? flagInput : ''}
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
                          if (e.key === 'Enter' && !machine.solved) {
                            handleSubmitFlag(machine.machine_id);
                          }
                        }}
                        disabled={machine.solved}
                        className="flex-1 px-4 py-2 bg-black/50 border border-gray-800 rounded-lg text-white focus:outline-none focus:border-orange-500 transition-colors text-sm disabled:opacity-50 font-mono placeholder:text-gray-600"
                      />
                      <button
                        onClick={() => handleSubmitFlag(machine.machine_id)}
                        disabled={submitting || !flagInput.trim() || machine.solved}
                        className="px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-700 disabled:opacity-50 text-white rounded-lg transition-colors flex items-center gap-2"
                        title="Submit Flag"
                      >
                        {submitting && selectedMachine === machine.machine_id ? (
                          <Loader className="w-4 h-4 animate-spin" />
                        ) : (
                          <Send className="w-4 h-4" />
                        )}
                      </button>
                    </div>

                    {/* Submission Result */}
                    {submitResult && selectedMachine === machine.machine_id && (
                      <div
                        className={`p-3 rounded-lg border flex items-center gap-2 ${submitResult.correct
                            ? 'bg-green-950/20 border-green-500/50'
                            : 'bg-red-950/20 border-red-500/50'
                          }`}
                        style={{ animation: 'slideDown 0.3s ease-out' }}
                      >
                        {submitResult.correct ? (
                          <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                        ) : (
                          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                        )}
                        <div className="flex-1">
                          <p className={`text-sm font-medium ${submitResult.correct ? 'text-green-400' : 'text-red-400'}`}>
                            {submitResult.message}
                          </p>
                          {submitResult.points > 0 && (
                            <p className="text-xs text-gray-400 mt-1">
                              +{submitResult.points} points earned!
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Bottom Border Animation */}
                  <div className="absolute bottom-0 left-0 w-full h-1 bg-gradient-to-r from-orange-500 to-orange-600 transform scale-x-0 group-hover:scale-x-100 transition-transform duration-500 rounded-b-2xl" />
                </div>
              );
            })}
          </div>
        )}
      </div>

      <style>{`
        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes slideDown {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
        }
      `}</style>
    </div>
  );
};

export default Machines;
