"""Bounded RSS discovery; no automatic claim of independent verification."""
import calendar
import html
import re
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlparse
import feedparser
import requests

FEEDS = {
    'trt': 'https://www.trthaber.com/ekonomi_articles.rss',
    'ntv': 'https://www.ntv.com.tr/ekonomi.rss',
    'dunya': 'https://www.dunya.com/rss',
}


def collect(now):
    candidates, health = {}, {}
    for publisher, url in FEEDS.items():
        try:
            with requests.get(url, timeout=(10, 25), stream=True,
                              headers={'User-Agent': 'MDT-FuelMonitor/1.0'}) as response:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 4_000_000:
                        raise ValueError('Feed size limit')
            feed = feedparser.parse(bytes(content))
            if not feed.entries:
                raise ValueError('Empty or invalid feed')
            relevant = 0
            for entry in feed.entries[:200]:
                title = html.unescape(re.sub('<[^>]+>', '', entry.get('title', ''))).strip()
                if not re.search(r'benzin|motorin|akaryakıt|akaryakit|lpg|otogaz', title, re.I):
                    continue
                link = entry.get('link', '')
                if urlparse(link).scheme != 'https':
                    continue
                published = entry.get('published_parsed') or entry.get('updated_parsed')
                if not published:
                    continue
                published = datetime.fromtimestamp(calendar.timegm(published), timezone.utc)
                if not now - timedelta(hours=72) <= published <= now + timedelta(minutes=5):
                    continue
                key = sha256(link.encode()).hexdigest()
                candidates[key] = dict(title=title[:500], url=link, publisher=publisher,
                                       publishedAt=published, discoveredAt=now)
                relevant += 1
            health[publisher] = dict(ok=True, entries=len(feed.entries), candidates=relevant)
        except (requests.RequestException, ValueError) as exc:
            health[publisher] = dict(ok=False, error=type(exc).__name__)
    return candidates, health
