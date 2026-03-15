/**
 * Server heartbeat — auto-reload when server restarts
 */

export function startHeartbeat() {
  let serverStartTime = null;
  let wasDown = false;

  async function check() {
    try {
      const resp = await fetch('/api/status');
      if (!resp.ok) throw new Error('not ok');
      const data = await resp.json();

      if (wasDown) {
        console.log('[Pulse] Server is back — reloading');
        location.reload();
        return;
      }

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

  setTimeout(() => setInterval(check, 3000), 5000);
}
