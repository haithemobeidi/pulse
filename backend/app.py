"""
PC-Inspector (Pulse) - Flask Application
Single server handles both API and static frontend.
"""

import logging
import threading
from pathlib import Path
from flask import Flask, send_from_directory
from backend.database import db

# Logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
backend_logger = logging.getLogger('backend')
backend_logger.setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(_handler)
logging.getLogger('backend.collectors').setLevel(logging.INFO)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = str(PROJECT_ROOT / 'frontend')

# Flask app
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')

# Database
db.connect()
db.create_schema()

# Register blueprints
from backend.routes.hardware import bp as hardware_bp
from backend.routes.snapshots import bp as snapshots_bp
from backend.routes.issues import bp as issues_bp
from backend.routes.ai import bp as ai_bp
from backend.routes.fixes import bp as fixes_bp
from backend.routes.collection import bp as collection_bp
from backend.routes.reliability import bp as reliability_bp
from backend.routes.system import bp as system_bp
from backend.routes.corrections import bp as corrections_bp

app.register_blueprint(hardware_bp)
app.register_blueprint(snapshots_bp)
app.register_blueprint(issues_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(fixes_bp)
app.register_blueprint(collection_bp)
app.register_blueprint(reliability_bp)
app.register_blueprint(system_bp)
app.register_blueprint(corrections_bp)


# SSE endpoint — registered on app directly to avoid catch-all conflict
@app.route('/api/events')
def sse_events():
    from flask import Response
    from backend.services.events import register_client, event_stream
    client_id = register_client()
    return Response(
        event_stream(client_id),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


# Static file serving — MUST be last (catch-all)
@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(FRONTEND_DIR, path)


# Startup collection
def _startup_collect():
    import time
    time.sleep(2)
    logger.info("=== STARTUP: Running initial data collection ===")
    try:
        from backend.services.collection import run_collection
        run_collection(db, notes='Startup auto-collection')
        logger.info("=== STARTUP: Initial collection complete ===")
    except Exception as e:
        logger.error(f"=== STARTUP: Collection failed: {e} ===")


if __name__ == '__main__':
    port = 5000

    # Start background scheduler for fix holding period checks
    from backend.services.scheduler import start_scheduler
    start_scheduler(db)

    collect_thread = threading.Thread(target=_startup_collect, daemon=True)
    collect_thread.start()

    print(f"\n{'='*50}")
    print("Pulse Started")
    print(f"{'='*50}")
    print(f"Dashboard: http://localhost:{port}")
    print(f"API: http://localhost:{port}/api/status")
    print(f"{'='*50}\n")

    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
