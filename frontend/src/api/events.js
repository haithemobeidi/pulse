/**
 * SSE Client — receives real-time progress events from the backend.
 *
 * Event types dispatched as custom DOM events:
 * - pulse:scan_progress — { step, status, detail }
 * - pulse:analysis_progress — { step, status, detail }
 * - pulse:fix_status — { fix_id, old_state, new_state, event }
 */

import { API_BASE } from '../utils.js';

let eventSource = null;
let reconnectTimer = null;
let reconnectDelay = 3000;
const MAX_RECONNECT_DELAY = 30000;

export function connectSSE() {
  if (eventSource) return;

  try {
    eventSource = new EventSource(`${API_BASE}/api/events`);

    eventSource.addEventListener('scan_progress', (e) => {
      try {
        const data = JSON.parse(e.data);
        window.dispatchEvent(new CustomEvent('pulse:scan_progress', { detail: data }));
      } catch (err) {
        console.warn('[SSE] Failed to parse scan_progress:', err);
      }
    });

    eventSource.addEventListener('analysis_progress', (e) => {
      try {
        const data = JSON.parse(e.data);
        window.dispatchEvent(new CustomEvent('pulse:analysis_progress', { detail: data }));
      } catch (err) {
        console.warn('[SSE] Failed to parse analysis_progress:', err);
      }
    });

    eventSource.addEventListener('fix_status', (e) => {
      try {
        const data = JSON.parse(e.data);
        window.dispatchEvent(new CustomEvent('pulse:fix_status', { detail: data }));
      } catch (err) {
        console.warn('[SSE] Failed to parse fix_status:', err);
      }
    });

    eventSource.onopen = () => {
      console.log('[SSE] Connected');
      reconnectDelay = 3000; // Reset on successful connection
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    eventSource.onerror = () => {
      disconnectSSE();
      console.warn(`[SSE] Connection lost, retrying in ${reconnectDelay / 1000}s...`);
      reconnectTimer = setTimeout(connectSSE, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY); // Exponential backoff
    };
  } catch (err) {
    console.warn('[SSE] Failed to connect:', err);
    reconnectTimer = setTimeout(connectSSE, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
  }
}

export function disconnectSSE() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}
