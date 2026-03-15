"""Corrections routes — /api/corrections"""

from flask import Blueprint, jsonify, request
from backend.database import db, Correction
from backend.services.style_learning import maybe_regenerate_guide

bp = Blueprint('corrections', __name__, url_prefix='/api/corrections')


@bp.route('', methods=['POST'])
def create_correction():
    """Capture a user correction to AI output."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        correction_type = data.get('correction_type', 'response_edit')
        original = data.get('original_text', '')
        corrected = data.get('corrected_text', '')

        if not original or not corrected:
            return jsonify({'error': 'original_text and corrected_text required'}), 400

        if original == corrected:
            return jsonify({'error': 'No changes detected'}), 400

        correction = Correction(
            correction_type=correction_type,
            original_text=original,
            corrected_text=corrected,
            context=data.get('context', ''),
        )
        correction_id = db.create_correction(correction)

        # Check if we should regenerate the style guide
        scope_map = {
            'diagnosis_edit': 'diagnosis',
            'fix_edit': 'fix_suggestion',
            'response_edit': 'chat_response',
        }
        scope = scope_map.get(correction_type, 'chat_response')
        guide = maybe_regenerate_guide(db, scope)

        return jsonify({
            'correction_id': correction_id,
            'guide_regenerated': guide is not None,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/stats')
def correction_stats():
    """Get correction counts per scope."""
    try:
        stats = {
            'total': db.count_corrections(),
            'by_type': {
                'diagnosis_edit': db.count_corrections('diagnosis_edit'),
                'fix_edit': db.count_corrections('fix_edit'),
                'response_edit': db.count_corrections('response_edit'),
            },
            'style_guides': {},
        }

        for scope in ['diagnosis', 'fix_suggestion', 'chat_response']:
            guide = db.get_style_guide(scope)
            if guide:
                stats['style_guides'][scope] = {
                    'version': guide['version'],
                    'correction_count': guide['correction_count'],
                    'generated_at': guide['generated_at'],
                }

        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
