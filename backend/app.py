"""
PC-Inspector - Simple Flask Application
Single server handles both API and static frontend
"""

import json
import os
import logging
import webbrowser
import threading
import time
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from backend.database import db, Snapshot, SnapshotType, Issue, IssueType, IssueSeverity, GPUState, MonitorState
from backend.collectors.hardware import HardwareCollector
from backend.collectors.monitors import MonitorCollector

# Enable logging to console for ALL modules
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Make sure backend loggers are set to INFO
backend_logger = logging.getLogger('backend')
backend_logger.setLevel(logging.INFO)

# Also get collector logger
collector_logger = logging.getLogger('backend.collectors')
collector_logger.setLevel(logging.INFO)

# Calculate absolute path to frontend directory
PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = str(PROJECT_ROOT / 'frontend')

# Initialize Flask app
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')

# Initialize database
db.connect()
db.create_schema()


# ============================================================================
# Static Files
# ============================================================================

@app.route('/')
def index():
    """Serve index.html"""
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve CSS, JS, and other static files"""
    return send_from_directory(FRONTEND_DIR, path)


# ============================================================================
# API Routes
# ============================================================================

@app.route('/api/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'PC-Inspector',
        'version': '0.1.0'
    })


@app.route('/api/status')
def status():
    """API status"""
    try:
        snapshot_cursor = db.execute("SELECT COUNT(*) FROM snapshots")
        snapshot_count = snapshot_cursor.fetchone()[0]

        issue_cursor = db.execute("SELECT COUNT(*) FROM issues")
        issue_count = issue_cursor.fetchone()[0]

        return jsonify({
            'status': 'ok',
            'database': 'connected',
            'snapshots': snapshot_count,
            'issues': issue_count
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Hardware Endpoints
# ============================================================================

@app.route('/api/hardware/current')
def get_current_hardware():
    """Get current system hardware status"""
    try:
        cursor = db.execute("SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()

        if not row:
            return jsonify({'status': 'no_data', 'message': 'No snapshots available'})

        latest_snapshot_id = row[0]
        gpu = db.get_gpu_state(latest_snapshot_id)
        monitors = db.get_monitor_states(latest_snapshot_id)

        hardware_cursor = db.execute(
            "SELECT component_type, component_data FROM hardware_state WHERE snapshot_id = ?",
            (latest_snapshot_id,)
        )
        hardware_states = {}
        for row in hardware_cursor.fetchall():
            hardware_states[row[0]] = row[1]

        return jsonify({
            'status': 'ok',
            'snapshot_id': latest_snapshot_id,
            'gpu': gpu,
            'monitors': [dict(m) for m in monitors] if monitors else [],
            'monitor_count': len(monitors) if monitors else 0,
            'cpu': hardware_states.get('cpu'),
            'memory': hardware_states.get('memory')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/hardware/gpu')
def get_gpu():
    """Get current GPU status"""
    try:
        cursor = db.execute("SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()

        if not row:
            return jsonify(None)

        gpu = db.get_gpu_state(row[0])
        return jsonify(gpu)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/hardware/monitors')
def get_monitors():
    """Get current monitor status"""
    try:
        cursor = db.execute("SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()

        if not row:
            return jsonify([])

        monitors = db.get_monitor_states(row[0])
        return jsonify([dict(m) for m in monitors])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Snapshots Endpoints
# ============================================================================

@app.route('/api/snapshots', methods=['GET'])
def list_snapshots():
    """List snapshots"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        snapshots = db.get_snapshots(limit=limit, offset=offset)
        return jsonify([dict(s) for s in snapshots])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshots', methods=['POST'])
def create_snapshot():
    """Create snapshot"""
    try:
        data = request.get_json()
        snapshot = Snapshot(
            snapshot_type=data.get('snapshot_type', SnapshotType.MANUAL),
            notes=data.get('notes')
        )
        snapshot_id = db.create_snapshot(snapshot)
        return jsonify({'id': snapshot_id, 'status': 'created'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshots/<int:snapshot_id>')
def get_snapshot(snapshot_id):
    """Get snapshot details"""
    try:
        snapshot = db.get_snapshot(snapshot_id)
        if not snapshot:
            return jsonify({'error': 'Not found'}), 404

        gpu = db.get_gpu_state(snapshot_id)
        monitors = db.get_monitor_states(snapshot_id)

        return jsonify({
            'id': snapshot['id'],
            'timestamp': snapshot['timestamp'],
            'snapshot_type': snapshot['snapshot_type'],
            'notes': snapshot['notes'],
            'gpu_info': gpu,
            'monitors': [dict(m) for m in monitors]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Issues Endpoints
# ============================================================================

@app.route('/api/issues', methods=['GET'])
def list_issues():
    """List issues"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        issues = db.get_issues(limit=limit, offset=offset)
        return jsonify([dict(i) for i in issues])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/issues', methods=['POST'])
def log_issue():
    """Log issue with automatic snapshot"""
    try:
        data = request.get_json()

        # Create snapshot
        snapshot = Snapshot(
            snapshot_type=SnapshotType.ISSUE_LOGGED,
            notes=f"Issue: {data.get('issue_type')}"
        )
        snapshot_id = db.create_snapshot(snapshot)

        # Collect data
        try:
            hw = HardwareCollector(db)
            hw.collect(snapshot_id)
        except Exception as e:
            print(f"Hardware collection error: {e}")

        try:
            mon = MonitorCollector(db)
            mon.collect(snapshot_id)
        except Exception as e:
            print(f"Monitor collection error: {e}")

        # Log issue
        issue = Issue(
            snapshot_id=snapshot_id,
            issue_type=data.get('issue_type', IssueType.OTHER),
            description=data.get('description'),
            severity=data.get('severity', IssueSeverity.MEDIUM)
        )
        issue_id = db.create_issue(issue)

        return jsonify({'id': issue_id, 'snapshot_id': snapshot_id, 'status': 'created'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/issues/<int:issue_id>')
def get_issue(issue_id):
    """Get issue with context"""
    try:
        issue = db.get_issue(issue_id)
        if not issue:
            return jsonify({'error': 'Not found'}), 404

        snapshot_id = issue['snapshot_id']
        gpu = db.get_gpu_state(snapshot_id)
        monitors = db.get_monitor_states(snapshot_id)

        return jsonify({
            'id': issue['id'],
            'snapshot_id': issue['snapshot_id'],
            'issue_type': issue['issue_type'],
            'description': issue['description'],
            'severity': issue['severity'],
            'timestamp': issue['timestamp'],
            'gpu_state': gpu,
            'monitors': [dict(m) for m in monitors]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Data Collection Endpoints
# ============================================================================

@app.route('/api/debug/system-info', methods=['GET'])
def debug_system_info():
    """Debug endpoint to check what system info is available"""
    import logging
    logger = logging.getLogger(__name__)

    debug_info = {
        'psutil': {'available': False, 'info': None},
        'gputil': {'available': False, 'info': None},
        'wmi': {'available': False, 'info': None},
    }

    # Test psutil
    try:
        import psutil
        debug_info['psutil']['available'] = True
        debug_info['psutil']['info'] = {
            'cpu_cores': psutil.cpu_count(logical=False),
            'cpu_threads': psutil.cpu_count(logical=True),
            'memory_gb': psutil.virtual_memory().total / (1024**3),
        }
    except Exception as e:
        debug_info['psutil']['info'] = f"Error: {e}"

    # Test GPUtil
    try:
        import GPUtil
        debug_info['gputil']['available'] = True
        gpus = GPUtil.getGPUs()
        if gpus:
            debug_info['gputil']['info'] = {
                'gpu_count': len(gpus),
                'gpus': [
                    {
                        'id': gpu.id,
                        'name': gpu.name,
                        'memory_total': gpu.memoryTotal,
                        'load': gpu.load,
                        'temp': gpu.temperature,
                    }
                    for gpu in gpus
                ]
            }
        else:
            debug_info['gputil']['info'] = 'No GPUs detected by GPUtil'
    except Exception as e:
        debug_info['gputil']['info'] = f"Error: {e}"

    # Test WMI
    try:
        import wmi
        debug_info['wmi']['available'] = True
        c = wmi.WMI()

        # Try video controllers
        vcs = c.Win32_VideoController()
        debug_info['wmi']['info'] = {
            'video_controllers': [
                {
                    'name': vc.Name,
                    'driver_version': vc.DriverVersion,
                    'adapter_ram': vc.AdapterRAM,
                }
                for vc in vcs
            ] if vcs else []
        }
    except Exception as e:
        debug_info['wmi']['info'] = f"Error: {e}"

    logger.info(f"System debug info: {debug_info}")
    return jsonify(debug_info)


@app.route('/api/collect/all', methods=['POST'])
def collect_all():
    """Collect all data"""
    try:
        # Create snapshot
        snapshot = Snapshot(
            snapshot_type=SnapshotType.SCHEDULED,
            notes='Manual data collection'
        )
        snapshot_id = db.create_snapshot(snapshot)

        results = {
            'status': 'success',
            'snapshot_id': snapshot_id,
            'collections': {}
        }

        # Hardware
        try:
            hw = HardwareCollector(db)
            if hw.collect(snapshot_id):
                results['collections']['hardware'] = 'ok'
            else:
                results['collections']['hardware'] = 'no_data'
        except Exception as e:
            results['collections']['hardware'] = f'error: {str(e)}'

        # Monitors
        try:
            mon = MonitorCollector(db)
            if mon.collect(snapshot_id):
                results['collections']['monitors'] = 'ok'
            else:
                results['collections']['monitors'] = 'no_data'
        except Exception as e:
            results['collections']['monitors'] = f'error: {str(e)}'

        return jsonify(results)
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Auto-launch Browser
# ============================================================================

def open_browser(port=5000):
    """Open browser after server starts"""
    time.sleep(1)
    webbrowser.open(f'http://localhost:{port}')


if __name__ == '__main__':
    port = 5000

    # Open browser in background thread
    thread = threading.Thread(target=open_browser, args=(port,), daemon=True)
    thread.start()

    print(f"\n{'='*50}")
    print("PC-Inspector Started")
    print(f"{'='*50}")
    print(f"Dashboard: http://localhost:{port}")
    print(f"API: http://localhost:{port}/api/status")
    print(f"{'='*50}\n")

    # Start Flask (this blocks)
    app.run(host='0.0.0.0', port=port, debug=False)
