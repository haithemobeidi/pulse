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
from backend.collectors.reliability import ReliabilityCollector
from backend.ai.reasoning import analyze_issue as ai_analyze, has_any_provider, get_provider_status
from backend.ai.providers import chat_with_failover
from backend.ai.learning import LearningEngine
from backend.database import AiAnalysis, SuggestedFix, FixOutcome

# Enable logging to console for ALL modules
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Make sure backend loggers are set to INFO
backend_logger = logging.getLogger('backend')
backend_logger.setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(_handler)

# Also get collector logger
collector_logger = logging.getLogger('backend.collectors')
collector_logger.setLevel(logging.INFO)

# Server start time (used by frontend to detect restarts)
import time as _time
SERVER_START_TIME = str(int(_time.time()))

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
            'issues': issue_count,
            'server_start': SERVER_START_TIME
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Live Stats Endpoint (lightweight, no database writes)
# ============================================================================

@app.route('/api/live-stats')
def get_live_stats():
    """Get real-time CPU, RAM, GPU stats without running full collectors"""
    stats = {}

    try:
        import psutil
        stats['cpu_percent'] = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        stats['ram_percent'] = mem.percent
        stats['ram_used_gb'] = round(mem.used / (1024**3), 1)
        stats['ram_total_gb'] = round(mem.total / (1024**3), 1)
    except Exception:
        pass

    try:
        from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlDeviceGetTemperature, nvmlDeviceGetUtilizationRates, nvmlShutdown
        nvmlInit()
        handle = nvmlDeviceGetHandleByIndex(0)
        mem_info = nvmlDeviceGetMemoryInfo(handle)
        stats['gpu_vram_used_mb'] = mem_info.used // (1024 * 1024)
        stats['gpu_vram_total_mb'] = mem_info.total // (1024 * 1024)
        stats['gpu_vram_percent'] = round(mem_info.used / mem_info.total * 100, 1)
        try:
            stats['gpu_temp'] = nvmlDeviceGetTemperature(handle, 0)
        except Exception:
            pass
        try:
            util = nvmlDeviceGetUtilizationRates(handle)
            stats['gpu_usage'] = util.gpu
        except Exception:
            pass
        nvmlShutdown()
    except Exception:
        pass

    return jsonify(stats)


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
            'memory': hardware_states.get('memory'),
            'motherboard': hardware_states.get('motherboard'),
            'storage': hardware_states.get('storage'),
            'network': hardware_states.get('network'),
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


@app.route('/api/hardware/gpu/history')
def get_gpu_history():
    """Get GPU state history across snapshots"""
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


@app.route('/api/hardware/monitors/history')
def get_monitor_history():
    """Get monitor state history across snapshots"""
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

        try:
            rel = ReliabilityCollector(db)
            rel.collect(snapshot_id, days=7)  # Last 7 days for issue context
        except Exception as e:
            print(f"Reliability collection error: {e}")

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
# AI Analysis Endpoints
# ============================================================================

@app.route('/api/ai/status')
def ai_status():
    """Check which AI providers are available"""
    return jsonify(get_provider_status())


@app.route('/api/ai/analyze', methods=['POST'])
def analyze():
    """
    Analyze a problem using AI.

    Request body:
        description: str - Description of the problem
        screenshot_path: str (optional) - Path to screenshot
    """
    try:
        data = request.get_json()
        description = data.get('description', '')

        if not description:
            return jsonify({'error': 'Description is required'}), 400

        preferred_provider = data.get('provider', 'auto')  # auto, ollama, gemini, claude
        include_context = data.get('include_context', False)

        # Save screenshot if provided (base64 data URL)
        screenshot_path = None
        screenshot_data = data.get('screenshot')
        if screenshot_data and screenshot_data.startswith('data:image'):
            try:
                import base64
                # Parse data URL: data:image/png;base64,xxxxx
                header, b64data = screenshot_data.split(',', 1)
                ext = 'png' if 'png' in header else 'jpg'
                filename = f"screenshot_{int(time.time())}.{ext}"
                filepath = os.path.join(os.path.dirname(__file__), '..', 'data', 'screenshots', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(base64.b64decode(b64data))
                screenshot_path = filepath
                logger.info(f"Screenshot saved: {filepath}")
            except Exception as e:
                logger.warning(f"Failed to save screenshot: {e}")

        # Build recent context (timeline events + issues from last hour)
        recent_context = ""
        if include_context:
            try:
                recent_records = db.get_recent_reliability_records(days=1, limit=20)
                recent_issues = db.execute(
                    "SELECT * FROM issues ORDER BY timestamp DESC LIMIT 10"
                ).fetchall()
                if recent_records:
                    recent_context += "\n\nRecent system events (last 24h):\n"
                    for r in recent_records[:15]:
                        recent_context += f"- [{r.get('event_time', '')}] {r.get('record_type', '')}: {r.get('source_name', '')} - {(r.get('event_message', '') or '')[:150]}\n"
                if recent_issues:
                    recent_context += "\nRecent issues:\n"
                    for iss in recent_issues[:5]:
                        recent_context += f"- [{iss['timestamp']}] {iss['issue_type']}: {iss['description'][:150]}\n"
            except Exception as e:
                logger.warning(f"Failed to build recent context: {e}")

        # Append context to description
        full_description = description
        if recent_context:
            full_description += recent_context

        # First collect fresh data so AI has current system state
        snapshot = Snapshot(
            snapshot_type=SnapshotType.ISSUE_LOGGED,
            notes=f"AI Analysis: {description[:100]}"
        )
        snapshot_id = db.create_snapshot(snapshot)

        # Run collectors in parallel for speed
        import concurrent.futures

        def _collect_hw():
            try:
                HardwareCollector(db).collect(snapshot_id)
            except Exception as e:
                logger.warning(f"Hardware collection error during AI analysis: {e}")

        def _collect_mon():
            try:
                MonitorCollector(db).collect(snapshot_id)
            except Exception as e:
                logger.warning(f"Monitor collection error during AI analysis: {e}")

        def _collect_rel():
            try:
                ReliabilityCollector(db).collect(snapshot_id, days=14)
            except Exception as e:
                logger.warning(f"Reliability collection error during AI analysis: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(_collect_hw), executor.submit(_collect_mon), executor.submit(_collect_rel)]
            concurrent.futures.wait(futures, timeout=30)

        # Log the issue
        issue = Issue(
            snapshot_id=snapshot_id,
            issue_type=IssueType.OTHER,
            description=description,
            severity=IssueSeverity.MEDIUM
        )
        issue_id = db.create_issue(issue)

        # Run AI analysis with provider preference + context
        analysis = ai_analyze(db, full_description, screenshot_path, preferred_provider)

        # Store analysis in database
        ai_record = AiAnalysis(
            issue_id=issue_id,
            diagnosis=analysis.get('diagnosis', ''),
            confidence=analysis.get('confidence', 0),
            root_cause=analysis.get('root_cause', ''),
            raw_response=json.dumps(analysis),
            model_used=analysis.get('model', 'unknown'),
            tokens_input=analysis.get('tokens_used', {}).get('input', 0),
            tokens_output=analysis.get('tokens_used', {}).get('output', 0),
        )
        analysis_id = db.create_ai_analysis(ai_record)

        # Store each suggested fix with pending status
        stored_fixes = []
        for fix_data in analysis.get('suggested_fixes', []):
            # Ensure all values are scalar (AI may return lists)
            def to_str(v):
                if isinstance(v, list):
                    return '\n'.join(str(i) for i in v)
                return str(v) if v is not None else ''

            def to_float(v):
                if isinstance(v, list):
                    v = v[0] if v else 0.5
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return 0.5

            fix = SuggestedFix(
                analysis_id=analysis_id,
                issue_id=issue_id,
                title=to_str(fix_data.get('title', '')),
                description=to_str(fix_data.get('description', '')),
                risk_level=to_str(fix_data.get('risk_level', 'medium')),
                action_type=to_str(fix_data.get('action_type', 'manual')),
                action_detail=to_str(fix_data.get('action_detail', '')),
                estimated_success=to_float(fix_data.get('estimated_success', 0.5)),
                reversible=bool(fix_data.get('reversible', True)),
                status='pending',
            )
            fix_id = db.create_suggested_fix(fix)
            fix_data['id'] = fix_id
            stored_fixes.append(fix_data)

        analysis['suggested_fixes'] = stored_fixes
        analysis['issue_id'] = issue_id
        analysis['snapshot_id'] = snapshot_id
        analysis['analysis_id'] = analysis_id

        return jsonify(analysis)

    except Exception as e:
        logger.error(f"AI analysis endpoint error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Chat Follow-up Endpoint
# ============================================================================

CHAT_SYSTEM_PROMPT = """You are Pulse, a Windows PC troubleshooting assistant having a conversation with a user about their PC problems.

You have context from a previous diagnosis. The user is now asking follow-up questions or providing more details. Respond naturally and helpfully.

RULES:
1. Focus on what the user is asking in their latest message.
2. Reference the conversation history to stay consistent.
3. If they provide new information, refine your diagnosis.
4. Be conversational — not overly formal or technical.
5. If suggesting commands or steps, be specific and exact.
6. Keep responses concise but thorough.

Respond in plain text (not JSON). Use markdown formatting for readability."""


@app.route('/api/ai/chat', methods=['POST'])
def chat_followup():
    """Follow-up chat message — sends conversation history to AI with system context"""
    try:
        data = request.get_json()
        messages = data.get('messages', [])
        provider = data.get('provider', 'ollama')

        if not messages:
            return jsonify({'error': 'No messages provided'}), 400

        # Build system context from current hardware data
        system_context = ""
        try:
            from backend.ai.reasoning import build_context
            context = build_context(db, messages[-1].get('content', ''))
            hw = context.get('hardware', {})
            gpu = hw.get('gpu', {})
            cpu_data = hw.get('cpu', {}).get('component_data', {})
            mem_data = hw.get('memory', {}).get('component_data', {})

            parts = []
            if gpu:
                parts.append(f"GPU: {gpu.get('gpu_name', '?')} (Driver: {gpu.get('driver_version', '?')})")
            if isinstance(cpu_data, str):
                import json as _json
                try: cpu_data = _json.loads(cpu_data)
                except: cpu_data = {}
            if isinstance(cpu_data, dict) and cpu_data.get('name'):
                parts.append(f"CPU: {cpu_data['name']}")
            if isinstance(mem_data, str):
                try: mem_data = _json.loads(mem_data)
                except: mem_data = {}
            if isinstance(mem_data, dict) and mem_data.get('total_gb'):
                parts.append(f"RAM: {mem_data['total_gb']}GB {mem_data.get('memory_type', '')}")

            if parts:
                system_context = "\n\nUser's system: " + " | ".join(parts)
        except Exception as e:
            logger.warning(f"Could not build chat context: {e}")

        prompt = CHAT_SYSTEM_PROMPT + system_context

        result = chat_with_failover(
            system_prompt=prompt,
            user_message=messages[-1].get('content', ''),
            preferred_provider=provider,
            messages=messages,
        )

        return jsonify({
            'response': result.get('content', ''),
            'provider': result.get('provider', 'unknown'),
            'model': result.get('model', 'unknown'),
        })

    except Exception as e:
        logger.error(f"Chat follow-up error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Fix Approval Endpoints
# ============================================================================

@app.route('/api/fixes/<int:fix_id>/approve', methods=['POST'])
def approve_fix(fix_id):
    """
    Approve a suggested fix for execution.
    The fix will NOT execute automatically - it just marks it as approved.
    A separate execute call is needed.
    """
    try:
        fix = db.get_fix(fix_id)
        if not fix:
            return jsonify({'error': 'Fix not found'}), 404

        if fix['status'] != 'pending':
            return jsonify({'error': f'Fix is already {fix["status"]}'}), 400

        db.update_fix_status(fix_id, 'approved')
        return jsonify({'status': 'approved', 'fix_id': fix_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fixes/<int:fix_id>/reject', methods=['POST'])
def reject_fix(fix_id):
    """Reject a suggested fix"""
    try:
        fix = db.get_fix(fix_id)
        if not fix:
            return jsonify({'error': 'Fix not found'}), 404

        db.update_fix_status(fix_id, 'rejected')
        return jsonify({'status': 'rejected', 'fix_id': fix_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fixes/<int:fix_id>/execute', methods=['POST'])
def execute_fix(fix_id):
    """
    Execute an approved fix. ONLY works if fix status is 'approved'.
    For command-type fixes, runs the command and captures output.
    For manual fixes, just marks as executed.
    """
    try:
        fix = db.get_fix(fix_id)
        if not fix:
            return jsonify({'error': 'Fix not found'}), 404

        if fix['status'] != 'approved':
            return jsonify({
                'error': f'Fix must be approved before execution. Current status: {fix["status"]}'
            }), 400

        action_type = fix.get('action_type', '')
        action_detail = fix.get('action_detail', '')
        output = ""
        success = True

        if action_type == 'command':
            # Execute the command via PowerShell
            import subprocess
            try:
                result = subprocess.run(
                    ["powershell.exe", "-Command", action_detail],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                output = result.stdout + result.stderr
                success = result.returncode == 0
            except subprocess.TimeoutExpired:
                output = "Command timed out after 60 seconds"
                success = False
            except Exception as e:
                output = f"Execution error: {e}"
                success = False

        elif action_type == 'service':
            # Restart a Windows service
            import subprocess
            try:
                result = subprocess.run(
                    ["powershell.exe", "-Command", f"Restart-Service -Name '{action_detail}' -Force"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                output = result.stdout + result.stderr
                success = result.returncode == 0
            except Exception as e:
                output = f"Service restart error: {e}"
                success = False

        elif action_type == 'manual':
            output = "Manual fix - user will follow the instructions"
            success = True

        else:
            output = f"Action type '{action_type}' - user should follow instructions"
            success = True

        db.update_fix_status(fix_id, 'executed', output=output, success=success)

        return jsonify({
            'status': 'executed',
            'fix_id': fix_id,
            'success': success,
            'output': output
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fixes/<int:fix_id>/outcome', methods=['POST'])
def record_fix_outcome(fix_id):
    """
    Record whether a fix actually resolved the issue.
    This is the key learning signal.
    """
    try:
        data = request.get_json()
        resolved = data.get('resolved', False)
        notes = data.get('notes', '')

        fix = db.get_fix(fix_id)
        if not fix:
            return jsonify({'error': 'Fix not found'}), 404

        learning = LearningEngine(db)
        outcome_id = learning.record_outcome(
            fix_id=fix_id,
            issue_id=fix['issue_id'],
            resolved=resolved,
            notes=notes
        )

        return jsonify({
            'status': 'recorded',
            'outcome_id': outcome_id,
            'resolved': resolved
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fixes/issue/<int:issue_id>')
def get_fixes_for_issue(issue_id):
    """Get all suggested fixes for an issue"""
    try:
        fixes = db.get_suggested_fixes(issue_id)
        return jsonify(fixes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Learning & Patterns Endpoints
# ============================================================================

@app.route('/api/patterns')
def get_patterns():
    """Get all learned patterns"""
    try:
        pattern_type = request.args.get('type')
        patterns = db.get_active_patterns(pattern_type)
        return jsonify(patterns)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recommendations')
def get_recommendations():
    """Get preventive recommendations based on learned patterns"""
    try:
        learning = LearningEngine(db)
        recs = learning.get_recommendations()
        return jsonify(recs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Reliability Monitor Endpoints
# ============================================================================

@app.route('/api/reliability/recent')
def get_recent_reliability():
    """Get recent reliability records"""
    try:
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 100, type=int)
        records = db.get_recent_reliability_records(days=days, limit=limit)
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reliability/snapshot/<int:snapshot_id>')
def get_reliability_for_snapshot(snapshot_id):
    """Get reliability records for a specific snapshot"""
    try:
        records = db.get_reliability_records(snapshot_id)
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reliability/summary')
def get_reliability_summary():
    """Get a summary of reliability issues by type"""
    try:
        days = request.args.get('days', 30, type=int)
        records = db.get_recent_reliability_records(days=days, limit=500)

        summary = {
            'total_records': len(records),
            'by_type': {},
            'stability_index': None,
            'recent_crashes': [],
            'recent_installs': [],
        }

        for record in records:
            rtype = record.get('record_type', 'unknown')
            summary['by_type'][rtype] = summary['by_type'].get(rtype, 0) + 1

            if record.get('stability_index') and summary['stability_index'] is None:
                summary['stability_index'] = record['stability_index']

            if 'crash' in rtype and len(summary['recent_crashes']) < 10:
                summary['recent_crashes'].append({
                    'source': record.get('source_name'),
                    'message': record.get('event_message', '')[:200],
                    'time': record.get('event_time'),
                    'product': record.get('product_name')
                })

            if 'install' in rtype and len(summary['recent_installs']) < 10:
                summary['recent_installs'].append({
                    'source': record.get('source_name'),
                    'message': record.get('event_message', '')[:200],
                    'time': record.get('event_time'),
                    'product': record.get('product_name')
                })

        return jsonify(summary)
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
    """Collect all data using parallel threads for speed"""
    import concurrent.futures
    import time as _time

    start = _time.time()
    logger.info("=== COLLECT ALL: Starting ===")

    try:
        # Create snapshot
        snapshot = Snapshot(
            snapshot_type=SnapshotType.SCHEDULED,
            notes='Manual data collection'
        )
        snapshot_id = db.create_snapshot(snapshot)
        logger.info(f"COLLECT: Snapshot {snapshot_id} created in {_time.time()-start:.1f}s")

        results = {
            'status': 'success',
            'snapshot_id': snapshot_id,
            'collections': {}
        }

        def collect_hardware():
            t = _time.time()
            try:
                logger.info("COLLECT: Hardware starting...")
                hw = HardwareCollector(db)
                result = 'ok' if hw.collect(snapshot_id) else 'no_data'
                logger.info(f"COLLECT: Hardware done in {_time.time()-t:.1f}s -> {result}")
                return result
            except Exception as e:
                logger.error(f"COLLECT: Hardware FAILED in {_time.time()-t:.1f}s -> {e}")
                return f'error: {str(e)}'

        def collect_monitors():
            t = _time.time()
            try:
                logger.info("COLLECT: Monitors starting...")
                mon = MonitorCollector(db)
                result = 'ok' if mon.collect(snapshot_id) else 'no_data'
                logger.info(f"COLLECT: Monitors done in {_time.time()-t:.1f}s -> {result}")
                return result
            except Exception as e:
                logger.error(f"COLLECT: Monitors FAILED in {_time.time()-t:.1f}s -> {e}")
                return f'error: {str(e)}'

        def collect_reliability():
            t = _time.time()
            try:
                logger.info("COLLECT: Reliability starting...")
                rel = ReliabilityCollector(db)
                result = 'ok' if rel.collect(snapshot_id, days=30) else 'no_data'
                logger.info(f"COLLECT: Reliability done in {_time.time()-t:.1f}s -> {result}")
                return result
            except Exception as e:
                logger.error(f"COLLECT: Reliability FAILED in {_time.time()-t:.1f}s -> {e}")
                return f'error: {str(e)}'

        # Run all collectors in parallel
        logger.info("COLLECT: Launching 3 threads...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            hw_future = executor.submit(collect_hardware)
            mon_future = executor.submit(collect_monitors)
            rel_future = executor.submit(collect_reliability)

            # Wait with timeout (45 seconds max)
            try:
                results['collections']['hardware'] = hw_future.result(timeout=45)
            except concurrent.futures.TimeoutError:
                logger.error("COLLECT: Hardware TIMED OUT after 45s")
                results['collections']['hardware'] = 'timeout'

            try:
                results['collections']['monitors'] = mon_future.result(timeout=45)
            except concurrent.futures.TimeoutError:
                logger.error("COLLECT: Monitors TIMED OUT after 45s")
                results['collections']['monitors'] = 'timeout'

            try:
                results['collections']['reliability'] = rel_future.result(timeout=45)
            except concurrent.futures.TimeoutError:
                logger.error("COLLECT: Reliability TIMED OUT after 45s")
                results['collections']['reliability'] = 'timeout'

        elapsed = _time.time() - start
        logger.info(f"=== COLLECT ALL: Done in {elapsed:.1f}s === Results: {results['collections']}")
        return jsonify(results)
    except Exception as e:
        logger.error(f"=== COLLECT ALL: EXCEPTION after {_time.time()-start:.1f}s === {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Auto-launch Browser
# ============================================================================

def open_browser(port=5000):
    """Open browser after server starts"""
    time.sleep(1)
    webbrowser.open(f'http://localhost:{port}')


def startup_collect():
    """Run initial data collection on server startup"""
    import time as _time
    _time.sleep(2)  # Wait for Flask to be ready
    logger.info("=== STARTUP: Running initial data collection ===")
    try:
        snapshot = Snapshot(
            snapshot_type=SnapshotType.SCHEDULED,
            notes='Startup auto-collection'
        )
        snapshot_id = db.create_snapshot(snapshot)

        import concurrent.futures
        def _hw():
            try:
                HardwareCollector(db).collect(snapshot_id)
            except Exception as e:
                logger.warning(f"Startup hardware collect failed: {e}")

        def _mon():
            try:
                MonitorCollector(db).collect(snapshot_id)
            except Exception as e:
                logger.warning(f"Startup monitor collect failed: {e}")

        def _rel():
            try:
                ReliabilityCollector(db).collect(snapshot_id, days=30)
            except Exception as e:
                logger.warning(f"Startup reliability collect failed: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(_hw), executor.submit(_mon), executor.submit(_rel)]
            concurrent.futures.wait(futures, timeout=45)

        logger.info("=== STARTUP: Initial collection complete ===")
    except Exception as e:
        logger.error(f"=== STARTUP: Collection failed: {e} ===")


if __name__ == '__main__':
    port = 5000

    # Browser auto-open disabled — use Pulse Manager or existing tab
    # thread = threading.Thread(target=open_browser, args=(port,), daemon=True)
    # thread.start()

    # Run initial data collection in background
    collect_thread = threading.Thread(target=startup_collect, daemon=True)
    collect_thread.start()

    print(f"\n{'='*50}")
    print("Pulse Started")
    print(f"{'='*50}")
    print(f"Dashboard: http://localhost:{port}")
    print(f"API: http://localhost:{port}/api/status")
    print(f"{'='*50}\n")

    # Start Flask (this blocks)
    app.run(host='0.0.0.0', port=port, debug=False)
