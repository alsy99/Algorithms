from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import aiohttp
import feedparser
import structlog

from sentiment_trader.models import NewsItem

logger = structlog.get_logger(__name__)

DEFAULT_FEEDS = [
    ("moneycontrol", "https://www.moneycontrol.com/rss/latestnews.xml"),
    (
        "et_markets",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    ),
    (
        "business_standard",
        "https://www.business-standard.com/rss/markets-106.rss",
    ),
]


class NewsRssPoller:
    def __init__(self, poll_seconds: int = 120) -> None:
        self._poll_seconds = poll_seconds
        self._seen: set[str] = set()
        self._queue: asyncio.Queue[NewsItem] = asyncio.Queue()

    @property
    def queue(self) -> asyncio.Queue[NewsItem]:
        return self._queue

    async def run(self) -> None:
        while True:
            try:
                await self._poll_once()
            except Exception as exc:
                logger.exception("news_rss.poll_error", error=str(exc))
            await asyncio.sleep(self._poll_seconds)

    async def _poll_once(self) -> None:
        async with aiohttp.ClientSession() as session:
            for source, url in DEFAULT_FEEDS:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status != 200:
                            logger.warning("news_rss.bad_status", source=source, status=resp.status)
                            continue
                        body = await resp.text()
                except Exception as exc:
                    logger.warning("news_rss.fetch_failed", source=source, error=str(exc))
                    continue

                feed = await asyncio.to_thread(feedparser.parse, body)
                for entry in feed.entries:
                    item_id = entry.get("id") or entry.get("link") or entry.get("title", "")
                    if not item_id or item_id in self._seen:
                        continue
                    self._seen.add(item_id)
                    published = entry.get("published_parsed")
                    if published:
                        published_at = datetime(*published[:6], tzinfo=timezone.utc)
                    else:
                        published_at = datetime.now(timezone.utc)
                    text = f"{entry.get('title', '')} {entry.get('summary', '')}".strip()
                    if not text:
                        continue
                    await self._queue.put(
                        NewsItem(
                            id=item_id,
                            source=source,
                            text=text,
                            published_at=published_at,
                            url=entry.get("link", ""),
                        )
                    )
