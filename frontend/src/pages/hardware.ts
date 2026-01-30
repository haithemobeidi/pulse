/**
 * Hardware Page
 *
 * Shows historical hardware data:
 * - GPU driver version changes
 * - Monitor connection changes
 * - Useful for correlating issues with hardware changes
 */

import * as api from '../api/client.js';
import { showLoading, formatDate } from '../main.js';

export async function initHardware() {
  console.log('Loading hardware history...');

  // Load GPU history
  await loadGPUHistory();

  // Load monitor history
  await loadMonitorHistory();
}

async function loadGPUHistory() {
  const container = document.getElementById('gpu-history');
  if (!container) return;

  showLoading('gpu-history');

  try {
    const history = await api.getGPUHistory(20);

    if (history.length === 0) {
      container.innerHTML = '<p class="loading">No GPU history available</p>';
      return;
    }

    let lastDriver = '';
    let html = '';

    history.forEach((gpu: any, idx: number) => {
      const changed = idx > 0 && gpu.driver_version !== lastDriver;

      html += `
        <div class="history-item ${changed ? 'changed' : ''}">
          <div class="history-time">${formatDate(gpu.snapshot_id || new Date().toISOString())}</div>
          <div class="history-content">
<strong>${gpu.gpu_name}</strong>
Driver: ${gpu.driver_version || 'Unknown'}
${gpu.vram_total_mb ? `VRAM: ${gpu.vram_total_mb} MB` : ''}
${gpu.temperature_c ? `Temp: ${gpu.temperature_c.toFixed(1)}°C` : ''}
${changed ? '← DRIVER UPDATED' : ''}
          </div>
        </div>
      `;

      lastDriver = gpu.driver_version;
    });

    container.innerHTML = html;
  } catch (error) {
    container.innerHTML = `<p class="error">Failed to load GPU history: ${error}</p>`;
  }
}

async function loadMonitorHistory() {
  const container = document.getElementById('monitor-history');
  if (!container) return;

  showLoading('monitor-history');

  try {
    const history = await api.getMonitorHistory(30);

    if (history.length === 0) {
      container.innerHTML = '<p class="loading">No monitor history available</p>';
      return;
    }

    // Group by snapshot for clarity
    const bySnapshot: Record<string, any[]> = {};

    history.forEach((mon: any) => {
      const key = mon.timestamp || 'unknown';
      if (!bySnapshot[key]) {
        bySnapshot[key] = [];
      }
      bySnapshot[key].push(mon);
    });

    let html = '';

    // Sort snapshots by timestamp (newest first)
    const sorted = Object.entries(bySnapshot).sort(
      ([ts1], [ts2]) =>
        new Date(ts2).getTime() - new Date(ts1).getTime()
    );

    sorted.forEach(([timestamp, monitors]) => {
      html += `
        <div class="history-item">
          <div class="history-time">${formatDate(timestamp)}</div>
          <div class="history-content">
${monitors.map((m: any) => `<div>${m.monitor_name} - ${m.connection_type} (${m.status})</div>`).join('')}
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  } catch (error) {
    container.innerHTML = `<p class="error">Failed to load monitor history: ${error}</p>`;
  }
}
