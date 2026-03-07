import React, { useState, useEffect } from 'react';
import { AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import api from '../services/api';

const ContainerDebug = () => {
  const [dockerStatus, setDockerStatus] = useState(null);
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [status, machinesData] = await Promise.all([
        api.getDockerStatus(),
        api.getMachines()
      ]);
      setDockerStatus(status);
      setMachines(machinesData);
      setLoading(false);
    } catch (err) {
      console.error('Debug fetch error:', err);
      setLoading(false);
    }
  };

  const testContainerAction = async (containerId) => {
    setTestResult({ loading: true });
    try {
      const result = await api.startContainer(containerId);
      setTestResult({ success: true, message: JSON.stringify(result, null, 2) });
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    }
  };

  if (loading) return <div className="p-8 text-white">Loading debug info...</div>;

  return (
    <div className="min-h-screen bg-black text-white p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold text-orange-500">Container Debug Tool</h1>
          <button
            onClick={fetchData}
            className="px-4 py-2 bg-blue-500 rounded-lg flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {/* Docker Status */}
        <div className="mb-6 p-6 bg-gray-900 rounded-xl border border-gray-800">
          <h2 className="text-xl font-bold mb-4 text-orange-500">Docker Status</h2>
          <pre className="text-xs bg-black p-4 rounded overflow-auto">
            {JSON.stringify(dockerStatus, null, 2)}
          </pre>
        </div>

        {/* Machines */}
        <div className="mb-6 p-6 bg-gray-900 rounded-xl border border-gray-800">
          <h2 className="text-xl font-bold mb-4 text-orange-500">Machines</h2>
          <pre className="text-xs bg-black p-4 rounded overflow-auto">
            {JSON.stringify(machines, null, 2)}
          </pre>
        </div>

        {/* Container Matching Test */}
        <div className="mb-6 p-6 bg-gray-900 rounded-xl border border-gray-800">
          <h2 className="text-xl font-bold mb-4 text-orange-500">Container Matching</h2>
          {machines.map((machine) => {
            const container = dockerStatus?.containers?.find(c => {
              const containerName = c.Names?.[0]?.replace('/', '') || c.Name || '';
              return (
                containerName.includes(machine.machine_id.substring(0, 8)) ||
                containerName.includes(machine.machine_id) ||
                containerName.startsWith('hackforge_machine_')
              );
            });

            return (
              <div key={machine.machine_id} className="mb-4 p-4 bg-black rounded border border-gray-800">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-400">Machine ID:</p>
                    <code className="text-orange-500 text-xs">{machine.machine_id}</code>
                    <p className="text-sm text-gray-400 mt-2">Variant:</p>
                    <p className="text-white">{machine.variant}</p>
                  </div>
                  <div>
                    {container ? (
                      <>
                        <div className="flex items-center gap-2 mb-2">
                          <CheckCircle className="w-4 h-4 text-green-500" />
                          <span className="text-green-500 font-semibold">Container Found</span>
                        </div>
                        <p className="text-sm text-gray-400">Container ID:</p>
                        <code className="text-blue-500 text-xs">{container.Id || container.ID}</code>
                        <p className="text-sm text-gray-400 mt-2">Container Name:</p>
                        <code className="text-blue-500 text-xs">
                          {container.Names?.[0] || container.Name}
                        </code>
                        <p className="text-sm text-gray-400 mt-2">Status:</p>
                        <span className={`text-xs font-semibold ${
                          container.State === 'running' ? 'text-green-500' : 'text-gray-500'
                        }`}>
                          {container.State}
                        </span>
                        <button
                          onClick={() => testContainerAction(container.Id || container.ID)}
                          className="mt-3 px-4 py-2 bg-green-600 hover:bg-green-700 rounded text-sm"
                        >
                          Test Start
                        </button>
                      </>
                    ) : (
                      <div className="flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-red-500" />
                        <span className="text-red-500 font-semibold">No Container Found</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Test Result */}
        {testResult && (
          <div className={`p-6 rounded-xl border ${
            testResult.success 
              ? 'bg-green-950/20 border-green-500/50' 
              : testResult.loading
              ? 'bg-blue-950/20 border-blue-500/50'
              : 'bg-red-950/20 border-red-500/50'
          }`}>
            <h2 className="text-xl font-bold mb-4">Test Result</h2>
            <pre className="text-xs bg-black p-4 rounded overflow-auto">
              {testResult.message}
            </pre>
          </div>
        )}

        {/* API Test */}
        <div className="p-6 bg-gray-900 rounded-xl border border-gray-800">
          <h2 className="text-xl font-bold mb-4 text-orange-500">API Service Test</h2>
          <div className="space-y-2">
            <p className="text-sm">
              <span className="text-gray-400">API Object Type:</span>{' '}
              <code className="text-green-500">{typeof api}</code>
            </p>
            <p className="text-sm">
              <span className="text-gray-400">startContainer Method:</span>{' '}
              <code className="text-green-500">{typeof api.startContainer}</code>
            </p>
            <p className="text-sm">
              <span className="text-gray-400">stopContainer Method:</span>{' '}
              <code className="text-green-500">{typeof api.stopContainer}</code>
            </p>
            <p className="text-sm">
              <span className="text-gray-400">API Methods:</span>{' '}
              <code className="text-blue-500 text-xs">
                {Object.keys(api).filter(k => typeof api[k] === 'function').join(', ')}
              </code>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ContainerDebug;
