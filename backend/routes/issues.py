"""Issue API routes — /api/issues/*"""

from flask import Blueprint, jsonify, request
from backend.database import db, Snapshot, SnapshotType, Issue, IssueType, IssueSeverity
from backend.collectors.hardware import HardwareCollector
from backend.collectors.monitors import MonitorCollector
from backend.collectors.reliability import ReliabilityCollector

bp = Blueprint('issues', __name__, url_prefix='/api/issues')


@bp.route('', methods=['GET'])
def list_issues():
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        issues = db.get_issues(limit=limit, offset=offset)
        return jsonify([dict(i) for i in issues])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('', methods=['POST'])
def log_issue():
    try:
        data = request.get_json()

        snapshot = Snapshot(
            snapshot_type=SnapshotType.ISSUE_LOGGED,
            notes=f"Issue: {data.get('issue_type')}"
        )
        snapshot_id = db.create_snapshot(snapshot)

        # Collect context data
        try:
            HardwareCollector(db).collect(snapshot_id)
        except Exception as e:
            print(f"Hardware collection error: {e}")

        try:
            MonitorCollector(db).collect(snapshot_id)
        except Exception as e:
            print(f"Monitor collection error: {e}")

        try:
            ReliabilityCollector(db).collect(snapshot_id, days=7)
        except Exception as e:
            print(f"Reliability collection error: {e}")

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


@bp.route('/<int:issue_id>')
def get_issue(issue_id):
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
