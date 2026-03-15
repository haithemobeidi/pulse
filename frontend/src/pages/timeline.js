/**
 * Timeline page — color-coded, filterable system event timeline.
 *
 * Categories:
 *   system  (blue)   — driver installs, OS updates, app installs/uninstalls
 *   crash   (red)    — app crashes, driver crashes, OS crashes, hardware failures
 *   user    (amber)  — user-logged issues, fix outcomes
 *   ai      (purple) — AI analyses, suggested fixes
 */

import * as api from '../api/client.js';
import { showLoading, formatDate } from '../main.js';
import { escapeHtml, formatType, API_BASE } from '../utils.js';

// Which categories are currently visible
let activeFilters = new Set(['system', 'crash', 'user', 'ai']);
let allItems = [];

export async function initTimeline() {
  console.log('Loading timeline...');
  const container = document.getElementById('timeline-view');
  if (!container) return;

  showLoading('timeline-view');

  try {
    const [reliabilityResp, issues, analyses, fixes] = await Promise.all([
      fetch(`${API_BASE}/api/reliability/recent?limit=200`).then(r => r.json()),
      api.getIssues(100),
      fetch(`${API_BASE}/api/learning/fixes`).then(r => r.json()).catch(() => ({ fixes: [] })),
      fetch(`${API_BASE}/api/learning/overview`).then(r => r.json()).catch(() => ({ patterns: [] })),
    ]);

    const reliability = Array.isArray(reliabilityResp) ? reliabilityResp : [];
    allItems = [];

    // System & crash events from reliability records
    reliability.forEach((r) => {
      const cat = r.record_type || 'misc_failure';
      const group = getGroup(cat);
      allItems.push({
        group,
        category: cat,
        data: r,
        timestamp: r.event_time || r.timestamp || '',
        render: () => renderReliability(r, cat),
      });
    });

    // User-logged issues
    issues.forEach((i) => {
      allItems.push({
        group: 'user',
        category: i.issue_type,
        data: i,
        timestamp: i.timestamp || '',
        render: () => renderIssue(i),
      });
    });

    // AI analyses (from fix data — each fix has an analysis behind it)
    const fixList = analyses?.fixes || [];
    fixList.forEach((f) => {
      allItems.push({
        group: 'ai',
        category: 'ai_fix',
        data: f,
        timestamp: f.executed_at || f.approved_at || '',
        render: () => renderFix(f),
      });
    });

    // Sort newest first
    allItems.sort((a, b) => {
      const dateA = new Date(a.timestamp).getTime() || 0;
      const dateB = new Date(b.timestamp).getTime() || 0;
      return dateB - dateA;
    });

    renderTimeline(container);

  } catch (error) {
    container.innerHTML = `<p class="error">Failed to load timeline: ${error}</p>`;
  }
}

function renderTimeline(container) {
  if (allItems.length === 0) {
    container.innerHTML = '<p class="loading">No timeline data yet. Click "Collect Data" on the Dashboard to scan your system.</p>';
    return;
  }

  // Filter bar + legend
  const filterBar = buildFilterBar();
  const filtered = allItems.filter(item => activeFilters.has(item.group));

  let itemsHtml = '';
  if (filtered.length === 0) {
    itemsHtml = '<p style="color:var(--text-secondary);padding:20px;">No events match the current filters.</p>';
  } else {
    filtered.forEach(item => {
      itemsHtml += item.render();
    });
  }

  container.innerHTML = filterBar + '<div class="timeline-list">' + itemsHtml + '</div>';

  // Attach filter click handlers
  container.querySelectorAll('.tl-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.dataset.group;
      if (activeFilters.has(group)) {
        activeFilters.delete(group);
      } else {
        activeFilters.add(group);
      }
      renderTimeline(container);
    });
  });
}

function buildFilterBar() {
  const filters = [
    { group: 'system', label: 'System', color: '#3b82f6' },
    { group: 'crash', label: 'Crashes', color: '#ef4444' },
    { group: 'user', label: 'User Actions', color: '#f59e0b' },
    { group: 'ai', label: 'AI / Fixes', color: '#a855f7' },
  ];

  const counts = {};
  allItems.forEach(item => {
    counts[item.group] = (counts[item.group] || 0) + 1;
  });

  const btns = filters.map(f => {
    const active = activeFilters.has(f.group);
    const count = counts[f.group] || 0;
    return `<button class="tl-filter-btn ${active ? 'active' : ''}" data-group="${f.group}"
              style="--filter-color:${f.color};">
              <span class="tl-filter-dot" style="background:${f.color};"></span>
              ${f.label} <span class="tl-filter-count">${count}</span>
            </button>`;
  }).join('');

  return `<div class="tl-filter-bar">${btns}</div>`;
}

function getGroup(category) {
  if (category.includes('crash') || category.includes('failure')) return 'crash';
  if (category.includes('install') || category.includes('update')) return 'system';
  return 'system';
}

const groupColors = {
  system: '#3b82f6',
  crash: '#ef4444',
  user: '#f59e0b',
  ai: '#a855f7',
};

function renderReliability(r, category) {
  const group = getGroup(category);
  const color = groupColors[group];
  return `
    <div class="timeline-item" style="border-left-color:${color};">
      <div class="timeline-content">
        <div class="timeline-time">${formatDate(r.event_time || r.timestamp || '')}</div>
        <div class="timeline-title">${getIcon(category)} ${formatType(category)}</div>
        <div class="timeline-desc">
          <strong>${escapeHtml(r.source_name || '')}</strong>
          ${r.product_name ? ` - ${escapeHtml(r.product_name)}` : ''}
        </div>
        ${r.event_message ? `<div class="timeline-desc" style="margin-top:4px;color:var(--text-secondary);font-size:12px;">${escapeHtml(r.event_message.substring(0, 300))}${r.event_message.length > 300 ? '...' : ''}</div>` : ''}
      </div>
    </div>
  `;
}

function renderIssue(issue) {
  return `
    <div class="timeline-item" style="border-left-color:${groupColors.user};">
      <div class="timeline-content">
        <div class="timeline-time">${formatDate(issue.timestamp)}</div>
        <div class="timeline-title">${getIcon('issue')} Issue: ${formatType(issue.issue_type)}</div>
        <div class="timeline-desc">${escapeHtml(issue.description)}</div>
        <div class="timeline-desc" style="margin-top:5px;color:var(--text-secondary);">
          Severity: <strong>${issue.severity}</strong>
        </div>
      </div>
    </div>
  `;
}

function renderFix(f) {
  const stateColors = {
    pending: 'var(--text-secondary)',
    approved: 'var(--accent)',
    executed: 'var(--warning)',
    holding: '#c084fc',
    resolved: 'var(--success)',
    failed: 'var(--error)',
    rejected: '#6b7280',
    rolled_back: 'var(--error)',
  };
  const color = stateColors[f.status] || 'var(--text-secondary)';

  return `
    <div class="timeline-item" style="border-left-color:${groupColors.ai};">
      <div class="timeline-content">
        <div class="timeline-time">${formatDate(f.executed_at || f.approved_at || '')}</div>
        <div class="timeline-title"><span style="color:#a855f7;">&#x2699;</span> Fix: ${escapeHtml(f.title || 'Untitled')}</div>
        <div class="timeline-desc">${escapeHtml(f.description || '').substring(0, 200)}</div>
        <div style="margin-top:6px;">
          <span style="background:${color};color:white;font-size:11px;padding:1px 8px;border-radius:10px;text-transform:uppercase;">${f.status}</span>
          ${f.action_type ? `<span style="font-size:11px;color:var(--text-secondary);margin-left:8px;">${f.action_type}</span>` : ''}
        </div>
      </div>
    </div>
  `;
}

function getIcon(category) {
  const icons = {
    app_crash: '<span style="color:#ef4444;">&#x2716;</span>',
    app_install: '<span style="color:#22c55e;">&#x2795;</span>',
    app_uninstall: '<span style="color:#f59e0b;">&#x2796;</span>',
    os_update: '<span style="color:#3b82f6;">&#x21BB;</span>',
    os_crash: '<span style="color:#dc2626;">&#x26A0;</span>',
    driver_crash: '<span style="color:#f97316;">&#x26A1;</span>',
    driver_install: '<span style="color:#3b82f6;">&#x2795;</span>',
    hardware_failure: '<span style="color:#ef4444;">&#x2699;</span>',
    misc_failure: '<span style="color:#a0a0a0;">&#x2022;</span>',
    issue: '<span style="color:#f59e0b;">&#x25CF;</span>',
  };
  return icons[category] || icons.misc_failure;
}
