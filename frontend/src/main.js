/**
 * Pulse Frontend - Main Entry Point
 */

import * as api from './api/client.js';
import { initDashboard } from './pages/dashboard.js';
import { initIssues } from './pages/issues.js';
import { initTimeline } from './pages/timeline.js';
import { setupTroubleshoot, loadProviderStatus } from './pages/troubleshoot.js';
import { setupIssueModal } from './components/issue-modal.js';
import { setupDataCollection } from './components/data-collection.js';
import { startHeartbeat } from './components/heartbeat.js';
import { connectSSE } from './api/events.js';

// Global utilities (exported for use by page modules)
export function showNotification(message, type = 'success') {
  const notification = document.getElementById('notification');
  if (!notification) return;

  notification.textContent = message;
  notification.className = `notification ${type}`;
  notification.classList.remove('hidden');

  setTimeout(() => {
    notification.classList.add('hidden');
  }, 5000);
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

      if (typeof window.stopLiveStats === 'function') {
        window.stopLiveStats();
      }
      loadPageData(pageName);
    });
  });
}

async function loadPageData(pageName) {
  try {
    switch (pageName) {
      case 'troubleshoot':
        await loadProviderStatus();
        break;
      case 'dashboard':
        await initDashboard();
        break;
      case 'issues':
        await initIssues();
        break;
      case 'timeline':
        await initTimeline();
        break;
    }
  } catch (error) {
    console.error(`Failed to load ${pageName}:`, error);
    showNotification(`Failed to load ${pageName}`, 'error');
  }
}

// Initialize
async function init() {
  console.log('Pulse starting...');

  try {
    setupNavigation();
    setupTroubleshoot();
    setupIssueModal();
    setupDataCollection();
    await loadProviderStatus();
    startHeartbeat();
    connectSSE();
    console.log('Pulse ready');
  } catch (error) {
    console.error('Initialization failed:', error);
    showNotification('Failed to initialize application', 'error');
  }
}

document.addEventListener('DOMContentLoaded', init);

export { api };
