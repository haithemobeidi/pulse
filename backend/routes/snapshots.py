"""Snapshot API routes — /api/snapshots/*"""

from flask import Blueprint, jsonify, request
from backend.database import db, Snapshot, SnapshotType

bp = Blueprint('snapshots', __name__, url_prefix='/api/snapshots')


@bp.route('', methods=['GET'])
def list_snapshots():
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        snapshots = db.get_snapshots(limit=limit, offset=offset)
        return jsonify([dict(s) for s in snapshots])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('', methods=['POST'])
def create_snapshot():
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


@bp.route('/<int:snapshot_id>')
def get_snapshot(snapshot_id):
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
