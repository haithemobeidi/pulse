/**
 * API Client for PC-Inspector Backend
 *
 * Provides typed fetch wrapper for communicating with the FastAPI backend.
 * Handles JSON serialization, error handling, and base URL configuration.
 */

const API_BASE_URL = 'http://localhost:5000';

interface RequestOptions extends RequestInit {
  body?: any;
}

/**
 * Make API request to backend
 */
export async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  const fetchOptions: RequestInit = {
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

  return response.text() as any;
}

/**
 * GET request
 */
export async function get<T>(path: string, params?: Record<string, any>): Promise<T> {
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

  return request<T>(url, { method: 'GET' });
}

/**
 * POST request
 */
export async function post<T>(path: string, body?: any): Promise<T> {
  return request<T>(path, { method: 'POST', body });
}

/**
 * PUT request
 */
export async function put<T>(path: string, body?: any): Promise<T> {
  return request<T>(path, { method: 'PUT', body });
}

/**
 * DELETE request
 */
export async function deleteRequest<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' });
}

// ============================================================================
// API Endpoints
// ============================================================================

// Snapshots

export interface Snapshot {
  id: number;
  timestamp: string;
  snapshot_type: string;
  notes?: string;
}

export interface SnapshotDetail extends Snapshot {
  gpu_info?: any;
  monitors?: any[];
  issues_count: number;
}

export function getSnapshots(limit = 50, offset = 0): Promise<Snapshot[]> {
  return get<Snapshot[]>('/api/snapshots', { limit, offset });
}

export function getSnapshot(id: number): Promise<SnapshotDetail> {
  return get<SnapshotDetail>(`/api/snapshots/${id}`);
}

export function createSnapshot(
  snapshot_type: string,
  notes?: string
): Promise<Snapshot> {
  return post<Snapshot>('/api/snapshots', { snapshot_type, notes });
}

// Hardware

export function getCurrentHardware(): Promise<any> {
  return get<any>('/api/hardware/current');
}

export function getGPUStatus(): Promise<any> {
  return get<any>('/api/hardware/gpu');
}

export function getGPUHistory(limit = 20): Promise<any[]> {
  return get<any[]>('/api/hardware/gpu/history', { limit });
}

export function getMonitorStatus(): Promise<any[]> {
  return get<any[]>('/api/hardware/monitors');
}

export function getMonitorHistory(limit = 20): Promise<any[]> {
  return get<any[]>('/api/hardware/monitors/history', { limit });
}

// Issues

export interface Issue {
  id: number;
  snapshot_id: number;
  issue_type: string;
  description: string;
  severity: string;
  timestamp: string;
}

export interface IssueWithContext extends Issue {
  gpu_state?: any;
  monitors?: any[];
  hardware_state?: any[];
}

export function getIssues(limit = 50, offset = 0): Promise<Issue[]> {
  return get<Issue[]>('/api/issues', { limit, offset });
}

export function getIssue(id: number): Promise<IssueWithContext> {
  return get<IssueWithContext>(`/api/issues/${id}`);
}

export function getIssuesByType(type: string, limit = 20): Promise<Issue[]> {
  return get<Issue[]>(`/api/issues/type/${type}`, { limit });
}

export function logIssue(
  issue_type: string,
  description: string,
  severity: string = 'medium',
  snapshot_id?: number
): Promise<Issue> {
  return post<Issue>('/api/issues', {
    issue_type,
    description,
    severity,
    snapshot_id,
  });
}

// Data Collection

export interface CollectionResult {
  status: string;
  snapshot_id?: number;
  collections?: Record<string, string>;
  error?: string;
}

export function collectAll(): Promise<CollectionResult> {
  return post<CollectionResult>('/api/collect/all');
}

export function collectHardware(): Promise<CollectionResult> {
  return post<CollectionResult>('/api/collect/hardware');
}

export function collectMonitors(): Promise<CollectionResult> {
  return post<CollectionResult>('/api/collect/monitors');
}

// Status

export interface APIStatus {
  status: string;
  database: string;
  powershell: string;
  snapshots: number;
  issues: number;
}

export function getAPIStatus(): Promise<APIStatus> {
  return get<APIStatus>('/api/status');
}
