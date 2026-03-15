"""Hardware API routes — /api/hardware/*"""

from flask import Blueprint, jsonify, request
from backend.database import db

bp = Blueprint('hardware', __name__, url_prefix='/api/hardware')


@bp.route('/current')
def get_current_hardware():
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
            'memory': hardware_states.get('memory'),
            'motherboard': hardware_states.get('motherboard'),
            'storage': hardware_states.get('storage'),
            'network': hardware_states.get('network'),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@bp.route('/gpu')
def get_gpu():
    try:
        cursor = db.execute("SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return jsonify(None)
        gpu = db.get_gpu_state(row[0])
        return jsonify(gpu)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/monitors')
def get_monitors():
    try:
        cursor = db.execute("SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return jsonify([])
        monitors = db.get_monitor_states(row[0])
        return jsonify([dict(m) for m in monitors])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/gpu/history')
def get_gpu_history():
    try:
        limit = request.args.get('limit', 20, type=int)
        rows = db.execute(
            """SELECT g.*, s.timestamp, s.snapshot_type
               FROM gpu_state g
               JOIN snapshots s ON g.snapshot_id = s.id
               ORDER BY s.timestamp DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/monitors/history')
def get_monitor_history():
    try:
        limit = request.args.get('limit', 20, type=int)
        rows = db.execute(
            """SELECT m.*, s.timestamp, s.snapshot_type
               FROM monitor_state m
               JOIN snapshots s ON m.snapshot_id = s.id
               ORDER BY s.timestamp DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
