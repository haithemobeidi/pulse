"""Reliability monitor routes — /api/reliability/*"""

from flask import Blueprint, jsonify, request
from backend.database import db

bp = Blueprint('reliability', __name__, url_prefix='/api/reliability')


@bp.route('/recent')
def get_recent():
    try:
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 100, type=int)
        records = db.get_recent_reliability_records(days=days, limit=limit)
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/snapshot/<int:snapshot_id>')
def for_snapshot(snapshot_id):
    try:
        records = db.get_reliability_records(snapshot_id)
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/summary')
def summary():
    try:
        days = request.args.get('days', 30, type=int)
        records = db.get_recent_reliability_records(days=days, limit=500)

        result = {
            'total_records': len(records),
            'by_type': {},
            'stability_index': None,
            'recent_crashes': [],
            'recent_installs': [],
        }

        for record in records:
            rtype = record.get('record_type', 'unknown')
            result['by_type'][rtype] = result['by_type'].get(rtype, 0) + 1

            if record.get('stability_index') and result['stability_index'] is None:
                result['stability_index'] = record['stability_index']

            if 'crash' in rtype and len(result['recent_crashes']) < 10:
                result['recent_crashes'].append({
                    'source': record.get('source_name'),
                    'message': record.get('event_message', '')[:200],
                    'time': record.get('event_time'),
                    'product': record.get('product_name')
                })

            if 'install' in rtype and len(result['recent_installs']) < 10:
                result['recent_installs'].append({
                    'source': record.get('source_name'),
                    'message': record.get('event_message', '')[:200],
                    'time': record.get('event_time'),
                    'product': record.get('product_name')
                })

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
