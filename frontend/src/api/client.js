/**
 * API Client for PC-Inspector Backend
 */

const API_BASE_URL = 'http://localhost:5000';

async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;

  const fetchOptions = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };

  if (options.body && typeof options.body === 'object') {
    fetchOptions.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, fetchOptions);

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API Error: ${response.status} - ${error}`);
  }

  const contentType = response.headers.get('content-type');
  if (contentType?.includes('application/json')) {
    return response.json();
  }

  return response.text();
}

export async function get(path, params) {
  let url = path;
  if (params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== undefined) {
        query.append(key, String(value));
      }
    }
    const queryString = query.toString();
    url = queryString ? `${path}?${queryString}` : path;
  }

  return request(url, { method: 'GET' });
}

export async function post(path, body) {
  return request(path, { method: 'POST', body });
}

export async function put(path, body) {
  return request(path, { method: 'PUT', body });
}

export async function deleteRequest(path) {
  return request(path, { method: 'DELETE' });
}

// Snapshots
export function getSnapshots(limit = 50, offset = 0) {
  return get('/api/snapshots', { limit, offset });
}

export function getSnapshot(id) {
  return get(`/api/snapshots/${id}`);
}

export function createSnapshot(snapshot_type, notes) {
  return post('/api/snapshots', { snapshot_type, notes });
}

// Hardware
export function getCurrentHardware() {
  return get('/api/hardware/current');
}

export function getGPUStatus() {
  return get('/api/hardware/gpu');
}

export function getGPUHistory(limit = 20) {
  return get('/api/hardware/gpu/history', { limit });
}

export function getMonitorStatus() {
  return get('/api/hardware/monitors');
}

export function getMonitorHistory(limit = 20) {
  return get('/api/hardware/monitors/history', { limit });
}

// Issues
export function getIssues(limit = 50, offset = 0) {
  return get('/api/issues', { limit, offset });
}

export function getIssue(id) {
  return get(`/api/issues/${id}`);
}

export function getIssuesByType(type, limit = 20) {
  return get(`/api/issues/type/${type}`, { limit });
}

export function logIssue(issue_type, description, severity = 'medium', snapshot_id) {
  return post('/api/issues', {
    issue_type,
    description,
    severity,
    snapshot_id,
  });
}

// Data Collection
export function collectAll() {
  return post('/api/collect/all');
}

export function collectHardware() {
  return post('/api/collect/hardware');
}

export function collectMonitors() {
  return post('/api/collect/monitors');
}

// Status
export function getAPIStatus() {
  return get('/api/status');
}
