// src/services/api.js - Enhanced API Service
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ─── Flag validation constants (must mirror flags.py exactly) ────────────────
const FLAG_MAX_LENGTH = 50;
const FLAG_PATTERN = /^HACKFORGE\{[a-zA-Z0-9_\-.!@#$%^&*()[\]+=?/,]{1,40}\}$/;


// ─── Frontend flag validator ──────────────────────────────────────────────────
// Runs before any network request is made, saving a round-trip and giving the
// user instant, precise feedback.
//
// Returns: { valid: true, cleaned: '...' }
//       or { valid: false, error: 'Human-readable message' }

const validateFlagLocally = (rawFlag) => {
  if (typeof rawFlag !== 'string') {
    return { valid: false, error: 'Flag must be a string.' };
  }

  const cleaned = rawFlag.trim();

  if (!cleaned) {
    return { valid: false, error: 'Please enter a flag before submitting.' };
  }

  if (cleaned.length > FLAG_MAX_LENGTH) {
    return {
      valid: false,
      error: `Flag is too long (max ${FLAG_MAX_LENGTH} characters).`,
    };
  }

  if (!FLAG_PATTERN.test(cleaned)) {
    return {
      valid: false,
      error: 'Invalid flag format. Expected: HACKFORGE{...}',
    };
  }

  return { valid: true, cleaned };
};


class APIService {
  // ── Auth helper ─────────────────────────────────────────────────────────────
  // Attaches the JWT stored in localStorage to every request so the backend
  // can verify the caller's identity.
  _authHeaders() {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  // ── Core request helper ──────────────────────────────────────────────────────
  async request(endpoint, options = {}) {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...this._authHeaders(),
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'API request failed' }));

        // Surface the Retry-After header from rate-limit responses so callers
        // can display an accurate cooldown countdown to the user.
        if (response.status === 429) {
          const retryAfter = response.headers.get('Retry-After');
          const err = new Error(error.detail || 'Too many attempts. Please wait before retrying.');
          err.status = 429;
          err.retryAfter = retryAfter ? parseInt(retryAfter, 10) : 60;
          throw err;
        }

        throw new Error(error.detail || 'API request failed');
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error (${endpoint}):`, error);
      throw error;
    }
  }

  // ── Stats & Dashboard ────────────────────────────────────────────────────────
  async getStats(userId = null) {
    const query = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
    return this.request(`/api/stats${query}`);
  }

  async getPlatformStats() {
    return this.request('/api/statistics');
  }

  // ── Campaigns ────────────────────────────────────────────────────────────────
  async deleteCampaign(campaignId) {
    return this.request(`/api/campaigns/${campaignId}`, { method: 'DELETE' });
  }

  async createCampaign(userId, campaignName, difficulty, count = null) {
    const payload = {
      user_id: userId,
      campaign_name: campaignName,
      difficulty,
      count,
    };

    return this.request('/api/campaigns', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getUserCampaigns(userId) {
    return this.request(`/api/users/${encodeURIComponent(userId)}/campaigns`);
  }

  async getCampaign(campaignId) {
    return this.request(`/api/campaigns/${campaignId}`);
  }

  async getCampaignMachines(campaignId) {
    return this.request(`/api/campaigns/${campaignId}/machines`);
  }

  async getCampaignProgress(campaignId, userId) {
    return this.request(`/api/campaigns/${campaignId}/progress?user_id=${encodeURIComponent(userId)}`);
  }


  // ── Machines ─────────────────────────────────────────────────────────────────
  async getMachines() {
    return this.request('/api/machines');
  }

  async getMachine(machineId) {
    return this.request(`/api/machines/${machineId}`);
  }

  async getMachineStats(machineId) {
    return this.request(`/api/machines/${machineId}/stats`);
  }

  // ── Flag validation ───────────────────────────────────────────────────────────
  /**
   * Submit a flag for validation.
   *
   * Validation happens in two layers:
   *   1. Client-side (instant, no network): format, length, allowed characters.
   *   2. Server-side (authoritative):        same rules + rate limiting.
   *
   * If the client-side check fails, an error is thrown immediately so the UI
   * can show the message without waiting for a network round-trip.
   *
   * The error thrown for a rate-limit (HTTP 429) carries:
   *   error.status      = 429
   *   error.retryAfter  = seconds until the user can try again
   *
   * @param {string} machineId
   * @param {string} flag        Raw user input (will be trimmed here and on server)
   * @param {string} userId
   */
  async validateFlag(machineId, flag, userId) {
    // ── Layer 1: client-side validation ─────────────────────────────────────
    const check = validateFlagLocally(flag);
    if (!check.valid) {
      // Throw in the same shape as server errors so CampaignDetail.jsx can
      // display it with the same error-handling code path.
      throw new Error(check.error);
    }

    // ── Layer 2: server-side validation + rate limiting ──────────────────────
    return this.request('/api/flags/validate', {
      method: 'POST',
      body: JSON.stringify({
        machine_id: machineId,
        flag: check.cleaned,   // send the trimmed value
        user_id: userId,
      }),
    });
  }

  // ── Docker — global ───────────────────────────────────────────────────────────
  async startContainers() {
    return this.request('/api/docker/start', { method: 'POST' });
  }

  async stopContainers() {
    return this.request('/api/docker/stop', { method: 'POST' });
  }

  async restartContainers() {
    return this.request('/api/docker/restart', { method: 'POST' });
  }

  async destroyContainers() {
    return this.request('/api/docker/destroy', { method: 'DELETE' });
  }

  async getDockerStatus() {
    return this.request('/api/docker/status');
  }

  async getCampaignContainers(campaignId) {
    return this.request(`/api/docker/campaign/${campaignId}/containers`);
  }

  // ── Docker — individual containers ───────────────────────────────────────────
  async startContainer(containerId) {
    return this.request(`/api/docker/container/${containerId}/start`, { method: 'POST' });
  }

  async stopContainer(containerId) {
    return this.request(`/api/docker/container/${containerId}/stop`, { method: 'POST' });
  }

  async restartContainer(containerId) {
    return this.request(`/api/docker/container/${containerId}/restart`, { method: 'POST' });
  }

  async removeContainer(containerId) {
    return this.request(`/api/docker/container/${containerId}`, { method: 'DELETE' });
  }

  async getContainerLogs(containerId, tail = 100) {
    return this.request(`/api/docker/container/${containerId}/logs?tail=${tail}`);
  }

  // ── Docker — individual machines ─────────────────────────────────────────────
  async startMachineContainer(machineId) {
    return this.request(`/api/machines/${machineId}/docker/start`, { method: 'POST' });
  }

  async stopMachineContainer(machineId) {
    return this.request(`/api/machines/${machineId}/docker/stop`, { method: 'POST' });
  }

  async restartMachineContainer(machineId) {
    return this.request(`/api/machines/${machineId}/docker/restart`, { method: 'POST' });
  }

  async getMachineContainerStatus(machineId) {
    return this.request(`/api/machines/${machineId}/docker/status`);
  }

  async getMachineContainerLogs(machineId, tail = 100) {
    return this.request(`/api/machines/${machineId}/docker/logs?tail=${tail}`);
  }

  // ── Docker — campaign-level ───────────────────────────────────────────────────
  async startCampaignContainers(campaignId) {
    return this.request(`/api/campaigns/${campaignId}/docker/start`, { method: 'POST' });
  }

  async stopCampaignContainers(campaignId) {
    return this.request(`/api/campaigns/${campaignId}/docker/stop`, { method: 'POST' });
  }

  // ── Users ─────────────────────────────────────────────────────────────────────
  async createUser(username, email, role = 'individual') {
    return this.request('/api/users', {
      method: 'POST',
      body: JSON.stringify({ username, email, role }),
    });
  }

  async getUser(userId) {
    return this.request(`/api/users/${encodeURIComponent(userId)}`);
  }

  async getUserProgress(userId) {
    return this.request(`/api/users/${encodeURIComponent(userId)}/progress`);
  }

  // ── Leaderboard ───────────────────────────────────────────────────────────────
  async getLeaderboard(limit = 100, timeframe = 'all_time') {
    return this.request(`/api/leaderboard?limit=${limit}&timeframe=${timeframe}`);
  }


  // ── Health Check ──────────────────────────────────────────────────────────────
  async healthCheck() {
    return this.request('/health');
  }
}

// Singleton export
const apiService = new APIService();
export default apiService;
