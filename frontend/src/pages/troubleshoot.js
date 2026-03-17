/**
 * Troubleshoot page — chat UI, screenshot handling, fix approval
 */

import * as api from '../api/client.js';
import { showNotification } from '../main.js';
import { escapeHtml, API_BASE } from '../utils.js';
import { connectSSE, disconnectSSE } from '../api/events.js';

// Chat state
let chatHistory = [];
let isFirstMessage = true;
let currentSessionId = null;
let currentAbortController = null;

async function startNewSession() {
  try {
    const resp = await fetch(`${API_BASE}/api/ai/sessions/new`, { method: 'POST' });
    const data = await resp.json();
    currentSessionId = data.session_id;
    console.log(`[Pulse] New session: ${currentSessionId}`);
  } catch (e) {
    console.warn('[Pulse] Failed to create session:', e);
    currentSessionId = null;
  }
}

export function setupTroubleshoot() {
  const sendBtn = document.getElementById('analyze-btn');
  const input = document.getElementById('problem-input');

  if (!sendBtn || !input) return;

  // Create initial session
  startNewSession();

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
      currentSessionId = null;
      startNewSession();
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
    const hardware = await api.getCurrentHardware();

    if (hardware.status === 'no_data') {
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

  const welcome = chatMessages.querySelector('.chat-welcome');
  if (welcome) welcome.remove();

  addChatMessage('user', text);
  chatHistory.push({ role: 'user', content: text });
  input.value = '';
  input.style.height = 'auto';

  // Build visual progress indicator
  const typingEl = document.createElement('div');
  typingEl.className = 'chat-typing';

  const allSteps = isFirstMessage
    ? ['context', 'collecting', 'hardware', 'monitors', 'reliability', 'analyzing', 'storing']
    : ['thinking'];
  const stepLabels = {
    context: 'Building context',
    collecting: 'Scanning system',
    hardware: 'Hardware',
    monitors: 'Monitors',
    reliability: 'Reliability',
    analyzing: 'AI analyzing',
    storing: 'Saving results',
    thinking: 'Thinking',
  };

  let currentStepIdx = 0;

  function renderProgress() {
    const pct = Math.round(((currentStepIdx + 1) / allSteps.length) * 100);
    const currentLabel = stepLabels[allSteps[currentStepIdx]] || allSteps[currentStepIdx];

    let stepsHtml = '';
    if (isFirstMessage) {
      stepsHtml = allSteps.map((s, i) => {
        const label = stepLabels[s] || s;
        const color = i < currentStepIdx ? '#a6e3a1' : i === currentStepIdx ? '#89b4fa' : '#585b70';
        const icon = i < currentStepIdx ? '\u2713' : i === currentStepIdx ? '\u25B6' : '\u2022';
        return `<span style="color:${color};font-size:12px;margin-right:8px;">${icon} ${label}</span>`;
      }).join('');
    }

    typingEl.innerHTML = `
      <div style="margin-bottom:8px;font-size:14px;color:#cdd6f4;">
        ${currentLabel}...
      </div>
      <div style="background:#313244;border-radius:4px;height:6px;width:100%;max-width:400px;overflow:hidden;margin-bottom:8px;">
        <div style="background:linear-gradient(90deg,#89b4fa,#74c7ec);height:100%;width:${pct}%;transition:width 0.5s ease;border-radius:4px;"></div>
      </div>
      ${stepsHtml ? `<div style="line-height:1.8;">${stepsHtml}</div>` : ''}
    `;
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  renderProgress();
  chatMessages.appendChild(typingEl);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  // Connect SSE for live progress during analysis
  connectSSE();

  // Listen for SSE progress events to update the progress bar
  const progressHandler = (e) => {
    const { step, status } = e.detail;
    const idx = allSteps.indexOf(step);
    if (idx >= 0) {
      currentStepIdx = idx;
      if (status === 'done') {
        currentStepIdx = Math.min(idx + 1, allSteps.length - 1);
      }
      renderProgress();
    }
  };
  window.addEventListener('pulse:analysis_progress', progressHandler);
  window.addEventListener('pulse:scan_progress', progressHandler);

  // Create AbortController for cancellation
  currentAbortController = new AbortController();
  const { signal } = currentAbortController;

  // Show stop button, hide send button
  sendBtn.style.display = 'none';
  let stopBtn = document.getElementById('stop-btn');
  if (!stopBtn) {
    stopBtn = document.createElement('button');
    stopBtn.id = 'stop-btn';
    stopBtn.className = 'btn';
    stopBtn.innerHTML = '&#9632; Stop';
    stopBtn.style.cssText = 'background:#f38ba8;color:#1e1e2e;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font-weight:600;font-size:14px;';
    sendBtn.parentNode.insertBefore(stopBtn, sendBtn.nextSibling);
  }
  stopBtn.style.display = '';
  stopBtn.onclick = () => {
    if (currentAbortController) {
      currentAbortController.abort();
      currentAbortController = null;
    }
  };

  try {
    let responseText = '';
    let providerUsed = '';

    if (isFirstMessage) {
      isFirstMessage = false;

      const payload = { description: text, provider, include_context: true };
      if (currentSessionId) payload.session_id = currentSessionId;
      if (window._screenshotData) {
        payload.screenshot = window._screenshotData;
        window._screenshotData = null;
        document.getElementById('screenshot-area').style.display = 'none';
      }

      const resp = await fetch(`${API_BASE}/api/ai/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal,
      });

      const analysis = await resp.json();

      if (analysis.error && !analysis.diagnosis) {
        throw new Error(analysis.error);
      }

      // Track session ID from response
      if (analysis.session_id) currentSessionId = analysis.session_id;

      responseText = formatAnalysisAsChat(analysis);
      providerUsed = `${analysis.provider || '?'} (${analysis.model || '?'})`;
      chatHistory.push({ role: 'assistant', content: responseText });

    } else {
      const chatPayload = { messages: chatHistory, provider };
      if (currentSessionId) chatPayload.session_id = currentSessionId;
      if (window._screenshotData) {
        chatPayload.screenshot = window._screenshotData;
        window._screenshotData = null;
        document.getElementById('screenshot-area').style.display = 'none';
      }
      const resp = await fetch(`${API_BASE}/api/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chatPayload),
        signal,
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
    if (error.name === 'AbortError') {
      // Remove the user message from history since we cancelled
      chatHistory.pop();
      addChatMessage('system', 'Cancelled.');
    } else {
      addChatMessage('system', `Error: ${error.message}`);
      console.error('[Pulse] Chat error:', error);
    }
  } finally {
    // Clean up SSE progress listeners
    window.removeEventListener('pulse:analysis_progress', progressHandler);
    window.removeEventListener('pulse:scan_progress', progressHandler);
    currentAbortController = null;
    // Restore send button, hide stop button
    sendBtn.style.display = '';
    sendBtn.disabled = false;
    const stopBtnEl = document.getElementById('stop-btn');
    if (stopBtnEl) stopBtnEl.style.display = 'none';
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
    // Add edit button for correction capture
    const editBtn = document.createElement('button');
    editBtn.className = 'msg-edit-btn';
    editBtn.textContent = 'Edit';
    editBtn.style.cssText = 'float:right;padding:2px 8px;font-size:11px;background:#313244;color:#a6adc8;border:1px solid #45475a;border-radius:4px;cursor:pointer;margin-top:4px;';
    editBtn.addEventListener('click', () => startCorrectionEdit(msgEl, content));
    msgEl.appendChild(editBtn);
  }

  chatMessages.appendChild(msgEl);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function startCorrectionEdit(msgEl, originalContent) {
  const textarea = document.createElement('textarea');
  textarea.value = originalContent;
  textarea.style.cssText = 'width:100%;min-height:100px;background:#11111b;color:#cdd6f4;border:1px solid #45475a;border-radius:6px;padding:8px;font-size:14px;resize:vertical;font-family:inherit;';

  const btnRow = document.createElement('div');
  btnRow.style.cssText = 'margin-top:6px;display:flex;gap:8px;';

  const saveBtn = document.createElement('button');
  saveBtn.textContent = 'Save Correction';
  saveBtn.className = 'btn btn-primary';
  saveBtn.style.cssText = 'padding:4px 12px;font-size:12px;';

  const cancelBtn = document.createElement('button');
  cancelBtn.textContent = 'Cancel';
  cancelBtn.style.cssText = 'padding:4px 12px;font-size:12px;background:#45475a;color:#cdd6f4;border:none;border-radius:6px;cursor:pointer;';

  btnRow.appendChild(saveBtn);
  btnRow.appendChild(cancelBtn);

  // Replace message content with editor
  const originalHTML = msgEl.innerHTML;
  msgEl.innerHTML = '';
  msgEl.appendChild(textarea);
  msgEl.appendChild(btnRow);

  cancelBtn.addEventListener('click', () => {
    msgEl.innerHTML = originalHTML;
  });

  saveBtn.addEventListener('click', async () => {
    const corrected = textarea.value.trim();
    if (!corrected || corrected === originalContent) {
      msgEl.innerHTML = originalHTML;
      return;
    }

    try {
      await fetch(`${API_BASE}/api/corrections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          correction_type: 'response_edit',
          original_text: originalContent,
          corrected_text: corrected,
        }),
      });

      // Show the corrected version
      msgEl.innerHTML = formatMessageContent(corrected);
      const editBtn = document.createElement('button');
      editBtn.className = 'msg-edit-btn';
      editBtn.textContent = 'Edit';
      editBtn.style.cssText = 'float:right;padding:2px 8px;font-size:11px;background:#313244;color:#a6adc8;border:1px solid #45475a;border-radius:4px;cursor:pointer;margin-top:4px;';
      editBtn.addEventListener('click', () => startCorrectionEdit(msgEl, corrected));
      msgEl.appendChild(editBtn);

      showNotification('Correction saved — Pulse will learn from this!', 'success');
    } catch (e) {
      showNotification(`Failed to save correction: ${e.message}`, 'error');
      msgEl.innerHTML = originalHTML;
    }
  });

  textarea.focus();
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

export async function handleFixApprove(fixId) {
  const statusDiv = document.querySelector(`.fix-status[data-fix-id="${fixId}"]`);

  try {
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

      resp = await fetch(`${API_BASE}/api/fixes/${fixId}/execute`, { method: 'POST' });
      data = await resp.json();

      if (data.success) {
        statusDiv.innerHTML = `<span style="color:#a6e3a1;">Executed successfully.</span>` +
          (data.output ? `<pre style="background:#11111b;padding:8px;border-radius:4px;margin-top:6px;color:#a6adc8;font-size:12px;max-height:100px;overflow:auto;">${escapeHtml(data.output)}</pre>` : '') +
          `<div style="margin-top:8px;"><span style="color:#a6adc8;">Did this fix the problem?</span> ` +
          `<button class="btn btn-primary fix-yes-btn" style="padding:4px 12px;font-size:12px;margin:0 4px;">Yes</button>` +
          `<button class="btn fix-no-btn" style="padding:4px 12px;font-size:12px;background:#45475a;color:#cdd6f4;border:none;border-radius:6px;cursor:pointer;">No</button></div>`;

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

export async function handleFixReject(fixId) {
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

export async function loadProviderStatus() {
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
