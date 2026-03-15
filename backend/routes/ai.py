"""AI analysis and chat routes — /api/ai/*"""

from flask import Blueprint, jsonify, request
from backend.database import db
from backend.ai.reasoning import get_provider_status
from backend.services.analysis import run_analysis
from backend.services.chat import handle_chat

bp = Blueprint('ai', __name__, url_prefix='/api/ai')


@bp.route('/status')
def ai_status():
    return jsonify(get_provider_status())


@bp.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        description = data.get('description', '')

        if not description:
            return jsonify({'error': 'Description is required'}), 400

        analysis = run_analysis(
            db,
            description,
            screenshot_data=data.get('screenshot'),
            provider=data.get('provider', 'auto'),
            include_context=data.get('include_context', False),
        )
        return jsonify(analysis)

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"AI analysis endpoint error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/chat', methods=['POST'])
def chat_followup():
    try:
        data = request.get_json()
        result = handle_chat(
            db,
            messages=data.get('messages', []),
            provider=data.get('provider', 'ollama'),
            screenshot_data=data.get('screenshot'),
        )
        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Chat follow-up error: {e}")
        return jsonify({'error': str(e)}), 500
