// 個人用 RS スクリーナー
// data/screener.json を読み込み、テーマカード＋銘柄表を描画

const TT_RANK = { 強い: 3, 普通: 2, 弱い: 1 };
const HQM_RANK = { Top: 4, Strong: 3, Good: 2, Fair: 1, Poor: 0 };

let DATA = null;

async function loadData() {
  try {
    const res = await fetch("./data/screener.json?t=" + Date.now());
    if (!res.ok) throw new Error("data load failed");
    DATA = await res.json();
  } catch (e) {
    // フォールバック（ローカル閲覧用サンプル）
    DATA = window.SAMPLE_DATA;
  }
  render();
}

function hqmLabel(score) {
  if (score == null || score < 0) return { text: "—", cls: "gray", tag: "Poor" };
  if (score >= 90) return { text: `${score}（Top）`, cls: "green", tag: "Top" };
  if (score >= 80) return { text: `${score}（Strong）`, cls: "green", tag: "Strong" };
  if (score >= 70) return { text: `${score}（Good）`, cls: "yellow", tag: "Good" };
  if (score >= 50) return { text: `${score}（Fair）`, cls: "yellow", tag: "Fair" };
  return { text: `${score}（Poor）`, cls: "red", tag: "Poor" };
}

function ttBadge(tt) {
  if (tt === "強い") return "green";
  if (tt === "普通") return "yellow";
  return "red";
}

function stageBadge(stage) {
  if (String(stage).includes("2")) return "green";
  if (String(stage).includes("1") || String(stage).includes("3")) return "yellow";
  return "red";
}

function rsClass(rs) {
  if (rs >= 80) return "high";
  if (rs >= 50) return "mid";
  return "low";
}

function themeClass(label) {
  if (label === "強い") return "strong";
  if (label === "普通") return "moderate";
  return "weak";
}

function renderThemes(themes) {
  const el = document.getElementById("themeCards");
  el.innerHTML = themes
    .map(
      (t) => `
    <div class="theme-card ${themeClass(t.label)}">
      <div class="theme-top">
        <div class="theme-name">${t.name}</div>
        <div style="text-align:right">
          <div class="theme-score">${t.score}</div>
          <div class="theme-label">${t.label}</div>
        </div>
      </div>
      <div class="theme-leaders">
        リーダー
        ${(t.leaders || []).map((x) => `<span>${x}</span>`).join("") || "<span>—</span>"}
      </div>
    </div>`
    )
    .join("");
}

function sortedStocks(stocks) {
  const stage2Only = document.getElementById("stage2Only").checked;
  const sortBy = document.getElementById("sortBy").value;
  let list = [...stocks];
  if (stage2Only) {
    list = list.filter((s) => String(s.stage).includes("2"));
  }
  list.sort((a, b) => {
    if (sortBy === "rs") return (b.rs || 0) - (a.rs || 0);
    if (sortBy === "hqm") return (b.hqm || 0) - (a.hqm || 0);
    if (sortBy === "tt") return (TT_RANK[b.tt] || 0) - (TT_RANK[a.tt] || 0);
    if (sortBy === "theme") return String(a.theme).localeCompare(String(b.theme), "ja");
    return 0;
  });
  return list;
}

function renderTable(stocks) {
  const body = document.getElementById("stockBody");
  const list = sortedStocks(stocks);
  if (!list.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty">該当銘柄なし（フィルターを緩めてください）</td></tr>`;
    return;
  }
  body.innerHTML = list
    .map((s) => {
      const h = hqmLabel(s.hqm);
      return `
      <tr>
        <td>
          <span class="ticker">${s.ticker}</span>
          <span class="ticker-name">${s.name || ""}</span>
        </td>
        <td class="rs ${rsClass(s.rs)}">${s.rs}</td>
        <td><span class="badge ${stageBadge(s.stage)}">${s.stage}</span></td>
        <td>${s.industry || "—"}</td>
        <td>${s.theme || "—"}</td>
        <td><span class="badge ${ttBadge(s.tt)}">${s.tt}</span></td>
        <td class="hqm-cell"><span class="badge ${h.cls}">${h.text}</span></td>
      </tr>`;
    })
    .join("");
}

function render() {
  if (!DATA) return;
  document.getElementById("lastUpdated").textContent =
    "更新: " + (DATA.updated_at || "—");
  renderThemes(DATA.themes || []);
  renderTable(DATA.stocks || []);
}

document.getElementById("stage2Only").addEventListener("change", render);
document.getElementById("sortBy").addEventListener("change", render);
document.getElementById("refreshBtn").addEventListener("click", loadData);

// サンプルデータ（data/screener.json が無いときのフォールバック）
window.SAMPLE_DATA = {
  updated_at: "2026-08-19 16:00 ET（サンプル）",
  themes: [
    {
      name: "AI/半導体",
      score: 92,
      label: "強い",
      leaders: ["NVDA", "AVGO", "TSM"],
    },
    {
      name: "サイバーセキュリティ",
      score: 74,
      label: "普通",
      leaders: ["CRWD", "PANW"],
    },
    {
      name: "バイオテック",
      score: 38,
      label: "弱い",
      leaders: [],
    },
  ],
  stocks: [
    {
      ticker: "NVDA",
      name: "NVIDIA Corporation",
      rs: 98,
      stage: "Stage2 ↑",
      industry: "Semiconductors",
      theme: "AI/半導体",
      tt: "強い",
      hqm: 92,
    },
    {
      ticker: "AVGO",
      name: "Broadcom Inc.",
      rs: 94,
      stage: "Stage2 ↑",
      industry: "Semiconductors",
      theme: "AI/半導体",
      tt: "強い",
      hqm: 89,
    },
    {
      ticker: "CRWD",
      name: "CrowdStrike Holdings",
      rs: 76,
      stage: "Stage2 →",
      industry: "Software - Infrastructure",
      theme: "サイバーセキュリティ",
      tt: "普通",
      hqm: 81,
    },
    {
      ticker: "PANW",
      name: "Palo Alto Networks",
      rs: 71,
      stage: "Stage2 →",
      industry: "Software - Infrastructure",
      theme: "サイバーセキュリティ",
      tt: "普通",
      hqm: 74,
    },
    {
      ticker: "SNOW",
      name: "Snowflake Inc.",
      rs: 64,
      stage: "Stage1 →",
      industry: "Software - Application",
      theme: "クラウド / データ",
      tt: "弱い",
      hqm: 68,
    },
    {
      ticker: "REGN",
      name: "Regeneron Pharmaceuticals",
      rs: 42,
      stage: "Stage4 ↓",
      industry: "Biotechnology",
      theme: "バイオテック",
      tt: "弱い",
      hqm: 45,
    },
    {
      ticker: "AMGN",
      name: "Amgen Inc.",
      rs: 34,
      stage: "Stage4 ↓",
      industry: "Biotechnology",
      theme: "バイオテック",
      tt: "弱い",
      hqm: 38,
    },
  ],
};

loadData();
