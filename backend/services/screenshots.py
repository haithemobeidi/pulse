"""
Screenshot Service - save and describe screenshot images.
"""

import os
import time
import base64
import logging

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'screenshots')


def save_screenshot(data_url):
    """
    Save a base64 data URL screenshot to disk.
    Returns filepath or None on failure.
    """
    if not data_url or not data_url.startswith('data:image'):
        return None

    try:
        header, b64data = data_url.split(',', 1)
        ext = 'png' if 'png' in header else 'jpg'
        filename = f"screenshot_{int(time.time())}.{ext}"
        filepath = os.path.join(SCREENSHOT_DIR, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(b64data))
        logger.info(f"Screenshot saved: {filepath}")
        return filepath
    except Exception as e:
        logger.warning(f"Failed to save screenshot: {e}")
        return None


def describe_screenshot(filepath):
    """
    Get a text description of a screenshot using the vision model.
    Returns description string or None.
    """
    if not filepath:
        return None

    try:
        from backend.ai.reasoning import _describe_image
        description = _describe_image(filepath)
        if description:
            logger.info(f"Image described: {description[:100]}...")
        return description
    except Exception as e:
        logger.warning(f"Screenshot description failed: {e}")
        return None
