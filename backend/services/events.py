"""
Server-Sent Events (SSE) service — real-time progress events to frontend.

Event types:
- scan_progress: data collection step updates
- analysis_progress: AI analysis step updates
- fix_status: fix state machine transitions
"""

import json
import logging
import threading
import time
from collections import deque
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Per-client event queues. Key = client_id, Value = deque of events
_clients: Dict[str, deque] = {}
_clients_lock = threading.Lock()
_client_counter = 0


def _next_client_id() -> str:
    global _client_counter
    _client_counter += 1
    return f"client-{_client_counter}"


def register_client() -> str:
    """Register a new SSE client and return its ID."""
    client_id = _next_client_id()
    with _clients_lock:
        _clients[client_id] = deque(maxlen=100)
    logger.debug(f"SSE client registered: {client_id}")
    return client_id


def unregister_client(client_id: str):
    """Remove a client's event queue."""
    with _clients_lock:
        _clients.pop(client_id, None)
    logger.debug(f"SSE client unregistered: {client_id}")


def emit(event_type: str, data: Dict[str, Any]):
    """Broadcast an event to all connected clients."""
    event = {
        'type': event_type,
        'data': data,
        'timestamp': time.time(),
    }
    with _clients_lock:
        for queue in _clients.values():
            queue.append(event)


def get_events(client_id: str) -> Optional[Dict]:
    """Get the next event for a client (non-blocking). Returns None if empty."""
    with _clients_lock:
        queue = _clients.get(client_id)
        if queue:
            try:
                return queue.popleft()
            except IndexError:
                return None
    return None


def event_stream(client_id: str):
    """Generator that yields SSE-formatted events for a client."""
    try:
        while True:
            event = get_events(client_id)
            if event:
                event_type = event.get('type', 'message')
                data = json.dumps(event.get('data', {}))
                yield f"event: {event_type}\ndata: {data}\n\n"
            else:
                # Send keepalive comment every 15s
                yield ": keepalive\n\n"
                time.sleep(1)
    except GeneratorExit:
        unregister_client(client_id)


# Convenience emit functions
def emit_scan_progress(step: str, status: str, detail: str = ''):
    """Emit a scan progress event."""
    emit('scan_progress', {'step': step, 'status': status, 'detail': detail})


def emit_analysis_progress(step: str, status: str = 'running', detail: str = ''):
    """Emit an analysis progress event."""
    emit('analysis_progress', {'step': step, 'status': status, 'detail': detail})


def emit_fix_status(fix_id: int, old_state: str, new_state: str, event: str):
    """Emit a fix state transition event."""
    emit('fix_status', {
        'fix_id': fix_id,
        'old_state': old_state,
        'new_state': new_state,
        'event': event,
    })
