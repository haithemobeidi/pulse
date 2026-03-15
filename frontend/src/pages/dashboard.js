import * as api from '../api/client.js';
import { showLoading, formatDate, formatTimeShort } from '../main.js';

let historyClicksSetup = false;
const historyLoaded = { gpu: false, monitors: false };

export async function initDashboard() {
  console.log('Loading dashboard...');

  // Set up clickable hardware cards FIRST (only once)
  if (!historyClicksSetup) {
    historyClicksSetup = true;
    setupHardwareCardClicks();
  }

  // Then load data
  const hwData = await loadHardwareStatus();
  await loadRecentIssues();

  // Build health summary from loaded data
  if (hwData) buildHealthSummary(hwData);

  // Start live stats polling (every 5 seconds)
  startLiveStats();
}

let liveInterval = null;

function startLiveStats() {
  if (liveInterval) clearInterval(liveInterval);
  updateLiveStats(); // immediate first update
  liveInterval = setInterval(updateLiveStats, 5000);

  // Expose stop function globally so navigation can call it
  window.stopLiveStats = () => {
    if (liveInterval) {
      clearInterval(liveInterval);
      liveInterval = null;
    }
  };
}

async function updateLiveStats() {
  try {
    const resp = await fetch('http://localhost:5000/api/live-stats');
    const stats = await resp.json();

    // Helper to update a data-live element
    function setLive(key, value) {
      const el = document.querySelector(`[data-live="${key}"]`);
      if (el) el.textContent = value;
    }

    // Update card values
    if (stats.cpu_percent !== undefined) {
      setLive('cpu-usage', `${stats.cpu_percent}%`);
    }
    if (stats.ram_used_gb !== undefined) {
      setLive('ram-used', `${stats.ram_used_gb} GB (${stats.ram_percent}%)`);
      setLive('ram-available', `${(stats.ram_total_gb - stats.ram_used_gb).toFixed(1)}`);
    }
    if (stats.gpu_temp !== undefined) {
      setLive('gpu-temp', `${stats.gpu_temp}°C`);
    }
    if (stats.gpu_vram_used_mb !== undefined) {
      const usedGb = (stats.gpu_vram_used_mb / 1024).toFixed(1);
      setLive('gpu-vram', `${usedGb} GB (${stats.gpu_vram_percent}%)`);
    }
    if (stats.gpu_usage !== undefined) {
      setLive('gpu-usage', `${stats.gpu_usage}%`);
    }

    // Update health bar
    const healthEl = document.getElementById('health-content');
    if (!healthEl) return;

    const items = healthEl.querySelectorAll('.health-item');
    items.forEach(item => {
      const text = item.textContent;
      if (text.includes('GPU') && text.includes('°C') && stats.gpu_temp !== undefined) {
        const dot = stats.gpu_temp > 85 ? 'red' : stats.gpu_temp > 70 ? 'yellow' : 'green';
        item.innerHTML = `<span class="health-dot ${dot}"></span>GPU ${stats.gpu_temp}°C`;
      }
      if (text.includes('CPU') && stats.cpu_percent !== undefined) {
        const dot = stats.cpu_percent > 90 ? 'red' : stats.cpu_percent > 70 ? 'yellow' : 'green';
        item.innerHTML = `<span class="health-dot ${dot}"></span>CPU ${stats.cpu_percent}%`;
      }
      if (text.includes('RAM') && stats.ram_percent !== undefined) {
        const dot = stats.ram_percent > 90 ? 'red' : stats.ram_percent > 75 ? 'yellow' : 'green';
        item.innerHTML = `<span class="health-dot ${dot}"></span>RAM ${stats.ram_percent}% (${stats.ram_used_gb}/${stats.ram_total_gb} GB)`;
      }
    });
  } catch (e) {
    // Silently fail — don't spam errors for polling
  }
}

function setupHardwareCardClicks() {
  document.querySelectorAll('.hw-card[data-component]').forEach((card) => {
    const component = card.dataset.component;
    const panel = card.querySelector('.hw-history-panel');
    if (!panel) return;

    card.addEventListener('click', async (e) => {
      // Don't toggle if clicking a link, button, or table cell
      if (e.target.closest('a, button, td, th')) return;

      panel.classList.toggle('hidden');
      card.classList.toggle('expanded');

      const justOpened = !panel.classList.contains('hidden');
      if (justOpened && !historyLoaded[component]) {
        historyLoaded[component] = true;
        if (component === 'gpu') await loadGPUHistory();
        if (component === 'monitors') await loadMonitorHistory();
      }
    });
  });
}

async function loadGPUHistory() {
  const container = document.getElementById('gpu-history');
  if (!container) return;

  try {
    const history = await api.getGPUHistory(20);

    if (history.length === 0) {
      container.innerHTML = '<p class="loading">No GPU history yet. Collect data to start tracking.</p>';
      return;
    }

    let lastDriver = '';
    let html = '';

    history.forEach((gpu, idx) => {
      const changed = idx > 0 && gpu.driver_version !== lastDriver;
      html += `
        <div class="history-item ${changed ? 'changed' : ''}">
          <div class="history-time">${formatDate(gpu.timestamp || new Date().toISOString())}</div>
          <div class="history-content">
<strong>${escapeHtml(gpu.gpu_name)}</strong>
Driver: ${escapeHtml(gpu.driver_version || 'Unknown')}
${gpu.vram_total_mb ? `VRAM: ${(gpu.vram_total_mb / 1024).toFixed(1)} GB` : ''}
${gpu.temperature_c ? `Temp: ${gpu.temperature_c}°C` : ''}
${changed ? '<span style="color:var(--warning);font-weight:bold;">DRIVER CHANGED</span>' : ''}
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

  try {
    const history = await api.getMonitorHistory(30);

    if (history.length === 0) {
      container.innerHTML = '<p class="loading">No monitor history yet. Collect data to start tracking.</p>';
      return;
    }

    const bySnapshot = {};
    history.forEach((mon) => {
      const key = mon.timestamp || 'unknown';
      if (!bySnapshot[key]) bySnapshot[key] = [];
      bySnapshot[key].push(mon);
    });

    let html = '';
    const sorted = Object.entries(bySnapshot).sort(
      ([ts1], [ts2]) => new Date(ts2).getTime() - new Date(ts1).getTime()
    );

    sorted.forEach(([timestamp, monitors]) => {
      html += `
        <div class="history-item">
          <div class="history-time">${formatDate(timestamp)}</div>
          <div class="history-content">
${monitors.map((m) => `<div>${escapeHtml(m.monitor_name)} - ${escapeHtml(m.connection_type)} (${m.status})</div>`).join('')}
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  } catch (error) {
    container.innerHTML = `<p class="error">Failed to load monitor history: ${error}</p>`;
  }
}

async function loadHardwareStatus() {
  try {
    const hardware = await api.getCurrentHardware();

    if (hardware.status === 'no_data') {
      document.getElementById('gpu-status').innerHTML = '<p>No data yet. Click "Collect Data".</p>';
      document.getElementById('monitors-status').innerHTML = '<p>No data yet. Click "Collect Data".</p>';
      document.getElementById('memory-status').innerHTML = '<p>No data yet. Click "Collect Data".</p>';
      document.getElementById('cpu-status').innerHTML = '<p>No data yet. Click "Collect Data".</p>';
      return null;
    }

    // GPU Status
    const gpuHtml = hardware.gpu
      ? `
        <div class="hw-item">
          <p><strong>Model:</strong> ${escapeHtml(hardware.gpu.gpu_name || 'Unknown')}</p>
          <p><strong>Driver:</strong> ${escapeHtml(hardware.gpu.driver_version || 'Unknown')}</p>
          <p><strong>VRAM:</strong> ${hardware.gpu.vram_total_mb ? (hardware.gpu.vram_total_mb / 1024).toFixed(1) : 'Unknown'} GB</p>
          <p><strong>VRAM Used:</strong> <span data-live="gpu-vram">${hardware.gpu.vram_used_mb ? `${(hardware.gpu.vram_used_mb / 1024).toFixed(1)} GB (${((hardware.gpu.vram_used_mb / hardware.gpu.vram_total_mb * 100) || 0).toFixed(1)}%)` : '—'}</span></p>
          <p><strong>Temp:</strong> <span data-live="gpu-temp">${hardware.gpu.temperature_c ? `${hardware.gpu.temperature_c}°C` : '—'}</span></p>
          <p><strong>GPU Load:</strong> <span data-live="gpu-usage">—</span></p>
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
    let memoryHtml = '<p>No memory data available</p>';
    if (memoryData) {
      let sticksHtml = '';
      if (memoryData.sticks && memoryData.sticks.length > 0) {
        sticksHtml = `
          <div class="ram-sticks">
            <p><strong>Configuration:</strong> ${memoryData.slots_used || memoryData.sticks.length} of ${memoryData.slots_total || '?'} slots used</p>
            <table class="hw-table">
              <thead><tr><th>Slot</th><th>Size</th><th>Speed</th><th>Type</th><th>Manufacturer</th><th>Part #</th></tr></thead>
              <tbody>
                ${memoryData.sticks.map(s => `
                  <tr>
                    <td>${escapeHtml(s.slot || '—')}</td>
                    <td>${s.capacity_gb || '?'} GB</td>
                    <td>${s.speed_mhz || '?'} MHz</td>
                    <td>${escapeHtml(s.type || '?')}</td>
                    <td>${escapeHtml(s.manufacturer || '—')}</td>
                    <td>${escapeHtml(s.part_number || '—')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>`;
      }
      memoryHtml = `
        <div class="hw-item">
          <p><strong>Total:</strong> ${memoryData.total_gb || 'Unknown'} GB ${memoryData.memory_type ? `(${memoryData.memory_type})` : ''}</p>
          <p><strong>Available:</strong> <span data-live="ram-available">${memoryData.available_gb || 'Unknown'}</span> GB</p>
          <p><strong>Used:</strong> <span data-live="ram-used">${memoryData.used_gb || 'Unknown'} GB (${memoryData.percent_used || 'Unknown'}%)</span></p>
          ${sticksHtml}
        </div>
      `;
    }
    document.getElementById('memory-status').innerHTML = memoryHtml;

    // CPU Status
    const cpuData = hardware.cpu ? JSON.parse(hardware.cpu) : null;
    let cpuHtml = '<p>No CPU data available</p>';
    if (cpuData) {
      cpuHtml = `
        <div class="hw-item">
          ${cpuData.name ? `<p><strong>Model:</strong> ${escapeHtml(cpuData.name)}</p>` : ''}
          ${cpuData.architecture ? `<p><strong>Architecture:</strong> ${escapeHtml(cpuData.architecture)}</p>` : ''}
          <p><strong>Cores:</strong> ${cpuData.physical_cores || 'Unknown'} cores / ${cpuData.logical_processors || 'Unknown'} threads</p>
          <p><strong>Usage:</strong> <span data-live="cpu-usage">${cpuData.usage_percent || 'Unknown'}%</span></p>
          <p><strong>Base Frequency:</strong> ${cpuData.frequency_mhz ? (cpuData.frequency_mhz / 1000).toFixed(2) : 'Unknown'} GHz</p>
          ${cpuData.max_frequency_mhz ? `<p><strong>Max Frequency:</strong> ${(cpuData.max_frequency_mhz / 1000).toFixed(2)} GHz</p>` : ''}
          ${cpuData.l3_cache_mb ? `<p><strong>L3 Cache:</strong> ${cpuData.l3_cache_mb} MB</p>` : ''}
          ${cpuData.socket ? `<p><strong>Socket:</strong> ${escapeHtml(cpuData.socket)}</p>` : ''}
        </div>
      `;
    }
    document.getElementById('cpu-status').innerHTML = cpuHtml;

    // Motherboard Status
    const mbData = hardware.motherboard ? JSON.parse(hardware.motherboard) : null;
    let mbHtml = '<p>No motherboard data available</p>';
    if (mbData) {
      // Format BIOS date from WMI format (20241205000000.000000+000) to readable
      let biosDate = mbData.bios_date || '';
      if (biosDate && biosDate.length >= 8) {
        const y = biosDate.substring(0, 4);
        const m = biosDate.substring(4, 6);
        const d = biosDate.substring(6, 8);
        biosDate = `${m}/${d}/${y}`;
      }

      mbHtml = `
        <div class="hw-item">
          ${mbData.manufacturer ? `<p><strong>Manufacturer:</strong> ${escapeHtml(mbData.manufacturer)}</p>` : ''}
          ${mbData.product ? `<p><strong>Model:</strong> ${escapeHtml(mbData.product)}</p>` : ''}
          ${mbData.version ? `<p><strong>Version:</strong> ${escapeHtml(mbData.version)}</p>` : ''}
          ${mbData.bios_version ? `<p><strong>BIOS:</strong> ${escapeHtml(mbData.bios_version)}${biosDate ? ` (${biosDate})` : ''}</p>` : ''}
          ${mbData.serial ? `<p><strong>Serial:</strong> ${escapeHtml(mbData.serial)}</p>` : ''}
        </div>
      `;
    }
    document.getElementById('motherboard-status').innerHTML = mbHtml;

    // Storage Status
    const storageData = hardware.storage ? JSON.parse(hardware.storage) : null;
    let storageHtml = '<p>No storage data available</p>';
    if (storageData) {
      let drivesHtml = '';
      if (storageData.drives && storageData.drives.length > 0) {
        drivesHtml = storageData.drives.map(d => `
          <div style="margin-bottom:8px;padding:6px 0;border-bottom:1px solid var(--border);">
            <p><strong>${escapeHtml(d.model || 'Unknown Drive')}</strong> <span style="color:var(--accent);">${escapeHtml(d.drive_type || '')}</span></p>
            <p style="color:var(--text-secondary);font-size:12px;">
              ${d.size_gb ? `${d.size_gb} GB` : ''}
              ${d.interface ? ` | ${escapeHtml(d.interface)}` : ''}
              ${d.firmware ? ` | FW: ${escapeHtml(d.firmware)}` : ''}
            </p>
          </div>
        `).join('');
      }

      let partitionsHtml = '';
      if (storageData.partitions && storageData.partitions.length > 0) {
        partitionsHtml = '<div style="margin-top:8px;">' + storageData.partitions.map(p => {
          const pct = p.percent_used || 0;
          const barColor = pct > 90 ? 'var(--error)' : pct > 70 ? 'var(--warning)' : 'var(--success)';
          return `
            <div style="margin-bottom:6px;">
              <div style="display:flex;justify-content:space-between;font-size:12px;">
                <span><strong>${escapeHtml(p.mount)}</strong> (${escapeHtml(p.fstype || '')})</span>
                <span>${p.free_gb} GB free of ${p.total_gb} GB</span>
              </div>
              <div style="height:4px;background:var(--bg-tertiary);border-radius:2px;margin-top:3px;">
                <div style="height:100%;width:${pct}%;background:${barColor};border-radius:2px;"></div>
              </div>
            </div>
          `;
        }).join('') + '</div>';
      }

      storageHtml = `<div class="hw-item">${drivesHtml}${partitionsHtml}</div>`;
    }
    document.getElementById('storage-status').innerHTML = storageHtml;

    // Network Status
    const netData = hardware.network ? JSON.parse(hardware.network) : null;
    let netHtml = '<p>No network data available</p>';
    if (netData && netData.adapters && netData.adapters.length > 0) {
      netHtml = '<div class="hw-item">' + netData.adapters.map(a => {
        const statusColor = a.status === 'Connected' ? 'var(--success)' : 'var(--text-secondary)';
        return `
          <div style="margin-bottom:8px;padding:6px 0;border-bottom:1px solid var(--border);">
            <p><strong>${escapeHtml(a.name || 'Unknown')}</strong></p>
            <p style="color:var(--text-secondary);font-size:12px;">
              <span style="color:${statusColor};">${a.status || 'Unknown'}</span>
              ${a.connection_name ? ` | ${escapeHtml(a.connection_name)}` : ''}
              ${a.speed_mbps ? ` | ${a.speed_mbps >= 1000 ? (a.speed_mbps / 1000) + ' Gbps' : a.speed_mbps + ' Mbps'}` : ''}
              ${a.type ? ` | ${escapeHtml(a.type)}` : ''}
            </p>
          </div>
        `;
      }).join('') + '</div>';
    }
    document.getElementById('network-status').innerHTML = netHtml;

    return hardware;
  } catch (error) {
    console.error('Failed to load hardware status:', error);
    document.getElementById('gpu-status').innerHTML = `<p class="error">Error: ${error}</p>`;
    document.getElementById('monitors-status').innerHTML = `<p class="error">Error: ${error}</p>`;
    return null;
  }
}

function buildHealthSummary(hardware) {
  const container = document.getElementById('health-content');
  if (!container) return;

  const items = [];

  // GPU temp
  if (hardware.gpu && hardware.gpu.temperature_c) {
    const temp = hardware.gpu.temperature_c;
    const dot = temp > 85 ? 'red' : temp > 70 ? 'yellow' : 'green';
    items.push(`<span class="health-item"><span class="health-dot ${dot}"></span>GPU ${temp}°C</span>`);
  }

  // Memory usage
  const memData = hardware.memory ? JSON.parse(hardware.memory) : null;
  if (memData) {
    const pct = memData.percent_used || 0;
    const dot = pct > 90 ? 'red' : pct > 75 ? 'yellow' : 'green';
    items.push(`<span class="health-item"><span class="health-dot ${dot}"></span>RAM ${pct}% used (${memData.used_gb}/${memData.total_gb} GB)</span>`);
  }

  // CPU usage
  const cpuData = hardware.cpu ? JSON.parse(hardware.cpu) : null;
  if (cpuData && cpuData.usage_percent !== undefined) {
    const pct = cpuData.usage_percent;
    const dot = pct > 90 ? 'red' : pct > 70 ? 'yellow' : 'green';
    items.push(`<span class="health-item"><span class="health-dot ${dot}"></span>CPU ${pct}%</span>`);
  }

  // Storage - check for nearly full drives
  const storageData = hardware.storage ? JSON.parse(hardware.storage) : null;
  if (storageData && storageData.partitions) {
    const full = storageData.partitions.filter(p => p.percent_used > 90);
    const warn = storageData.partitions.filter(p => p.percent_used > 75 && p.percent_used <= 90);
    if (full.length > 0) {
      items.push(`<span class="health-item"><span class="health-dot red"></span>${full.length} drive(s) nearly full</span>`);
    } else if (warn.length > 0) {
      items.push(`<span class="health-item"><span class="health-dot yellow"></span>${warn.length} drive(s) >75% used</span>`);
    } else {
      items.push(`<span class="health-item"><span class="health-dot green"></span>${storageData.partitions.length} drives healthy</span>`);
    }
  }

  // Monitors
  if (hardware.monitor_count) {
    items.push(`<span class="health-item"><span class="health-dot green"></span>${hardware.monitor_count} monitor(s)</span>`);
  }

  // Network
  const netData = hardware.network ? JSON.parse(hardware.network) : null;
  if (netData && netData.adapters) {
    const connected = netData.adapters.filter(a => a.status === 'Connected').length;
    const dot = connected > 0 ? 'green' : 'red';
    items.push(`<span class="health-item"><span class="health-dot ${dot}"></span>${connected} network(s) connected</span>`);
  }

  container.innerHTML = items.join('');
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
