/* Stage2 Entry Screener front-end */

let DATA = {
  updated_at: "—",
  stocks: [],
  industries: [],
  entry_count: 0,
  active_count: 0,
};

const $ = (id) => document.getElementById(id);

function statusClass(status) {
  if (status === "Entry") return "tag green";
  return "tag yellow";
}

function buildIndustryMap(industries) {
  const map = {};
  (industries || []).forEach((x) => {
    map[x.name] = x;
  });
  return map;
}

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderIndustries() {
  const el = $("industryList");
  if (!el) return;
  const list = DATA.industries || [];
  if (!list.length) {
    el.innerHTML = '<p class="empty">業種データなし</p>';
    return;
  }
  el.innerHTML = list
    .slice(0, 40)
    .map((x) => {
      const cls =
        x.label === "強い" ? "strong" : x.label === "弱い" ? "weak" : "mid";
      return `<div class="theme-card ${cls}">
        <div class="theme-name">${escapeHtml(x.name)}</div>
        <div class="theme-score">${x.score} <span class="label">${escapeHtml(
        x.label || ""
      )}</span></div>
        <div class="theme-leaders">${(x.leaders || [])
          .map(escapeHtml)
          .join(" · ")}</div>
      </div>`;
    })
    .join("");
}

function getFilteredSorted() {
  const entryOnly = $("fltEntry")?.checked !== false;
  const showActive = $("fltActive")?.checked === true;
  const indMap = buildIndustryMap(DATA.industries);

  let rows = (DATA.stocks || []).filter((s) => {
    if (s.stage2_entry) return true;
    if (showActive && s.stage2_active) return true;
    return false;
  });

  if (entryOnly && !showActive) {
    rows = rows.filter((s) => s.stage2_entry);
  }

  const sortBy = $("sortBy")?.value || "rs";
  rows = [...rows].sort((a, b) => {
    if (sortBy === "industry") {
      return String(a.industry || "").localeCompare(String(b.industry || ""));
    }
    if (sortBy === "indScore") {
      const sa = indMap[a.industry]?.score ?? 0;
      const sb = indMap[b.industry]?.score ?? 0;
      return sb - sa || (b.rs || 0) - (a.rs || 0);
    }
    if (sortBy === "breakout") {
      return (b.breakout_pct || -999) - (a.breakout_pct || -999);
    }
    if (a.stage2_entry !== b.stage2_entry) {
      return a.stage2_entry ? -1 : 1;
    }
    return (b.rs || 0) - (a.rs || 0);
  });

  return { rows, indMap };
}

function renderTable() {
  const body = $("stockBody");
  const hint = $("table-empty-hint");
  if (!body) return;

  const { rows, indMap } = getFilteredSorted();
  if (!rows.length) {
    body.innerHTML = "";
    if (hint) {
      hint.hidden = false;
      hint.textContent = "該当銘柄がありません。フィルターを確認してください。";
    }
    return;
  }
  if (hint) hint.hidden = true;

  body.innerHTML = rows
    .map((s) => {
      const indScore = indMap[s.industry]?.score;
      const status = s.stage2_entry ? "Entry" : "Active";
      return `<tr>
        <td><strong>${escapeHtml(s.ticker)}</strong></td>
        <td><span class="${statusClass(status)}">${status}</span></td>
        <td>${s.rs ?? "—"}</td>
        <td>${s.breakout_pct != null ? Number(s.breakout_pct).toFixed(2) + "%" : "—"}</td>
        <td>${s.pct_from_30w != null ? Number(s.pct_from_30w).toFixed(2) + "%" : "—"}</td>
        <td>${escapeHtml(s.industry || "—")}</td>
        <td>${indScore != null ? indScore : "—"}</td>
        <td>${s.price != null ? s.price : "—"}</td>
      </tr>`;
    })
    .join("");
}

function renderMeta() {
  if ($("updatedAt")) {
    $("updatedAt").textContent = `更新: ${DATA.updated_at || "—"}`;
  }
  if ($("counts")) {
    $("counts").textContent = `Entry: ${DATA.entry_count ?? "—"} / Active: ${
      DATA.active_count ?? "—"
    }`;
  }
}

function copyTvList() {
  const { rows } = getFilteredSorted();
  const text = rows.map((s) => s.ticker).join(",");
  if (!text) {
    alert("コピーする銘柄がありません");
    return;
  }
  navigator.clipboard.writeText(text).then(
    () => alert(`${rows.length}銘柄をコピーしました`),
    () => prompt("コピーしてください", text)
  );
}

function bind() {
  ["fltEntry", "fltActive", "sortBy"].forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener("change", renderTable);
  });
  const btn = $("tvCopyBtn");
  if (btn) btn.addEventListener("click", copyTvList);
}

async function load() {
  try {
    const res = await fetch("data/screener.json?ts=" + Date.now());
    if (!res.ok) throw new Error("screener.json load failed");
    DATA = await res.json();
  } catch (e) {
    console.error(e);
    DATA = {
      updated_at: "データ未取得",
      stocks: [],
      industries: [],
      entry_count: 0,
      active_count: 0,
    };
  }
  renderMeta();
  renderIndustries();
  renderTable();
}

bind();
load();
