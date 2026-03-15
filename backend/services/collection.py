"""
Collection Service - handles parallel data collection from hardware, monitors, reliability.
Replaces 3 duplicated collection patterns in app.py.
"""

import time
import logging
import concurrent.futures

from backend.database import Snapshot, SnapshotType
from backend.collectors.hardware import HardwareCollector
from backend.collectors.monitors import MonitorCollector
from backend.collectors.reliability import ReliabilityCollector

logger = logging.getLogger(__name__)


def run_collection(db, snapshot_type=SnapshotType.SCHEDULED, notes='Manual data collection', days=30, timeout=45):
    """
    Run parallel data collection (hardware, monitors, reliability).
    Returns dict with snapshot_id and per-collector results.
    """
    start = time.time()
    logger.info("=== Collection starting ===")

    snapshot = Snapshot(snapshot_type=snapshot_type, notes=notes)
    snapshot_id = db.create_snapshot(snapshot)
    logger.info(f"Snapshot {snapshot_id} created in {time.time()-start:.1f}s")

    results = {'snapshot_id': snapshot_id, 'collections': {}}

    def _collect(name, fn):
        t = time.time()
        try:
            from backend.services.events import emit_scan_progress
            emit_scan_progress(name.lower(), 'running')
            logger.info(f"COLLECT: {name} starting...")
            ok = fn()
            result = 'ok' if ok else 'no_data'
            emit_scan_progress(name.lower(), 'done', f'{time.time()-t:.1f}s')
            logger.info(f"COLLECT: {name} done in {time.time()-t:.1f}s -> {result}")
            return result
        except Exception as e:
            try:
                from backend.services.events import emit_scan_progress
                emit_scan_progress(name.lower(), 'error', str(e))
            except Exception:
                pass
            logger.error(f"COLLECT: {name} FAILED in {time.time()-t:.1f}s -> {e}")
            return f'error: {str(e)}'

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            'hardware': executor.submit(_collect, 'Hardware', lambda: HardwareCollector(db).collect(snapshot_id)),
            'monitors': executor.submit(_collect, 'Monitors', lambda: MonitorCollector(db).collect(snapshot_id)),
            'reliability': executor.submit(_collect, 'Reliability', lambda: ReliabilityCollector(db).collect(snapshot_id, days=days)),
        }

        for name, future in futures.items():
            try:
                results['collections'][name] = future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                logger.error(f"COLLECT: {name} TIMED OUT after {timeout}s")
                results['collections'][name] = 'timeout'

    elapsed = time.time() - start
    logger.info(f"=== Collection done in {elapsed:.1f}s === Results: {results['collections']}")
    return results
