/**
 * PC-Inspector Frontend Main Entry Point
 *
 * Initializes UI event handlers and data loading.
 * Manages page navigation and component state.
 */

import * as api from './api/client.js';
import { initDashboard } from './pages/dashboard.js';
import { initIssues } from './pages/issues.js';
import { initTimeline } from './pages/timeline.js';
import { initHardware } from './pages/hardware.js';

// ============================================================================
// Global Utilities
// ============================================================================

export function showNotification(
  message: string,
  type: 'success' | 'error' | 'warning' | 'info' = 'success'
) {
  const notification = document.getElementById('notification');
  if (!notification) return;

  notification.textContent = message;
  notification.className = `notification ${type}`;
  notification.classList.remove('hidden');

  setTimeout(() => {
    notification.classList.add('hidden');
  }, 3000);
}

export function showLoading(elementId: string, show: boolean = true) {
  const el = document.getElementById(elementId);
  if (!el) return;

  if (show) {
    el.innerHTML = '<p class="loading">Loading...</p>';
  }
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString();
}

export function formatDateShort(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString();
}

export function formatTimeShort(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// ============================================================================
// Page Navigation
// ============================================================================

function setupNavigation() {
  const navBtns = document.querySelectorAll('.nav-btn');
  const pages = document.querySelectorAll('.page');

  navBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const pageName = (btn as HTMLElement).getAttribute('data-page');

      // Update active button
      navBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      // Update active page
      pages.forEach((p) => p.classList.remove('active'));
      const page = document.getElementById(pageName || '');
      if (page) {
        page.classList.add('active');
      }

      // Load page data
      loadPageData(pageName);
    });
  });
}

async function loadPageData(pageName?: string | null) {
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

// ============================================================================
// Issue Logging Modal
// ============================================================================

function setupIssueModal() {
  const modal = document.getElementById('issue-modal');
  const logIssueBtn = document.getElementById('log-issue-btn');
  const form = document.getElementById('issue-form');
  const closeButtons = document.querySelectorAll('.modal-close, .modal-close-btn');

  if (!modal || !logIssueBtn || !form) return;

  // Open modal
  logIssueBtn.addEventListener('click', () => {
    modal.classList.remove('hidden');
  });

  // Close modal
  closeButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      modal.classList.add('hidden');
    });
  });

  // Close on outside click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.classList.add('hidden');
    }
  });

  // Form submission
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const type = (document.getElementById('issue-type') as HTMLSelectElement)
      ?.value;
    const severity = (document.getElementById(
      'issue-severity'
    ) as HTMLSelectElement)?.value;
    const description = (
      document.getElementById('issue-description') as HTMLTextAreaElement
    )?.value;

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

      // Reload dashboard and issues
      await Promise.all([initDashboard(), initIssues()]);
    } catch (error) {
      console.error('Failed to log issue:', error);
      showNotification(`Failed to log issue: ${error}`, 'error');
    } finally {
      logIssueBtn.disabled = false;
    }
  });
}

// ============================================================================
// Data Collection
// ============================================================================

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

// ============================================================================
// Initialization
// ============================================================================

async function init() {
  console.log('PC-Inspector starting...');

  try {
    // Setup UI
    setupNavigation();
    setupIssueModal();
    setupDataCollection();

    // Load initial page
    await initDashboard();

    console.log('PC-Inspector ready');
  } catch (error) {
    console.error('Initialization failed:', error);
    showNotification('Failed to initialize application', 'error');
  }
}

// Start app
document.addEventListener('DOMContentLoaded', init);

// Export utilities for pages
export { api };
