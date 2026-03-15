"""Data collection routes — /api/collect/*"""

from flask import Blueprint, jsonify
from backend.database import db
from backend.services.collection import run_collection

bp = Blueprint('collection', __name__, url_prefix='/api/collect')


@bp.route('/all', methods=['POST'])
def collect_all():
    try:
        results = run_collection(db)
        results['status'] = 'success'
        return jsonify(results)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Collect all error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500
