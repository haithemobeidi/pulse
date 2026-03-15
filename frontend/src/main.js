/**
 * Pulse Frontend - Main Entry Point
 */

import * as api from './api/client.js';
import { initDashboard } from './pages/dashboard.js';
import { initIssues } from './pages/issues.js';
import { initTimeline } from './pages/timeline.js';
// Hardware page removed - history now inline on Dashboard

const API_BASE = 'http://localhost:5000';

// Global utilities
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

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
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

      // Stop live polling when leaving dashboard
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
      // Hardware page removed - history is now inline on Dashboard cards
    }
  } catch (error) {
    console.error(`Failed to load ${pageName}:`, error);
    showNotification(`Failed to load ${pageName}`, 'error');
  }
}

// ============================================================================
// Troubleshoot Page
// ============================================================================

async function loadProviderStatus() {
  const badgesEl = document.getElementById('provider-badges');
  if (!badgesEl) return;

  try {
    const resp = await fetch(`${API_BASE}/api/ai/status`);
    const data = await resp.json();
    const providers = data.providers || {};

    let html = '';
    for (const [name, info] of Object.entries(providers)) {
      const dot = info.available ? '&#x25CF;' : '&#x25CB;';
      const color = info.available ? '#a6e3a1' : '#585b70';
      const label = name.charAt(0).toUpperCase() + name.slice(1);
      const extra = name === 'ollama' && info.models?.length
        ? ` (${info.models[0]})`
        : '';
      html += `<span style="color:${color};margin-right:16px;font-size:14px;">${dot} ${label}${extra}</span>`;
    }
    badgesEl.innerHTML = html;
  } catch (e) {
    badgesEl.innerHTML = '<span style="color:#f38ba8;">Cannot reach backend</span>';
  }
}

// Chat state
let chatHistory = []; // {role: 'user'|'assistant', content: ''}
let isFirstMessage = true;

function setupTroubleshoot() {
  const sendBtn = document.getElementById('analyze-btn');
  const input = document.getElementById('problem-input');

  if (!sendBtn || !input) return;

  sendBtn.addEventListener('click', () => sendMessage());
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Auto-resize textarea
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });

  // New chat button
  const newChatBtn = document.getElementById('new-chat-btn');
  if (newChatBtn) {
    newChatBtn.addEventListener('click', () => {
      chatHistory = [];
      isFirstMessage = true;
      window._screenshotData = null;
      const area = document.getElementById('screenshot-area');
      if (area) area.style.display = 'none';
      document.getElementById('chat-messages').innerHTML = `
        <div class="chat-welcome">
          <h2>What's wrong with your PC?</h2>
          <p style="color:var(--text-secondary);">Describe your problem below. I'll scan your system and help diagnose it.</p>
        </div>`;
    });
  }

  // Screenshot: file upload
  const fileInput = document.getElementById('screenshot-file');
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) handleScreenshot(e.target.files[0]);
    });
  }

  // Screenshot: paste (Ctrl+V)
  document.addEventListener('paste', (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        handleScreenshot(item.getAsFile());
        return;
      }
    }
  });

  // Screenshot: remove
  const removeBtn = document.getElementById('screenshot-remove');
  if (removeBtn) {
    removeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      window._screenshotData = null;
      document.getElementById('screenshot-area').style.display = 'none';
    });
  }

  // Check system scan status on load
  checkSystemStatus();
}

function handleScreenshot(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const dataUrl = e.target.result;
    window._screenshotData = dataUrl;
    const img = document.getElementById('screenshot-img');
    const area = document.getElementById('screenshot-area');
    img.src = dataUrl;
    area.style.display = 'block';
    showNotification('Screenshot attached', 'success');
  };
  reader.readAsDataURL(file);
}

async function checkSystemStatus() {
  const indicator = document.getElementById('scan-indicator');
  if (!indicator) return;

  try {
    // Check if we have recent data
    const hardware = await api.getCurrentHardware();

    if (hardware.status === 'no_data') {
      // No data at all - run a scan
      indicator.innerHTML = '<span style="color:var(--warning);">No system data. Scanning...</span>';
      indicator.classList.add('btn-loading');

      console.log('[Pulse] No system data found, running initial scan...');
      const result = await api.collectAll();
      console.log('[Pulse] Initial scan result:', result);

      indicator.classList.remove('btn-loading');
      indicator.innerHTML = '<span style="color:var(--success);">System scanned</span>';
    } else {
      indicator.innerHTML = '<span style="color:var(--success);">System data loaded</span>';
    }
  } catch (error) {
    console.error('[Pulse] System status check failed:', error);
    indicator.innerHTML = '<span style="color:var(--error);">Status check failed</span>';
  }
}

async function sendMessage() {
  const input = document.getElementById('problem-input');
  const sendBtn = document.getElementById('analyze-btn');
  const chatMessages = document.getElementById('chat-messages');

  const text = input.value.trim();
  if (!text) return;

  const provider = document.getElementById('provider-select').value;

  // Clear welcome message on first send
  const welcome = chatMessages.querySelector('.chat-welcome');
  if (welcome) welcome.remove();

  // Add user message to chat
  addChatMessage('user', text);
  chatHistory.push({ role: 'user', content: text });
  input.value = '';
  input.style.height = 'auto';

  // Show typing indicator
  const typingEl = document.createElement('div');
  typingEl.className = 'chat-typing';
  typingEl.textContent = isFirstMessage ? 'Scanning system & analyzing...' : 'Thinking...';
  chatMessages.appendChild(typingEl);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  sendBtn.disabled = true;

  try {
    let responseText = '';
    let providerUsed = '';

    if (isFirstMessage) {
      // First message: full analysis (scan + AI)
      isFirstMessage = false;

      const payload = { description: text, provider, include_context: true };
      if (window._screenshotData) {
        payload.screenshot = window._screenshotData;
        window._screenshotData = null;
        document.getElementById('screenshot-area').style.display = 'none';
      }

      const resp = await fetch(`${API_BASE}/api/ai/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const analysis = await resp.json();

      if (analysis.error && !analysis.diagnosis) {
        throw new Error(analysis.error);
      }

      // Build readable response from structured analysis
      responseText = formatAnalysisAsChat(analysis);
      providerUsed = `${analysis.provider || '?'} (${analysis.model || '?'})`;
      chatHistory.push({ role: 'assistant', content: responseText });

    } else {
      // Follow-up: conversational chat with history
      const resp = await fetch(`${API_BASE}/api/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: chatHistory, provider }),
      });

      const data = await resp.json();
      if (data.error) throw new Error(data.error);

      responseText = data.response || 'No response';
      providerUsed = `${data.provider || '?'} (${data.model || '?'})`;
      chatHistory.push({ role: 'assistant', content: responseText });
    }

    typingEl.remove();
    addChatMessage('assistant', responseText, providerUsed);

  } catch (error) {
    typingEl.remove();
    addChatMessage('system', `Error: ${error.message}`);
    console.error('[Pulse] Chat error:', error);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function addChatMessage(role, content, meta = '') {
  const chatMessages = document.getElementById('chat-messages');
  const msgEl = document.createElement('div');
  msgEl.className = `chat-msg ${role}`;

  if (role === 'user') {
    msgEl.textContent = content;
  } else if (role === 'system') {
    msgEl.textContent = content;
  } else {
    msgEl.innerHTML = formatMessageContent(content);
    if (meta) {
      msgEl.innerHTML += `<div class="msg-meta">${escapeHtml(meta)}</div>`;
    }
  }

  chatMessages.appendChild(msgEl);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatAnalysisAsChat(analysis) {
  let parts = [];

  if (analysis.diagnosis) {
    const confPct = Math.round((analysis.confidence || 0) * 100);
    parts.push(`**Diagnosis** (${confPct}% confidence):\n${analysis.diagnosis}`);
  }
  if (analysis.root_cause) {
    parts.push(`**Root Cause:** ${analysis.root_cause}`);
  }

  const fixes = analysis.suggested_fixes || [];
  if (fixes.length > 0) {
    parts.push('**Suggested Fixes:**');
    fixes.forEach((fix, i) => {
      const successPct = Math.round((fix.estimated_success || 0) * 100);
      parts.push(`${i + 1}. **${fix.title}** (${fix.risk_level} risk, ${successPct}% success)\n   ${fix.description}\n   \`${fix.action_detail}\``);
    });
  }

  const questions = analysis.questions || [];
  if (questions.length > 0) {
    parts.push('**Questions for you:**\n' + questions.map(q => `- ${q}`).join('\n'));
  }

  if (analysis.preventive_tips) {
    parts.push(`**Prevention:** ${analysis.preventive_tips}`);
  }

  return parts.join('\n\n');
}

function formatMessageContent(text) {
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/`([^`]+)`/g, '<code style="background:#11111b;padding:2px 6px;border-radius:3px;color:#89b4fa;">$1</code>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

async function handleFixApprove(fixId) {
  const statusDiv = document.querySelector(`.fix-status[data-fix-id="${fixId}"]`);

  try {
    // Step 1: Approve
    let resp = await fetch(`${API_BASE}/api/fixes/${fixId}/approve`, { method: 'POST' });
    let data = await resp.json();

    if (!resp.ok) {
      statusDiv.innerHTML = `<span style="color:#f38ba8;">Error: ${data.error}</span>`;
      return;
    }

    statusDiv.innerHTML = '<span style="color:#f9e2af;">Approved. Execute this fix?</span> ' +
      `<button class="btn btn-primary fix-execute-btn" style="padding:4px 12px;font-size:12px;margin-left:8px;">Execute</button>`;

    statusDiv.querySelector('.fix-execute-btn').addEventListener('click', async () => {
      statusDiv.innerHTML = '<span style="color:#a6adc8;">Executing...</span>';

      // Step 2: Execute
      resp = await fetch(`${API_BASE}/api/fixes/${fixId}/execute`, { method: 'POST' });
      data = await resp.json();

      if (data.success) {
        statusDiv.innerHTML = `<span style="color:#a6e3a1;">Executed successfully.</span>` +
          (data.output ? `<pre style="background:#11111b;padding:8px;border-radius:4px;margin-top:6px;color:#a6adc8;font-size:12px;max-height:100px;overflow:auto;">${escapeHtml(data.output)}</pre>` : '') +
          `<div style="margin-top:8px;"><span style="color:#a6adc8;">Did this fix the problem?</span> ` +
          `<button class="btn btn-primary fix-yes-btn" style="padding:4px 12px;font-size:12px;margin:0 4px;">Yes</button>` +
          `<button class="btn fix-no-btn" style="padding:4px 12px;font-size:12px;background:#45475a;color:#cdd6f4;border:none;border-radius:6px;cursor:pointer;">No</button></div>`;

        // Step 3: Outcome
        statusDiv.querySelector('.fix-yes-btn').addEventListener('click', () => recordOutcome(fixId, true, statusDiv));
        statusDiv.querySelector('.fix-no-btn').addEventListener('click', () => recordOutcome(fixId, false, statusDiv));
      } else {
        statusDiv.innerHTML = `<span style="color:#f38ba8;">Execution failed.</span>` +
          (data.output ? `<pre style="background:#11111b;padding:8px;border-radius:4px;margin-top:6px;color:#f38ba8;font-size:12px;">${escapeHtml(data.output)}</pre>` : '');
      }
    });

  } catch (error) {
    statusDiv.innerHTML = `<span style="color:#f38ba8;">Error: ${error.message}</span>`;
  }
}

async function handleFixReject(fixId) {
  const statusDiv = document.querySelector(`.fix-status[data-fix-id="${fixId}"]`);
  try {
    await fetch(`${API_BASE}/api/fixes/${fixId}/reject`, { method: 'POST' });
    statusDiv.innerHTML = '<span style="color:#585b70;">Rejected</span>';
  } catch (error) {
    statusDiv.innerHTML = `<span style="color:#f38ba8;">Error: ${error.message}</span>`;
  }
}

async function recordOutcome(fixId, resolved, statusDiv) {
  try {
    await fetch(`${API_BASE}/api/fixes/${fixId}/outcome`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resolved, notes: '' }),
    });
    statusDiv.innerHTML = resolved
      ? '<span style="color:#a6e3a1;">Marked as resolved. Pulse will remember this fix worked!</span>'
      : '<span style="color:#f9e2af;">Noted. Pulse will learn from this for next time.</span>';
  } catch (error) {
    statusDiv.innerHTML = `<span style="color:#f38ba8;">Error recording outcome: ${error.message}</span>`;
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
    const originalText = collectBtn.textContent;
    try {
      collectBtn.disabled = true;
      collectBtn.textContent = 'Scanning...';
      collectBtn.classList.add('btn-loading');
      console.log('[Pulse] Starting data collection...');
      const startTime = Date.now();

      const result = await api.collectAll();
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      console.log(`[Pulse] Collection completed in ${elapsed}s:`, result);

      if (result.status === 'success') {
        const parts = Object.entries(result.collections || {})
          .map(([k, v]) => `${k}: ${v}`)
          .join(', ');
        showNotification(`Scan complete (${elapsed}s) - ${parts}`, 'success');
        await initDashboard();
      } else {
        showNotification('Data collection partially succeeded', 'warning');
      }
    } catch (error) {
      console.error('[Pulse] Data collection failed:', error);
      showNotification(`Collection failed: ${error}`, 'error');
    } finally {
      collectBtn.disabled = false;
      collectBtn.textContent = originalText;
      collectBtn.classList.remove('btn-loading');
    }
  });
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
    console.log('Pulse ready');
  } catch (error) {
    console.error('Initialization failed:', error);
    showNotification('Failed to initialize application', 'error');
  }
}

document.addEventListener('DOMContentLoaded', init);

// Auto-reload when server restarts
(function serverHeartbeat() {
  let serverStartTime = null;
  let wasDown = false;

  async function check() {
    try {
      const resp = await fetch('/api/status');
      if (!resp.ok) throw new Error('not ok');
      const data = await resp.json();

      if (wasDown) {
        // Server came back from being down
        console.log('[Pulse] Server is back — reloading');
        location.reload();
        return;
      }

      // Track server start time to detect restarts
      const newStart = data.server_start;
      if (newStart && serverStartTime && newStart !== serverStartTime) {
        console.log('[Pulse] Server restarted — reloading');
        location.reload();
        return;
      }
      serverStartTime = newStart;
      wasDown = false;
    } catch {
      if (!wasDown) console.log('[Pulse] Server connection lost...');
      wasDown = true;
    }
  }

  // Start checking after 5s (let page load first)
  setTimeout(() => setInterval(check, 3000), 5000);
})();

export { api };
