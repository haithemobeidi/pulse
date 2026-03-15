import * as api from '../api/client.js';
import { showLoading, formatDate } from '../main.js';
import { escapeHtml, formatType, API_BASE } from '../utils.js';

export async function initTimeline() {
  console.log('Loading timeline...');
  const container = document.getElementById('timeline-view');
  if (!container) return;

  showLoading('timeline-view');

  try {
    // Load reliability records - this is where driver updates, installs, crashes live
    const [reliabilityResp, issues] = await Promise.all([
      fetch(`${API_BASE}/api/reliability/recent?limit=200`).then(r => r.json()),
      api.getIssues(100),
    ]);

    const reliability = Array.isArray(reliabilityResp) ? reliabilityResp : [];

    // Build timeline items from reliability records + issues
    const timelineItems = [];

    reliability.forEach((r) => {
      timelineItems.push({
        type: 'reliability',
        category: r.record_type || 'misc_failure',
        data: r,
        timestamp: r.event_time || r.timestamp || '',
      });
    });

    issues.forEach((i) => {
      timelineItems.push({
        type: 'issue',
        category: i.issue_type,
        data: i,
        timestamp: i.timestamp || '',
      });
    });

    // Sort newest first
    timelineItems.sort((a, b) => {
      const dateA = new Date(a.timestamp).getTime() || 0;
      const dateB = new Date(b.timestamp).getTime() || 0;
      return dateB - dateA;
    });

    if (timelineItems.length === 0) {
      container.innerHTML = '<p class="loading">No timeline data yet. Click "Collect Data" on the Dashboard to scan your system.</p>';
      return;
    }

    let html = '';
    timelineItems.forEach((item) => {
      if (item.type === 'issue') {
        const issue = item.data;
        html += `
          <div class="timeline-item">
            <div class="timeline-content">
              <div class="timeline-time">${formatDate(issue.timestamp)}</div>
              <div class="timeline-title">${getIcon('issue')} Issue: ${formatType(issue.issue_type)}</div>
              <div class="timeline-desc">${escapeHtml(issue.description)}</div>
              <div class="timeline-desc" style="margin-top: 5px; color: #a0a0a0;">
                Severity: <strong>${issue.severity}</strong>
              </div>
            </div>
          </div>
        `;
      } else {
        const r = item.data;
        const category = item.category;
        html += `
          <div class="timeline-item timeline-${getCategoryClass(category)}">
            <div class="timeline-content">
              <div class="timeline-time">${formatDate(item.timestamp)}</div>
              <div class="timeline-title">${getIcon(category)} ${formatType(category)}</div>
              <div class="timeline-desc">
                <strong>${escapeHtml(r.source_name || '')}</strong>
                ${r.product_name ? ` - ${escapeHtml(r.product_name)}` : ''}
              </div>
              ${r.event_message ? `<div class="timeline-desc" style="margin-top:4px;color:#a0a0a0;font-size:12px;">${escapeHtml(r.event_message.substring(0, 300))}${r.event_message.length > 300 ? '...' : ''}</div>` : ''}
            </div>
          </div>
        `;
      }
    });

    container.innerHTML = html;
  } catch (error) {
    container.innerHTML = `<p class="error">Failed to load timeline: ${error}</p>`;
  }
}

function getIcon(category) {
  const icons = {
    app_crash: '<span style="color:#ef4444;">&#x2716;</span>',
    app_install: '<span style="color:#22c55e;">&#x2795;</span>',
    app_uninstall: '<span style="color:#f59e0b;">&#x2796;</span>',
    os_update: '<span style="color:#3b82f6;">&#x21BB;</span>',
    os_crash: '<span style="color:#dc2626;">&#x26A0;</span>',
    driver_crash: '<span style="color:#f97316;">&#x26A1;</span>',
    hardware_failure: '<span style="color:#ef4444;">&#x2699;</span>',
    misc_failure: '<span style="color:#a0a0a0;">&#x2022;</span>',
    issue: '<span style="color:#f59e0b;">&#x25CF;</span>',
  };
  return icons[category] || icons.misc_failure;
}

function getCategoryClass(category) {
  if (category.includes('crash') || category.includes('failure')) return 'error';
  if (category.includes('install')) return 'success';
  if (category.includes('update')) return 'info';
  return 'default';
}

// escapeHtml and formatType imported from utils.js
