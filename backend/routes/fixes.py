"""Fix approval/execution routes — /api/fixes/*"""

from flask import Blueprint, jsonify, request
from backend.database import db
from backend.services.fixes import approve_fix, reject_fix, execute_fix, record_outcome

bp = Blueprint('fixes', __name__, url_prefix='/api/fixes')


@bp.route('/<int:fix_id>/approve', methods=['POST'])
def approve(fix_id):
    try:
        result, error = approve_fix(db, fix_id)
        if error:
            code = 404 if 'not found' in error.lower() else 400
            return jsonify({'error': error}), code
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:fix_id>/reject', methods=['POST'])
def reject(fix_id):
    try:
        result, error = reject_fix(db, fix_id)
        if error:
            return jsonify({'error': error}), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:fix_id>/execute', methods=['POST'])
def execute(fix_id):
    try:
        result, error = execute_fix(db, fix_id)
        if error:
            code = 404 if 'not found' in error.lower() else 400
            return jsonify({'error': error}), code
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:fix_id>/outcome', methods=['POST'])
def outcome(fix_id):
    try:
        data = request.get_json()
        result, error = record_outcome(
            db, fix_id,
            resolved=data.get('resolved', False),
            notes=data.get('notes', ''),
        )
        if error:
            return jsonify({'error': error}), 404

        # Feed outcome to the living brain
        try:
            fix = db.get_fix(fix_id)
            if fix:
                from backend.services.brain import record_fact
                record_fact(
                    db,
                    symptom=fix.get('description', '') or fix.get('title', ''),
                    diagnosis=None,
                    resolution=fix.get('action_detail') or fix.get('title', ''),
                    worked=data.get('resolved', False),
                    hardware_context=None,
                    source='fix_outcome',
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Brain learning from fix outcome failed: {e}")

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/issue/<int:issue_id>')
def fixes_for_issue(issue_id):
    try:
        fixes = db.get_suggested_fixes(issue_id)
        return jsonify(fixes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
