/**
 * Dashboard Page
 *
 * Shows current system status:
 * - GPU information and driver version
 * - Monitor configuration
 * - Memory and CPU status
 * - Recent issues
 */

import * as api from '../api/client.js';
import { showLoading, formatDate, showNotification } from '../main.js';

export async function initDashboard() {
  console.log('Loading dashboard...');

  try {
    const hwStatus = await api.getCurrentHardware();

    // Load GPU status
    loadGPUStatus(hwStatus);

    // Load monitors
    loadMonitorStatus(hwStatus);

    // Load memory
    loadMemoryStatus(hwStatus);

    // Load CPU
    loadCPUStatus(hwStatus);

    // Load recent issues
    loadRecentIssues();
  } catch (error) {
    console.error('Dashboard load error:', error);
    showNotification(`Failed to load dashboard: ${error}`, 'error');
  }
}

function loadGPUStatus(hwStatus: any) {
  const container = document.getElementById('gpu-status');
  if (!container) return;

  if (!hwStatus.gpu) {
    container.innerHTML = '<p class="loading">No GPU data available</p>';
    return;
  }

  const gpu = hwStatus.gpu;
  const html = `
    <div class="status-item">
      <span class="status-label">GPU:</span>
      <span class="status-value">${gpu.gpu_name || 'Unknown'}</span>
    </div>
    <div class="status-item">
      <span class="status-label">Driver:</span>
      <span class="status-value">${gpu.driver_version || 'Unknown'}</span>
    </div>
    ${
      gpu.vram_total_mb
        ? `<div class="status-item">
      <span class="status-label">VRAM:</span>
      <span class="status-value">${gpu.vram_total_mb} MB</span>
    </div>`
        : ''
    }
    ${
      gpu.temperature_c
        ? `<div class="status-item">
      <span class="status-label">Temperature:</span>
      <span class="status-value">${gpu.temperature_c.toFixed(1)}°C</span>
    </div>`
        : ''
    }
  `;

  container.innerHTML = html;
}

function loadMonitorStatus(hwStatus: any) {
  const container = document.getElementById('monitors-status');
  if (!container) return;

  const monitors = hwStatus.monitors || [];

  if (monitors.length === 0) {
    container.innerHTML = '<p class="loading">No monitors detected</p>';
    return;
  }

  let html = `<div class="status-item">
    <span class="status-label">Count:</span>
    <span class="status-value">${monitors.length}</span>
  </div>`;

  monitors.forEach((mon: any, idx: number) => {
    if (idx === 0) return; // Skip first, it's the count

    html += `
      <div class="status-item">
        <span class="status-label">${mon.monitor_name}:</span>
        <span class="status-value">${mon.connection_type || 'Unknown'}</span>
      </div>
    `;
  });

  container.innerHTML = html;
}

function loadMemoryStatus(hwStatus: any) {
  const container = document.getElementById('memory-status');
  if (!container) return;

  if (!hwStatus.memory) {
    container.innerHTML = '<p class="loading">No memory data available</p>';
    return;
  }

  const memData = JSON.parse(hwStatus.memory);

  const html = `
    <div class="status-item">
      <span class="status-label">Total:</span>
      <span class="status-value">${memData.total_gb} GB</span>
    </div>
    <div class="status-item">
      <span class="status-label">Used:</span>
      <span class="status-value">${memData.used_gb} GB</span>
    </div>
    <div class="status-item">
      <span class="status-label">Free:</span>
      <span class="status-value">${memData.free_gb} GB (${memData.percent_free}%)</span>
    </div>
  `;

  container.innerHTML = html;
}

function loadCPUStatus(hwStatus: any) {
  const container = document.getElementById('cpu-status');
  if (!container) return;

  if (!hwStatus.cpu) {
    container.innerHTML = '<p class="loading">No CPU data available</p>';
    return;
  }

  const cpuData = JSON.parse(hwStatus.cpu);

  const html = `
    <div class="status-item">
      <span class="status-label">Name:</span>
      <span class="status-value">${cpuData.name || 'Unknown'}</span>
    </div>
    <div class="status-item">
      <span class="status-label">Cores:</span>
      <span class="status-value">${cpuData.cores || 'Unknown'}</span>
    </div>
    <div class="status-item">
      <span class="status-label">Logical Processors:</span>
      <span class="status-value">${cpuData.logical_processors || 'Unknown'}</span>
    </div>
  `;

  container.innerHTML = html;
}

async function loadRecentIssues() {
  const container = document.getElementById('recent-issues-list');
  if (!container) return;

  showLoading('recent-issues-list');

  try {
    const issues = await api.getIssues(5);

    if (issues.length === 0) {
      container.innerHTML = '<p class="loading">No issues logged yet</p>';
      return;
    }

    let html = '';
    issues.forEach((issue: api.Issue) => {
      html += `
        <div class="issue-item severity-${issue.severity}">
          <div class="issue-type">${formatIssueType(issue.issue_type)}</div>
          <div class="issue-description">${escapeHtml(issue.description)}</div>
          <div class="issue-meta">
            <span>${formatDate(issue.timestamp)}</span>
            <span class="issue-severity">${issue.severity}</span>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  } catch (error) {
    container.innerHTML = `<p class="error">Failed to load issues: ${error}</p>`;
  }
}

function formatIssueType(type: string): string {
  return type
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
