"""System routes — health, status, live-stats, patterns, recommendations, debug"""

import atexit
from flask import Blueprint, jsonify, request
from backend.database import db
from backend.ai.learning import LearningEngine

bp = Blueprint('system', __name__)

# Cached NVML handle — init once, reuse across live-stats polls
_nvml_handle = None
_nvml_available = None

def _get_nvml_handle():
    global _nvml_handle, _nvml_available
    if _nvml_available is False:
        return None
    if _nvml_handle is not None:
        return _nvml_handle
    try:
        from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex
        nvmlInit()
        _nvml_handle = nvmlDeviceGetHandleByIndex(0)
        _nvml_available = True
        atexit.register(_nvml_shutdown)
        return _nvml_handle
    except Exception:
        _nvml_available = False
        return None

def _nvml_shutdown():
    try:
        from pynvml import nvmlShutdown
        nvmlShutdown()
    except Exception:
        pass


@bp.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'PC-Inspector',
        'version': '0.1.0'
    })


@bp.route('/api/status')
def status():
    from backend.routes import _server_start_time
    try:
        snapshot_count = db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        issue_count = db.execute("SELECT COUNT(*) FROM issues").fetchone()[0]

        return jsonify({
            'status': 'ok',
            'database': 'connected',
            'snapshots': snapshot_count,
            'issues': issue_count,
            'server_start': _server_start_time,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@bp.route('/api/live-stats')
def live_stats():
    stats = {}

    try:
        import psutil
        stats['cpu_percent'] = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory()
        stats['ram_percent'] = mem.percent
        stats['ram_used_gb'] = round(mem.used / (1024**3), 1)
        stats['ram_total_gb'] = round(mem.total / (1024**3), 1)
    except Exception:
        pass

    handle = _get_nvml_handle()
    if handle:
        try:
            from pynvml import nvmlDeviceGetMemoryInfo, nvmlDeviceGetTemperature, nvmlDeviceGetUtilizationRates
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
        except Exception:
            pass

    return jsonify(stats)


@bp.route('/api/patterns')
def get_patterns():
    try:
        pattern_type = request.args.get('type')
        patterns = db.get_active_patterns(pattern_type)
        return jsonify(patterns)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/recommendations')
def get_recommendations():
    try:
        learning = LearningEngine(db)
        recs = learning.get_recommendations()
        return jsonify(recs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/debug/system-info')
def debug_system_info():
    debug_info = {
        'psutil': {'available': False, 'info': None},
        'gputil': {'available': False, 'info': None},
        'wmi': {'available': False, 'info': None},
    }

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

    try:
        import GPUtil
        debug_info['gputil']['available'] = True
        gpus = GPUtil.getGPUs()
        if gpus:
            debug_info['gputil']['info'] = {
                'gpu_count': len(gpus),
                'gpus': [{'id': gpu.id, 'name': gpu.name, 'memory_total': gpu.memoryTotal,
                          'load': gpu.load, 'temp': gpu.temperature} for gpu in gpus]
            }
        else:
            debug_info['gputil']['info'] = 'No GPUs detected by GPUtil'
    except Exception as e:
        debug_info['gputil']['info'] = f"Error: {e}"

    try:
        import wmi
        debug_info['wmi']['available'] = True
        c = wmi.WMI()
        vcs = c.Win32_VideoController()
        debug_info['wmi']['info'] = {
            'video_controllers': [
                {'name': vc.Name, 'driver_version': vc.DriverVersion, 'adapter_ram': vc.AdapterRAM}
                for vc in vcs
            ] if vcs else []
        }
    except Exception as e:
        debug_info['wmi']['info'] = f"Error: {e}"

    return jsonify(debug_info)
