/**
 * Issues Page
 *
 * Shows all logged issues in a list.
 * Each issue shows the type, description, severity, and timestamp.
 */

import * as api from '../api/client.js';
import { showLoading, formatDate } from '../main.js';

export async function initIssues() {
  console.log('Loading issues...');

  const container = document.getElementById('all-issues-list');
  if (!container) return;

  showLoading('all-issues-list');

  try {
    const issues = await api.getIssues(100);

    if (issues.length === 0) {
      container.innerHTML = '<p class="loading">No issues logged</p>';
      return;
    }

    let html = '';
    issues.forEach((issue: api.Issue) => {
      html += `
        <div class="issue-item severity-${issue.severity}" onclick="handleIssueClick(${issue.id})">
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

// Make function global for onclick handlers
(window as any).handleIssueClick = async (issueId: number) => {
  console.log(`Viewing issue ${issueId}`);
  try {
    const issue = await api.getIssue(issueId);
    console.log('Issue details:', issue);
    // In a full implementation, would show a modal with full details
  } catch (error) {
    console.error('Failed to load issue details:', error);
  }
};
