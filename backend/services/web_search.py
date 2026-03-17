"""
Web Search Service — gives the troubleshooter access to current information.

The local AI model knows HOW to troubleshoot but lacks CURRENT information
(specific driver bugs, known issues, recent fixes). This service bridges that
gap by searching the web and injecting relevant results into the AI prompt.

Uses DuckDuckGo HTML API (free, no API key needed, just requests).
"""

import json
import logging
import re
from html.parser import HTMLParser
from typing import Dict, Any, List
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# Max results to inject into prompt
MAX_SNIPPETS_IN_PROMPT = 6
MAX_SNIPPET_LENGTH = 300
SEARCH_TIMEOUT = 10

# Domains to filter OUT (spam, shopping, social)
BLOCKED_DOMAINS = [
    'jlaforums.com', 'ebay.com', 'amazon.com', 'aliexpress.com',
    'walmart.com', 'bestbuy.com', 'facebook.com', 'pinterest.com',
    'instagram.com', 'tiktok.com',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}


# ============================================================================
# DuckDuckGo HTML Parser
# ============================================================================

def _extract_real_url(ddg_url: str) -> str:
    """Extract the actual URL from DuckDuckGo's redirect wrapper."""
    # DDG wraps URLs like: //duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.nvidia.com%2F...
    try:
        from urllib.parse import unquote, parse_qs, urlparse as _urlparse
        if 'uddg=' in ddg_url:
            parsed = _urlparse(ddg_url if ddg_url.startswith('http') else 'https:' + ddg_url)
            params = parse_qs(parsed.query)
            if 'uddg' in params:
                return unquote(params['uddg'][0])
        # If it's already a direct URL
        if ddg_url.startswith('http'):
            return ddg_url
        if ddg_url.startswith('//'):
            return 'https:' + ddg_url
    except Exception:
        pass
    return ddg_url


def _parse_ddg_html(html: str) -> List[Dict[str, str]]:
    """Parse DDG HTML results using string operations (more reliable than regex with quoting issues)."""
    results = []
    marker = 'class="result__a"'
    snippet_marker = 'class="result__snippet"'
    pos = 0

    while True:
        # Find next result link
        idx = html.find(marker, pos)
        if idx == -1:
            break

        # Find the href after the marker
        href_start = html.find('href="', idx)
        if href_start == -1 or href_start > idx + 200:
            pos = idx + len(marker)
            continue
        href_start += 6  # skip 'href="'
        href_end = html.find('"', href_start)
        if href_end == -1:
            pos = idx + len(marker)
            continue
        raw_url = html[href_start:href_end]

        # Find the title text (between > and </a>)
        title_start = html.find('>', href_end)
        if title_start == -1:
            pos = idx + len(marker)
            continue
        title_start += 1
        title_end = html.find('</a>', title_start)
        if title_end == -1:
            pos = idx + len(marker)
            continue
        title = html[title_start:title_end].strip()
        # Remove any nested tags from title
        title = re.sub('<[^>]+>', '', title).strip()

        # Find the snippet for this result
        snippet = ''
        snip_idx = html.find(snippet_marker, title_end)
        if snip_idx != -1 and snip_idx < title_end + 2000:
            snip_start = html.find('>', snip_idx)
            if snip_start != -1:
                snip_start += 1
                snip_end = html.find('</a>', snip_start)
                if snip_end != -1:
                    snippet = html[snip_start:snip_end].strip()
                    snippet = re.sub('<[^>]+>', '', snippet).strip()

        url = _extract_real_url(raw_url)

        if title:
            results.append({
                'title': title,
                'snippet': snippet,
                'url': url,
            })

        pos = title_end + 4

    return results


def _ddg_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search DuckDuckGo via HTML API with rate-limit handling."""
    import time

    session = requests.Session()
    session.headers.update(HEADERS)

    for attempt in range(3):
        try:
            resp = session.get(
                'https://html.duckduckgo.com/html/',
                params={'q': query, 'kl': 'us-en'},
                timeout=SEARCH_TIMEOUT,
            )

            # 202 = rate limited / "please wait"
            if resp.status_code == 202:
                logger.info(f"DDG rate limited (attempt {attempt+1}), waiting...")
                time.sleep(2 + attempt * 2)
                continue

            if resp.status_code != 200:
                logger.warning(f"DDG returned status {resp.status_code}")
                break

            results = _parse_ddg_html(resp.text)
            if results:
                return results[:max_results]

            # Got 200 but no results — might be empty SERP
            break

        except Exception as e:
            logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
            break

    return []


# ============================================================================
# Query Building
# ============================================================================

def _get_hardware_info(db) -> Dict[str, Any]:
    """Pull current hardware info from database for query building."""
    hardware = {}
    try:
        cursor = db.execute("SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return hardware
        snapshot_id = row[0]

        gpu = db.get_gpu_state(snapshot_id)
        if gpu:
            hardware['gpu'] = dict(gpu)

        hw_states = db.get_hardware_states(snapshot_id)
        for hw in hw_states:
            hw_dict = dict(hw)
            comp_type = hw_dict.get('component_type', '')
            data = hw_dict.get('component_data', '{}')
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    data = {}
            hardware[comp_type] = data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"Could not get hardware for search: {e}")

    return hardware


def _get_gpu_short(gpu_info: Dict) -> str:
    """'NVIDIA GeForce RTX 5090' -> 'RTX 5090'"""
    name = gpu_info.get('gpu_name', '') or gpu_info.get('name', '')
    for prefix in ['NVIDIA GeForce ', 'NVIDIA ', 'AMD Radeon ', 'AMD ', 'Intel ']:
        name = name.replace(prefix, '')
    return name.strip()


def _build_search_queries(description: str, hardware: Dict[str, Any]) -> List[str]:
    """Generate 2-3 targeted search queries."""
    queries = []
    desc_lower = description.lower()

    gpu_info = hardware.get('gpu', {})
    gpu_short = _get_gpu_short(gpu_info) if gpu_info else ''
    driver_version = gpu_info.get('driver_version', '') if gpu_info else ''

    cpu_info = hardware.get('cpu', {})
    cpu_name = cpu_info.get('name', '') if isinstance(cpu_info, dict) else ''
    if cpu_name:
        cpu_name = cpu_name.split('Processor')[0].strip()

    desc_short = description.strip()[:80]

    gpu_keywords = ['gpu', 'graphics', 'display', 'monitor', 'screen', 'crash',
                    'black screen', 'driver', 'game', 'gaming', 'fps', 'stutter',
                    'artifact', 'flicker', 'tearing', 'nvidia', 'geforce', 'rtx']
    is_gpu_related = any(kw in desc_lower for kw in gpu_keywords)

    cpu_keywords = ['cpu', 'processor', 'thermal', 'throttle', 'bsod', 'blue screen',
                    'ryzen', 'intel', 'overclock']
    is_cpu_related = any(kw in desc_lower for kw in cpu_keywords)

    # Query 1: Problem + specific hardware
    if is_gpu_related and gpu_short:
        q = f"{gpu_short} {desc_short}"
        if driver_version:
            q += f" driver {driver_version}"
        queries.append(q)
    elif is_cpu_related and cpu_name:
        queries.append(f"{cpu_name} {desc_short}")
    else:
        queries.append(f"{desc_short} Windows fix")

    # Query 2: Known issues
    if gpu_short and driver_version:
        queries.append(f"{gpu_short} driver {driver_version} known issues")
    elif gpu_short:
        queries.append(f"{gpu_short} common problems fix")

    # Query 3: Reddit (real user solutions)
    if is_gpu_related and gpu_short:
        queries.append(f"site:reddit.com {gpu_short} {desc_short}")
    else:
        queries.append(f"site:reddit.com {desc_short} fix")

    return queries[:3]


# ============================================================================
# Search + Format
# ============================================================================

def _is_blocked(url: str) -> bool:
    """Check if URL is from a blocked domain."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in BLOCKED_DOMAINS)


def search_web(description: str, hardware: Dict[str, Any]) -> List[Dict[str, str]]:
    """Search the web, filter junk, return relevant results."""
    queries = _build_search_queries(description, hardware)
    all_results = []
    seen_urls = set()

    import time

    for qi, query in enumerate(queries):
        if qi > 0:
            time.sleep(1.5)  # Avoid DDG rate limiting between queries
        results = _ddg_search(query, max_results=5)

        for r in results:
            url = r.get('url', '')
            if _is_blocked(url) or url in seen_urls:
                continue
            seen_urls.add(url)

            snippet = r.get('snippet', '')
            if len(snippet) > MAX_SNIPPET_LENGTH:
                snippet = snippet[:MAX_SNIPPET_LENGTH] + '...'

            all_results.append({
                'title': r.get('title', ''),
                'snippet': snippet,
                'url': url,
                'query': query,
            })

    logger.info(f"Web search: {len(all_results)} results from {len(queries)} queries")
    return all_results[:MAX_SNIPPETS_IN_PROMPT]


def build_search_context(results: List[Dict[str, str]]) -> str:
    """Format search results for AI prompt injection."""
    if not results:
        return ""

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get('title', 'Untitled')
        snippet = r.get('snippet', '')
        url = r.get('url', '')
        try:
            domain = urlparse(url).netloc.replace('www.', '')
        except Exception:
            domain = ''

        lines.append(f"[{i}] {title} ({domain})\n    {snippet}")

    header = "WEB SEARCH RESULTS (current information about this problem -- use these to give specific, up-to-date advice):"
    return header + "\n" + "\n".join(lines)


def search_for_issue(db, description: str) -> str:
    """
    High-level: get hardware context, search web, return formatted prompt section.
    """
    hardware = _get_hardware_info(db)
    results = search_web(description, hardware)
    return build_search_context(results)
