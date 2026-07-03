from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from sentiment_trader.config import EnvSettings, WatchlistConfig
from sentiment_trader.models import NewsItem

logger = structlog.get_logger(__name__)

SUBREDDITS = ["IndiaInvestments", "IndianStreetBets"]


class RedditPoller:
    def __init__(
        self,
        env: EnvSettings,
        watchlist: WatchlistConfig,
        poll_seconds: int = 60,
    ) -> None:
        self._env = env
        self._watchlist = watchlist
        self._poll_seconds = poll_seconds
        self._seen: set[str] = set()
        self._queue: asyncio.Queue[NewsItem] = asyncio.Queue()
        self._keywords = self._build_keywords()

    @property
    def queue(self) -> asyncio.Queue[NewsItem]:
        return self._queue

    def _build_keywords(self) -> set[str]:
        keys: set[str] = set()
        for entry in self._watchlist.symbols:
            keys.add(entry.symbol.lower())
            for alias in entry.aliases:
                keys.add(alias.lower())
        return keys

    def _is_relevant(self, text: str) -> bool:
        lower = text.lower()
        return any(k in lower for k in self._keywords)

    async def run(self) -> None:
        if not self._env.reddit_client_id or not self._env.reddit_client_secret:
            logger.info("reddit.disabled", reason="missing credentials")
            while True:
                await asyncio.sleep(self._poll_seconds)

        import praw

        reddit = praw.Reddit(
            client_id=self._env.reddit_client_id,
            client_secret=self._env.reddit_client_secret,
            user_agent=self._env.reddit_user_agent,
        )

        while True:
            try:
                for sub_name in SUBREDDITS:
                    subreddit = reddit.subreddit(sub_name)
                    for submission in subreddit.new(limit=25):
                        if submission.id in self._seen:
                            continue
                        text = f"{submission.title} {submission.selftext}".strip()
                        if not self._is_relevant(text):
                            continue
                        self._seen.add(submission.id)
                        published_at = datetime.fromtimestamp(
                            submission.created_utc, tz=timezone.utc
                        )
                        await self._queue.put(
                            NewsItem(
                                id=submission.id,
                                source=f"reddit/{sub_name}",
                                text=text,
                                published_at=published_at,
                                url=f"https://reddit.com{submission.permalink}",
                            )
                        )
            except Exception as exc:
                logger.exception("reddit.poll_error", error=str(exc))
            await asyncio.sleep(self._poll_seconds)
