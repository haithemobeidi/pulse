/**
 * Shared frontend utilities
 */

// API base derived from current origin (works on any host/port)
export const API_BASE = window.location.origin;

export function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

export function formatType(type) {
  if (!type) return 'Unknown';
  return type.split('_').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}
