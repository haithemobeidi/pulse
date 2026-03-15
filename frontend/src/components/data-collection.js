/**
 * Data collection button handler with SSE progress
 */

import * as api from '../api/client.js';
import { showNotification } from '../main.js';
import { initDashboard } from '../pages/dashboard.js';

export function setupDataCollection() {
  const collectBtn = document.getElementById('collect-btn');
  if (!collectBtn) return;

  collectBtn.addEventListener('click', async () => {
    const originalText = collectBtn.textContent;
    const steps = { hardware: 'pending', monitors: 'pending', reliability: 'pending' };

    function updateButtonText() {
      const parts = Object.entries(steps).map(([name, status]) => {
        const icon = status === 'done' ? '\u2713' : status === 'running' ? '\u2026' : status === 'error' ? '\u2717' : '\u2022';
        return `${icon} ${name}`;
      });
      collectBtn.textContent = parts.join('  ');
    }

    // Listen for SSE scan progress
    const handler = (e) => {
      const { step, status } = e.detail;
      if (steps.hasOwnProperty(step)) {
        steps[step] = status;
        updateButtonText();
      }
    };
    window.addEventListener('pulse:scan_progress', handler);

    try {
      collectBtn.disabled = true;
      collectBtn.classList.add('btn-loading');
      updateButtonText();
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
      window.removeEventListener('pulse:scan_progress', handler);
      collectBtn.disabled = false;
      collectBtn.textContent = originalText;
      collectBtn.classList.remove('btn-loading');
    }
  });
}
