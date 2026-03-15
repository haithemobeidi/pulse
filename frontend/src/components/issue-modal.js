/**
 * Issue modal — log new issues
 */

import * as api from '../api/client.js';
import { showNotification } from '../main.js';
import { initDashboard } from '../pages/dashboard.js';
import { initIssues } from '../pages/issues.js';

export function setupIssueModal() {
  const modal = document.getElementById('issue-modal');
  const logIssueBtn = document.getElementById('log-issue-btn');
  const form = document.getElementById('issue-form');
  const closeButtons = document.querySelectorAll('.modal-close, .modal-close-btn');

  if (!modal || !logIssueBtn || !form) return;

  logIssueBtn.addEventListener('click', () => {
    modal.classList.remove('hidden');
  });

  closeButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      modal.classList.add('hidden');
    });
  });

  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.classList.add('hidden');
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const type = document.getElementById('issue-type').value;
    const severity = document.getElementById('issue-severity').value;
    const description = document.getElementById('issue-description').value;

    if (!type || !description) {
      showNotification('Please fill in all fields', 'warning');
      return;
    }

    try {
      logIssueBtn.disabled = true;
      await api.logIssue(type, description, severity);
      showNotification('Issue logged successfully!', 'success');
      modal.classList.add('hidden');
      form.reset();

      await Promise.all([initDashboard(), initIssues()]);
    } catch (error) {
      console.error('Failed to log issue:', error);
      showNotification(`Failed to log issue: ${error}`, 'error');
    } finally {
      logIssueBtn.disabled = false;
    }
  });
}
