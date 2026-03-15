/**
 * Learning page — visualize how Pulse learns from fix history
 */

import { escapeHtml, API_BASE } from '../utils.js';
import { formatDate } from '../main.js';

export async function initLearning() {
  console.log('Loading learning dashboard...');

  // Load all data in parallel
  const [patterns, corrections, fixes, embeddings] = await Promise.all([
    fetchJSON('/api/learning/overview'),
    fetchJSON('/api/corrections/stats'),
    fetchJSON('/api/learning/fixes'),
    fetchJSON('/api/learning/embeddings'),
  ]);

  renderStats(patterns, corrections, embeddings);
  renderPatterns(patterns);
  renderFixes(fixes);
  renderStyleGuides(corrections);
  renderCorrections(corrections);
}

async function fetchJSON(path) {
  try {
    const resp = await fetch(`${API_BASE}${path}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch (e) {
    console.warn(`Failed to fetch ${path}:`, e);
    return null;
  }
}

function renderStats(patterns, corrections, embeddings) {
  const patternCount = document.getElementById('learning-pattern-count');
  const correctionCount = document.getElementById('learning-correction-count');
  const embeddingCount = document.getElementById('learning-embedding-count');

  if (patternCount) {
    const count = patterns?.patterns?.length || 0;
    patternCount.textContent = count;
  }
  if (correctionCount) {
    correctionCount.textContent = corrections?.total || 0;
  }
  if (embeddingCount) {
    const count = embeddings?.total || 0;
    embeddingCount.textContent = count;
  }
}

function renderPatterns(data) {
  const container = document.getElementById('learning-patterns');
  if (!container) return;

  const patterns = data?.patterns || [];
  if (patterns.length === 0) {
    container.innerHTML = '<p style="color:var(--text-secondary);font-size:13px;">No patterns learned yet. Use Pulse to diagnose and fix issues — patterns emerge after 2+ fix outcomes.</p>';
    return;
  }

  let html = '';
  patterns.forEach(p => {
    const stored = Math.round((p.confidence || 0) * 100);
    const decayed = Math.round((p.decayed_confidence || 0) * 100);
    const barColor = decayed > 60 ? 'var(--success)' : decayed > 30 ? 'var(--warning)' : 'var(--error)';
    const typeIcon = {
      fix_effectiveness: '\u2699',
      recurring_issue: '\u21BB',
      change_trigger: '\u26A1',
    }[p.pattern_type] || '\u2022';
    const typeLabel = {
      fix_effectiveness: 'Fix Effectiveness',
      recurring_issue: 'Recurring Issue',
      change_trigger: 'Change Trigger',
    }[p.pattern_type] || p.pattern_type;

    html += `
      <div class="learning-pattern-item">
        <div class="learning-pattern-header">
          <span class="learning-pattern-type">${typeIcon} ${typeLabel}</span>
          <span class="learning-pattern-stats">
            seen ${p.times_seen}x${p.times_failed ? `, failed ${p.times_failed}x` : ''}
          </span>
        </div>
        <div class="learning-pattern-desc">${escapeHtml(p.description)}</div>
        <div class="learning-confidence-row">
          <div class="learning-confidence-bar-bg">
            <div class="learning-confidence-bar-stored" style="width:${stored}%;"></div>
            <div class="learning-confidence-bar-decayed" style="width:${decayed}%;background:${barColor};"></div>
          </div>
          <span class="learning-confidence-label">${decayed}%</span>
        </div>
        <div class="learning-pattern-meta">
          Stored: ${stored}% | Decayed: ${decayed}%${p.last_activity_at ? ` | Last active: ${formatDate(p.last_activity_at)}` : ''}
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

function renderFixes(data) {
  const container = document.getElementById('learning-fixes');
  if (!container) return;

  const fixes = data?.fixes || [];
  if (fixes.length === 0) {
    container.innerHTML = '<p style="color:var(--text-secondary);font-size:13px;">No fixes tracked yet. When AI suggests fixes and you approve/execute them, they\'ll appear here.</p>';
    return;
  }

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

  let html = '';
  fixes.forEach(f => {
    const color = stateColors[f.status] || 'var(--text-secondary)';
    const holdingInfo = f.status === 'holding' && f.auto_verify_at
      ? ` (auto-resolves: ${formatDate(f.auto_verify_at)})`
      : '';

    html += `
      <div class="learning-fix-item">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:13px;"><strong>${escapeHtml(f.title || 'Untitled fix')}</strong></span>
          <span class="learning-fix-state" style="background:${color};">${f.status}${holdingInfo}</span>
        </div>
        <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">
          ${f.action_type ? `Type: ${f.action_type}` : ''}
          ${f.executed_at ? ` | Executed: ${formatDate(f.executed_at)}` : ''}
          ${f.execution_success !== null ? ` | Success: ${f.execution_success ? 'Yes' : 'No'}` : ''}
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

function renderStyleGuides(data) {
  const container = document.getElementById('learning-style-guides');
  if (!container) return;

  const guides = data?.style_guides || {};
  if (Object.keys(guides).length === 0) {
    const total = data?.total || 0;
    const remaining = Math.max(0, 3 - total);
    container.innerHTML = `<p style="color:var(--text-secondary);font-size:13px;">
      No style guides generated yet.${remaining > 0 ? ` Edit ${remaining} more AI response(s) to generate your first guide.` : ' Processing...'}
    </p>`;
    return;
  }

  let html = '';
  for (const [scope, guide] of Object.entries(guides)) {
    html += `
      <div class="learning-guide-item">
        <div class="learning-guide-header">
          <strong>${escapeHtml(scope)}</strong>
          <span style="font-size:11px;color:var(--text-secondary);">v${guide.version} | ${guide.correction_count} corrections | ${formatDate(guide.generated_at)}</span>
        </div>
      </div>
    `;
  }

  container.innerHTML = html;
}

function renderCorrections(data) {
  const container = document.getElementById('learning-corrections');
  if (!container) return;

  const byType = data?.by_type || {};
  const total = data?.total || 0;

  if (total === 0) {
    container.innerHTML = '<p style="color:var(--text-secondary);font-size:13px;">No corrections yet. Click "Edit" on any AI response to start teaching Pulse your preferences.</p>';
    return;
  }

  let html = '<div class="learning-corrections-grid">';
  const labels = {
    diagnosis_edit: 'Diagnosis edits',
    fix_edit: 'Fix edits',
    response_edit: 'Response edits',
  };

  for (const [type, count] of Object.entries(byType)) {
    const label = labels[type] || type;
    const pct = total > 0 ? Math.round((count / total) * 100) : 0;
    html += `
      <div class="learning-correction-stat">
        <div style="font-size:20px;font-weight:600;color:var(--accent);">${count}</div>
        <div style="font-size:12px;color:var(--text-secondary);">${label}</div>
        <div style="margin-top:4px;height:3px;background:var(--bg-tertiary);border-radius:2px;">
          <div style="height:100%;width:${pct}%;background:var(--accent);border-radius:2px;"></div>
        </div>
      </div>
    `;
  }
  html += '</div>';

  container.innerHTML = html;
}
