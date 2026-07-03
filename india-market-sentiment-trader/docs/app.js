const WATCHLIST = [
  { symbol: "RELIANCE", ltp: 2850 },
  { symbol: "TCS", ltp: 4100 },
  { symbol: "HDFCBANK", ltp: 1680 },
  { symbol: "INFY", ltp: 1850 },
  { symbol: "SBIN", ltp: 820 },
  { symbol: "ITC", ltp: 465 },
  { symbol: "BHARTIARTL", ltp: 1580 },
  { symbol: "NIFTYBEES", ltp: 280 },
];

const params = new URLSearchParams(window.location.search);
const API_BASE = params.get("api") || "";

const state = {
  mode: API_BASE ? "live" : "demo",
  equity: 1_000_000,
  newsCount: 0,
  positions: 0,
  rows: WATCHLIST.map((r) => ({
    ...r,
    sentiment: 0,
    momentum: 0,
    signal: "HOLD",
  })),
  log: [],
};

function istMarketOpen() {
  const fmt = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "numeric",
    minute: "numeric",
    hour12: false,
    weekday: "short",
  });
  const parts = Object.fromEntries(fmt.formatToParts(new Date()).map((p) => [p.type, p.value]));
  const day = parts.weekday;
  if (day === "Sat" || day === "Sun") return false;
  const hm = `${parts.hour}:${parts.minute}`;
  return hm >= "9:15" && hm <= "15:30";
}

function pushLog(message) {
  const ts = new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" });
  state.log.unshift(`[${ts} IST] ${message}`);
  state.log = state.log.slice(0, 30);
}

function render() {
  document.getElementById("equity").textContent = `₹${Math.round(state.equity).toLocaleString("en-IN")}`;
  document.getElementById("news-count").textContent = state.newsCount;
  document.getElementById("positions").textContent = state.positions;
  document.getElementById("market-state").textContent = istMarketOpen() ? "OPEN" : "CLOSED";
  document.getElementById("market-time").textContent = new Date().toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
  });

  const status = document.getElementById("bot-status");
  status.textContent = state.mode === "live" ? "Live bot connected" : "Demo simulation";
  status.className = `status-pill ${state.mode === "live" ? "ok" : "demo"}`;
  document.getElementById("mode-label").textContent = `Mode: ${state.mode}`;

  const tbody = document.getElementById("watchlist-body");
  tbody.innerHTML = state.rows
    .map((row) => {
      const sClass = row.sentiment >= 0 ? "sentiment-pos" : "sentiment-neg";
      const sigClass = `signal-${row.signal.toLowerCase()}`;
      return `<tr>
        <td>${row.symbol}</td>
        <td>₹${row.ltp.toFixed(2)}</td>
        <td class="${sClass}">${row.sentiment.toFixed(3)}</td>
        <td>${(row.momentum * 100).toFixed(2)}%</td>
        <td class="${sigClass}">${row.signal}</td>
      </tr>`;
    })
    .join("");

  const logEl = document.getElementById("activity-log");
  logEl.innerHTML = state.log.map((line) => `<li>${line}</li>`).join("");
}

function demoTick() {
  state.rows.forEach((row) => {
    row.ltp = Math.max(1, row.ltp * (1 + (Math.random() - 0.5) * 0.004));
    row.sentiment = Math.max(-1, Math.min(1, row.sentiment + (Math.random() - 0.5) * 0.08));
    row.momentum = (Math.random() - 0.45) * 0.02;
    if (row.sentiment > 0.35 && row.momentum > 0) row.signal = "BUY";
    else if (row.sentiment < -0.25) row.signal = "SELL";
    else row.signal = "HOLD";
  });

  if (Math.random() < 0.35) {
    state.newsCount += 1;
    const sym = state.rows[Math.floor(Math.random() * state.rows.length)].symbol;
    pushLog(`Scored headline mentioning ${sym}`);
  }

  state.equity += (Math.random() - 0.48) * 1500;
  state.positions = Math.floor(Math.random() * 3);
  render();
}

async function fetchLive() {
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.mode = "live";
    state.equity = data.equity_inr ?? state.equity;
    state.newsCount = data.news_processed ?? state.newsCount;
    state.positions = data.open_positions ?? state.positions;
    state.rows = (data.watchlist || []).map((r) => ({
      symbol: r.symbol,
      ltp: r.ltp,
      sentiment: r.sentiment ?? 0,
      momentum: r.momentum ?? 0,
      signal: r.signal ?? "HOLD",
    }));
    if (data.recent_activity) {
      state.log = data.recent_activity;
    }
    render();
  } catch (err) {
    state.mode = "demo";
    pushLog(`Live API unavailable (${err.message}) — using demo simulation`);
    render();
  }
}

async function tick() {
  if (API_BASE) {
    await fetchLive();
  } else {
    demoTick();
  }
}

pushLog("Dashboard started");
render();
setInterval(tick, 2000);
tick();
