"""AI analysis and chat routes — /api/ai/*"""

import logging
from flask import Blueprint, jsonify, request
from backend.database import db
from backend.ai.reasoning import get_provider_status
from backend.services.analysis import run_analysis
from backend.services.chat import handle_chat
from backend.services import memory as mem

logger = logging.getLogger(__name__)

bp = Blueprint('ai', __name__, url_prefix='/api/ai')


@bp.route('/status')
def ai_status():
    return jsonify(get_provider_status())


@bp.route('/sessions/new', methods=['POST'])
def create_session():
    """Create a new troubleshooting session and return its ID."""
    session_id = mem.create_session(db)
    return jsonify({'session_id': session_id})


@bp.route('/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session memory contents."""
    memory = mem.get_memory(db, session_id)
    if not memory:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify({'session_id': session_id, 'memory': memory})


@bp.route('/sessions/<session_id>', methods=['DELETE'])
def end_session(session_id):
    """End a session and clean up memory."""
    db.delete_session_memory(session_id)
    return jsonify({'status': 'ok'})


@bp.route('/sessions', methods=['GET'])
def list_sessions():
    """List recent sessions."""
    sessions = db.get_all_sessions(limit=20)
    return jsonify({'sessions': sessions})


@bp.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        description = data.get('description', '')
        session_id = data.get('session_id')

        if not description:
            return jsonify({'error': 'Description is required'}), 400

        # Create a session if none provided
        if not session_id:
            session_id = mem.create_session(db)

        # Extract facts from user's description into session memory
        mem.extract_from_user_message(db, session_id, description)

        # Check for hardware anomalies
        mem.check_hardware_anomalies(db, session_id)

        analysis = run_analysis(
            db,
            description,
            screenshot_data=data.get('screenshot'),
            provider=data.get('provider', 'auto'),
            include_context=data.get('include_context', False),
            session_id=session_id,
        )

        # Extract info from AI response into memory
        mem.extract_from_ai_response(
            db, session_id, analysis.get('diagnosis', ''),
            fixes=analysis.get('suggested_fixes', [])
        )

        analysis['session_id'] = session_id
        return jsonify(analysis)

    except Exception as e:
        logger.error(f"AI analysis endpoint error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/chat', methods=['POST'])
def chat_followup():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        messages = data.get('messages', [])

        # Extract facts from user's latest message into session memory
        if session_id and messages:
            last_msg = messages[-1].get('content', '')
            mem.extract_from_user_message(db, session_id, last_msg)

        result = handle_chat(
            db,
            messages=messages,
            provider=data.get('provider', 'ollama'),
            screenshot_data=data.get('screenshot'),
            session_id=session_id,
        )

        # Extract info from AI response
        if session_id:
            mem.extract_from_ai_response(db, session_id, result.get('response', ''))

        if session_id:
            result['session_id'] = session_id

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Chat follow-up error: {e}")
        return jsonify({'error': str(e)}), 500
