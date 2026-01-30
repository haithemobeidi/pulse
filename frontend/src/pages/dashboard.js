import * as api from '../api/client.js';
import { showLoading, formatDate, formatTimeShort } from '../main.js';

export async function initDashboard() {
  console.log('Loading dashboard...');

  // Load hardware data
  await loadHardwareStatus();

  // Load recent issues
  await loadRecentIssues();
}

async function loadHardwareStatus() {
  try {
    const hardware = await api.getCurrentHardware();

    if (hardware.status === 'no_data') {
      document.getElementById('gpu-status').innerHTML = '<p>No data collected yet. Click "Collect Data" to start.</p>';
      document.getElementById('monitors-status').innerHTML = '<p>No data collected yet. Click "Collect Data" to start.</p>';
      document.getElementById('memory-status').innerHTML = '<p>No data collected yet. Click "Collect Data" to start.</p>';
      document.getElementById('cpu-status').innerHTML = '<p>No data collected yet. Click "Collect Data" to start.</p>';
      return;
    }

    // GPU Status
    const gpuHtml = hardware.gpu
      ? `
        <div class="hw-item">
          <p><strong>Model:</strong> ${escapeHtml(hardware.gpu.gpu_name || 'Unknown')}</p>
          <p><strong>Driver:</strong> ${escapeHtml(hardware.gpu.driver_version || 'Unknown')}</p>
          <p><strong>VRAM:</strong> ${hardware.gpu.vram_total_mb ? (hardware.gpu.vram_total_mb / 1024).toFixed(1) : 'Unknown'} GB</p>
          ${hardware.gpu.vram_used_mb ? `<p><strong>VRAM Used:</strong> ${(hardware.gpu.vram_used_mb / 1024).toFixed(1)} GB (${((hardware.gpu.vram_used_mb / hardware.gpu.vram_total_mb * 100) || 0).toFixed(1)}%)</p>` : ''}
          ${hardware.gpu.temperature_c ? `<p><strong>Temp:</strong> ${hardware.gpu.temperature_c}°C</p>` : ''}
        </div>
      `
      : '<p>No GPU data available</p>';
    document.getElementById('gpu-status').innerHTML = gpuHtml;

    // Monitors Status
    const monitorsHtml =
      hardware.monitor_count > 0
        ? `
        <div class="hw-item">
          <p><strong>Connected:</strong> ${hardware.monitor_count}</p>
          <ul class="monitor-list">
            ${hardware.monitors.map((m) => `<li>${escapeHtml(m.monitor_name || 'Unknown')} (${escapeHtml(m.connection_type || 'Unknown')})</li>`).join('')}
          </ul>
        </div>
      `
        : '<p>No monitors detected</p>';
    document.getElementById('monitors-status').innerHTML = monitorsHtml;

    // Memory Status
    const memoryData = hardware.memory ? JSON.parse(hardware.memory) : null;
    const memoryHtml = memoryData
      ? `
        <div class="hw-item">
          <p><strong>Total:</strong> ${memoryData.total_gb || 'Unknown'} GB</p>
          <p><strong>Available:</strong> ${memoryData.available_gb || 'Unknown'} GB</p>
          <p><strong>Used:</strong> ${memoryData.percent_used || 'Unknown'}%</p>
        </div>
      `
      : '<p>No memory data available</p>';
    document.getElementById('memory-status').innerHTML = memoryHtml;

    // CPU Status
    const cpuData = hardware.cpu ? JSON.parse(hardware.cpu) : null;
    const cpuHtml = cpuData
      ? `
        <div class="hw-item">
          <p><strong>Cores:</strong> ${cpuData.physical_cores || 'Unknown'} cores / ${cpuData.logical_processors || 'Unknown'} threads</p>
          <p><strong>Usage:</strong> ${cpuData.usage_percent || 'Unknown'}%</p>
          <p><strong>Base Frequency:</strong> ${cpuData.frequency_mhz ? (cpuData.frequency_mhz / 1000).toFixed(2) : 'Unknown'} GHz</p>
          ${cpuData.max_frequency_mhz ? `<p><strong>Max Frequency:</strong> ${(cpuData.max_frequency_mhz / 1000).toFixed(2)} GHz</p>` : ''}
        </div>
      `
      : '<p>No CPU data available</p>';
    document.getElementById('cpu-status').innerHTML = cpuHtml;
  } catch (error) {
    console.error('Failed to load hardware status:', error);
    document.getElementById('gpu-status').innerHTML = `<p class="error">Error: ${error}</p>`;
    document.getElementById('monitors-status').innerHTML = `<p class="error">Error: ${error}</p>`;
  }
}

async function loadRecentIssues() {
  try {
    const issues = await api.getIssues(5);

    const container = document.getElementById('recent-issues-list');
    if (!container) return;

    if (issues.length === 0) {
      container.innerHTML = '<p class="loading">No issues logged yet</p>';
      return;
    }

    let html = '';
    issues.forEach((issue) => {
      html += `
        <div class="issue-item severity-${issue.severity}">
          <div class="issue-type">${formatIssueType(issue.issue_type)}</div>
          <div class="issue-description">${escapeHtml(issue.description).substring(0, 100)}${issue.description.length > 100 ? '...' : ''}</div>
          <div class="issue-meta">
            <span>${formatTimeShort(issue.timestamp)}</span>
            <span class="issue-severity">${issue.severity}</span>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  } catch (error) {
    console.error('Failed to load recent issues:', error);
  }
}

function formatIssueType(type) {
  return type.split('_').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}
