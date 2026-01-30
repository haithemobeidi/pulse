import * as api from '../api/client.js';
import { showLoading, formatDate } from '../main.js';

export async function initTimeline() {
  console.log('Loading timeline...');
  const container = document.getElementById('timeline-view');
  if (!container) return;

  showLoading('timeline-view');

  try {
    const [snapshots, issues] = await Promise.all([
      api.getSnapshots(30),
      api.getIssues(100),
    ]);

    const timelineItems = [
      ...snapshots.map((s) => ({ type: 'snapshot', data: s })),
      ...issues.map((i) => ({ type: 'issue', data: i })),
    ].sort((a, b) => {
      const dateA = new Date(a.data.timestamp).getTime();
      const dateB = new Date(b.data.timestamp).getTime();
      return dateB - dateA;
    });

    if (timelineItems.length === 0) {
      container.innerHTML = '<p class="loading">No data yet</p>';
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
              <div class="timeline-title">Issue: ${formatIssueType(issue.issue_type)}</div>
              <div class="timeline-desc">${escapeHtml(issue.description)}</div>
              <div class="timeline-desc" style="margin-top: 5px; color: #a0a0a0;">
                Severity: <strong>${issue.severity}</strong>
              </div>
            </div>
          </div>
        `;
      } else {
        const snapshot = item.data;
        html += `
          <div class="timeline-item">
            <div class="timeline-content">
              <div class="timeline-time">${formatDate(snapshot.timestamp)}</div>
              <div class="timeline-title">Snapshot: ${formatSnapshotType(snapshot.snapshot_type)}</div>
              ${snapshot.notes ? `<div class="timeline-desc">${escapeHtml(snapshot.notes)}</div>` : ''}
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

function formatIssueType(type) {
  return type.split('_').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

function formatSnapshotType(type) {
  const typeMap = {
    scheduled: 'Scheduled Collection',
    issue_logged: 'Issue Capture',
    manual: 'Manual Snapshot',
  };
  return typeMap[type] || type;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
