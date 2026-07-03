from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>India Market Sentiment Trader</title>
  <style>
    body { font-family: system-ui, sans-serif; background:#0b1220; color:#e8eefc; margin:0; padding:1.5rem; }
    .card { background:#121a2b; border:1px solid #24304a; border-radius:12px; padding:1rem; margin-bottom:1rem; }
    table { width:100%; border-collapse:collapse; }
    th, td { text-align:left; padding:0.5rem; border-bottom:1px solid #24304a; }
    .ok { color:#3ddc97; }
  </style>
  <script>
    async function refresh() {
      const res = await fetch('/api/status');
      const data = await res.json();
      document.getElementById('equity').textContent = '₹' + Math.round(data.equity_inr).toLocaleString('en-IN');
      document.getElementById('news').textContent = data.news_processed;
      document.getElementById('positions').textContent = data.open_positions;
      document.getElementById('market').textContent = data.market_open ? 'OPEN' : 'CLOSED';
      const rows = data.watchlist.map(r => `<tr>
        <td>${r.symbol}</td><td>₹${r.ltp.toFixed(2)}</td>
        <td>${(r.sentiment ?? 0).toFixed(3)}</td><td>${r.signal}</td></tr>`).join('');
      document.getElementById('tbody').innerHTML = rows;
      document.getElementById('log').innerHTML = (data.recent_activity || [])
        .map(l => `<li>${l}</li>`).join('');
    }
    setInterval(refresh, 2000); refresh();
  </script>
</head>
<body>
  <h1>India Market Sentiment Trader <span class="ok">LIVE</span></h1>
  <div class="card">
    <p>Equity: <strong id="equity">—</strong> · News: <strong id="news">—</strong> · Positions: <strong id="positions">—</strong> · Market: <strong id="market">—</strong></p>
  </div>
  <div class="card">
    <table><thead><tr><th>Symbol</th><th>LTP</th><th>Sentiment</th><th>Signal</th></tr></thead>
    <tbody id="tbody"></tbody></table>
  </div>
  <div class="card"><ul id="log"></ul></div>
</body>
</html>"""


@dataclass
class DashboardState:
    recent_activity: deque[str] = field(default_factory=lambda: deque(maxlen=30))

    def log(self, message: str) -> None:
        ts = datetime.utcnow().strftime("%H:%M:%S")
        self.recent_activity.appendleft(f"[{ts} UTC] {message}")


StatusProvider = Callable[[], Awaitable[dict[str, Any]]]
