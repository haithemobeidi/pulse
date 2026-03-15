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

function setupTroubleshoot() {
  const analyzeBtn = document.getElementById('analyze-btn');
  const problemInput = document.getElementById('problem-input');

  if (!analyzeBtn || !problemInput) return;

  // Reset stale state from previous sessions (browser cache restores DOM)
  const scanProgress = document.getElementById('scan-progress');
  const analysisResults = document.getElementById('analysis-results');
  if (scanProgress) scanProgress.style.display = 'none';
  if (analysisResults) analysisResults.style.display = 'none';

  analyzeBtn.addEventListener('click', () => runAnalysis());
  problemInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      runAnalysis();
    }
  });

  // Screenshot: file upload
  const fileInput = document.getElementById('screenshot-file');
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        handleScreenshot(e.target.files[0]);
      }
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
      document.getElementById('screenshot-preview').style.display = 'none';
      document.getElementById('screenshot-label').style.display = '';
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
    const preview = document.getElementById('screenshot-preview');
    const label = document.getElementById('screenshot-label');
    img.src = dataUrl;
    preview.style.display = 'inline-block';
    label.style.display = 'none';
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

async function runAnalysis() {
  const problemInput = document.getElementById('problem-input');
  const analyzeBtn = document.getElementById('analyze-btn');
  const progressDiv = document.getElementById('scan-progress');
  const progressFill = document.getElementById('progress-fill');
  const scanStatus = document.getElementById('scan-status');
  const resultsDiv = document.getElementById('analysis-results');

  const description = problemInput.value.trim();
  if (!description) {
    showNotification('Describe your problem first', 'warning');
    problemInput.focus();
    return;
  }

  const provider = document.getElementById('provider-select').value;

  // Show progress
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = 'Analyzing...';
  progressDiv.style.display = 'block';
  resultsDiv.style.display = 'none';

  // Animate progress with realistic timing
  let progress = 0;
  const steps = [
    'Collecting hardware data...',
    'Scanning monitors & reliability...',
    'Sending to AI for analysis...',
    'Waiting for AI response...',
    'Processing diagnosis...',
  ];
  const stepInterval = setInterval(() => {
    progress = Math.min(progress + 5, 95);
    progressFill.style.width = progress + '%';
    const stepIdx = Math.min(Math.floor(progress / 20), steps.length - 1);
    scanStatus.textContent = steps[stepIdx];
  }, 1500);

  // Timeout: abort after 60 seconds
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);

  try {
    console.log('[Pulse] Starting analysis...');
    const startTime = Date.now();

    // Include screenshot if attached
    const payload = { description, provider };
    if (window._screenshotData) {
      payload.screenshot = window._screenshotData;
    }
    // Tell backend to include recent context
    payload.include_context = true;

    const resp = await fetch(`${API_BASE}/api/ai/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    clearTimeout(timeout);
    clearInterval(stepInterval);

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`[Pulse] Analysis completed in ${elapsed}s`);

    progressFill.style.width = '100%';
    scanStatus.textContent = `Done! (${elapsed}s)`;

    const analysis = await resp.json();

    if (analysis.error && !analysis.diagnosis) {
      showNotification(`Analysis failed: ${analysis.error}`, 'error');
      progressDiv.style.display = 'none';
      return;
    }

    displayAnalysis(analysis);

  } catch (error) {
    clearTimeout(timeout);
    clearInterval(stepInterval);
    progressDiv.style.display = 'none';

    if (error.name === 'AbortError') {
      console.error('[Pulse] Analysis timed out after 60s');
      showNotification('Analysis timed out. Try again or use a different AI provider.', 'error');
    } else {
      console.error('[Pulse] Analysis failed:', error);
      showNotification(`Analysis failed: ${error.message}`, 'error');
    }
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = 'Analyze';
    setTimeout(() => progressDiv.classList.add('hidden'), 2000);
  }
}

function displayAnalysis(analysis) {
  const resultsDiv = document.getElementById('analysis-results');
  resultsDiv.style.display = 'block';

  // Diagnosis
  const confidence = analysis.confidence || 0;
  const confPct = Math.round(confidence * 100);
  const confColor = confidence > 0.7 ? '#a6e3a1' : confidence > 0.4 ? '#f9e2af' : '#f38ba8';
  document.getElementById('confidence-badge').innerHTML =
    `<span style="color:${confColor};font-weight:bold;">${confPct}% confidence</span>`;
  document.getElementById('diagnosis-text').textContent = analysis.diagnosis || 'No diagnosis available';
  document.getElementById('root-cause').textContent = analysis.root_cause
    ? `Root cause: ${analysis.root_cause}`
    : '';
  document.getElementById('provider-used').textContent =
    `Analyzed by ${analysis.provider || 'unknown'} (${analysis.model || ''})`;

  // Fixes
  const fixesList = document.getElementById('fixes-list');
  const fixes = analysis.suggested_fixes || [];

  if (fixes.length > 0) {
    fixesList.innerHTML = '<h3 style="color:#cdd6f4;margin:16px 0 8px;">Suggested Fixes</h3>' +
      fixes.map((fix, i) => {
        const riskColors = {
          none: '#a6e3a1', low: '#a6e3a1', medium: '#f9e2af',
          high: '#fab387', critical: '#f38ba8'
        };
        const riskColor = riskColors[fix.risk_level] || '#a6adc8';
        const successPct = Math.round((fix.estimated_success || 0) * 100);
        const fixId = fix.id || '';

        return `
          <div class="card" style="border-left:3px solid ${riskColor};" data-fix-id="${fixId}">
            <div style="display:flex;justify-content:space-between;align-items:start;">
              <h4 style="color:#cdd6f4;margin:0;">${escapeHtml(fix.title)}</h4>
              <span style="color:${riskColor};font-size:12px;text-transform:uppercase;">${escapeHtml(fix.risk_level)} risk</span>
            </div>
            <p style="color:#a6adc8;margin:8px 0;">${escapeHtml(fix.description)}</p>
            <div style="background:#11111b;padding:10px;border-radius:6px;margin:8px 0;">
              <code style="color:#89b4fa;font-size:13px;white-space:pre-wrap;">${escapeHtml(fix.action_detail)}</code>
            </div>
            <div style="display:flex;gap:8px;align-items:center;margin-top:10px;">
              <span style="color:#585b70;font-size:12px;">Success: ${successPct}% | ${fix.reversible ? 'Reversible' : 'Not reversible'}</span>
              <div style="flex:1;"></div>
              ${fixId ? `
                <button class="btn btn-secondary fix-approve-btn" data-fix-id="${fixId}" style="padding:6px 14px;font-size:13px;">Approve</button>
                <button class="btn fix-reject-btn" data-fix-id="${fixId}" style="padding:6px 14px;font-size:13px;background:#45475a;color:#cdd6f4;border:none;border-radius:6px;cursor:pointer;">Reject</button>
              ` : ''}
            </div>
            <div class="fix-status" data-fix-id="${fixId}" style="margin-top:8px;"></div>
          </div>`;
      }).join('');

    // Attach fix button handlers
    fixesList.querySelectorAll('.fix-approve-btn').forEach(btn => {
      btn.addEventListener('click', () => handleFixApprove(btn.dataset.fixId));
    });
    fixesList.querySelectorAll('.fix-reject-btn').forEach(btn => {
      btn.addEventListener('click', () => handleFixReject(btn.dataset.fixId));
    });
  } else {
    fixesList.innerHTML = '';
  }

  // Questions
  const questions = analysis.questions || [];
  const questionsDiv = document.getElementById('ai-questions');
  if (questions.length > 0) {
    questionsDiv.classList.remove('hidden');
    document.getElementById('questions-list').innerHTML =
      questions.map(q => `<li style="margin:6px 0;">${escapeHtml(q)}</li>`).join('');
  } else {
    questionsDiv.classList.add('hidden');
  }

  // Prevention
  const preventive = analysis.preventive_tips;
  const preventiveDiv = document.getElementById('preventive-card');
  if (preventive) {
    preventiveDiv.classList.remove('hidden');
    document.getElementById('preventive-text').textContent = preventive;
  } else {
    preventiveDiv.classList.add('hidden');
  }
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

export { api };
