/**
 * PC-Inspector Frontend - Main Entry Point
 */

import * as api from './api/client.js';
import { initDashboard } from './pages/dashboard.js';
import { initIssues } from './pages/issues.js';
import { initTimeline } from './pages/timeline.js';
import { initHardware } from './pages/hardware.js';

// Global utilities
export function showNotification(message, type = 'success') {
  const notification = document.getElementById('notification');
  if (!notification) return;

  notification.textContent = message;
  notification.className = `notification ${type}`;
  notification.classList.remove('hidden');

  setTimeout(() => {
    notification.classList.add('hidden');
  }, 3000);
}

export function showLoading(elementId, show = true) {
  const el = document.getElementById(elementId);
  if (!el) return;

  if (show) {
    el.innerHTML = '<p class="loading">Loading...</p>';
  }
}

export function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleString();
}

export function formatDateShort(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString();
}

export function formatTimeShort(dateString) {
  const date = new Date(dateString);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Page Navigation
function setupNavigation() {
  const navBtns = document.querySelectorAll('.nav-btn');
  const pages = document.querySelectorAll('.page');

  navBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const pageName = btn.getAttribute('data-page');

      navBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      pages.forEach((p) => p.classList.remove('active'));
      const page = document.getElementById(pageName);
      if (page) {
        page.classList.add('active');
      }

      loadPageData(pageName);
    });
  });
}

async function loadPageData(pageName) {
  try {
    switch (pageName) {
      case 'dashboard':
        await initDashboard();
        break;
      case 'issues':
        await initIssues();
        break;
      case 'timeline':
        await initTimeline();
        break;
      case 'hardware':
        await initHardware();
        break;
    }
  } catch (error) {
    console.error(`Failed to load ${pageName}:`, error);
    showNotification(`Failed to load ${pageName}`, 'error');
  }
}

// Issue Modal
function setupIssueModal() {
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

// Data Collection
function setupDataCollection() {
  const collectBtn = document.getElementById('collect-btn');

  if (!collectBtn) return;

  collectBtn.addEventListener('click', async () => {
    try {
      collectBtn.disabled = true;
      const result = await api.collectAll();

      if (result.status === 'success') {
        showNotification('Data collected successfully!', 'success');
        await initDashboard();
      } else {
        showNotification('Data collection partially succeeded', 'warning');
      }
    } catch (error) {
      console.error('Data collection failed:', error);
      showNotification(`Collection failed: ${error}`, 'error');
    } finally {
      collectBtn.disabled = false;
    }
  });
}

// Initialize
async function init() {
  console.log('PC-Inspector starting...');

  try {
    setupNavigation();
    setupIssueModal();
    setupDataCollection();
    await initDashboard();
    console.log('PC-Inspector ready');
  } catch (error) {
    console.error('Initialization failed:', error);
    showNotification('Failed to initialize application', 'error');
  }
}

document.addEventListener('DOMContentLoaded', init);

export { api };
