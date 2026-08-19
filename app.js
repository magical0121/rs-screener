// 個人用 RS スクリーナー
// data/screener.json を読み込み、テーマカード＋銘柄表を描画

const TT_RANK = { 強い: 3, 普通: 2, 弱い: 1 };
const HQM_RANK = { Top: 4, Strong: 3, Good: 2, Fair: 1, Poor: 0 };

// FinanceDatabase / Finviz 系の英語業種 → 日本語表示
const INDUSTRY_JA = {
  "Advertising Agencies": "広告代理店",
  "Aerospace & Defense": "航空宇宙・防衛",
  "Agricultural Inputs": "農業資材",
  "Airlines": "航空",
  "Airports & Air Services": "空港・航空サービス",
  "Aluminum": "アルミニウム",
  "Apparel Manufacturing": "アパレル製造",
  "Apparel Retail": "アパレル小売",
  "Asset Management": "資産運用",
  "Auto & Truck Dealerships": "自動車販売",
  "Auto Manufacturers": "自動車メーカー",
  "Auto Parts": "自動車部品",
  "Banks - Diversified": "銀行（総合）",
  "Banks - Regional": "地方銀行",
  "Beverages - Brewers": "飲料（ビール）",
  "Beverages - Non-Alcoholic": "飲料（ノンアル）",
  "Beverages - Wineries & Distilleries": "飲料（酒類）",
  "Biotechnology": "バイオテクノロジー",
  "Broadcasting": "放送",
  "Building Materials": "建材",
  "Building Products & Equipment": "建築製品・設備",
  "Business Equipment & Supplies": "事務機器",
  "Capital Markets": "資本市場",
  "Chemicals": "化学",
  "Coking Coal": "原料炭",
  "Communication Equipment": "通信機器",
  "Computer Hardware": "コンピュータ機器",
  "Confectioners": "製菓",
  "Conglomerates": "コングロマリット",
  "Consulting Services": "コンサルティング",
  "Consumer Electronics": "家電",
  "Copper": "銅",
  "Credit Services": "信用・金融サービス",
  "Diagnostics & Research": "診断・研究",
  "Discount Stores": "ディスカウント店",
  "Drug Manufacturers - General": "医薬品（大手）",
  "Drug Manufacturers - Specialty & Generic": "医薬品（専門・GE）",
  "Education & Training Services": "教育・研修",
  "Electrical Equipment & Parts": "電気機器・部品",
  "Electronic Components": "電子部品",
  "Electronic Gaming & Multimedia": "ゲーム・マルチメディア",
  "Electronics & Computer Distribution": "電子・PC流通",
  "Engineering & Construction": "エンジニアリング・建設",
  "Entertainment": "エンタメ",
  "Farm & Heavy Construction Machinery": "農機・建機",
  "Farm Products": "農産物",
  "Financial Conglomerates": "金融コングロマリット",
  "Financial Data & Stock Exchanges": "金融データ・取引所",
  "Food Distribution": "食品流通",
  "Food & Staples Retailing": "食品・生活必需品小売",
  "Footwear & Accessories": "履物・アクセサリー",
  "Furnishings, Fixtures & Appliances": "家具・家電",
  "Gambling": "ギャンブル",
  "Gold": "金",
  "Grocery Stores": "食料品店",
  "Health Information Services": "医療情報サービス",
  "Healthcare Plans": "医療保険",
  "Home Improvement Retail": "ホームセンター",
  "Household & Personal Products": "家庭・パーソナル用品",
  "Household Durables": "家庭用耐久財",
  "Industrial Distribution": "工業流通",
  "Information Technology Services": "ITサービス",
  "Infrastructure Operations": "インフラ運営",
  "Insurance - Diversified": "保険（総合）",
  "Insurance - Life": "生命保険",
  "Insurance - Property & Casualty": "損保",
  "Insurance - Reinsurance": "再保険",
  "Insurance - Specialty": "保険（専門）",
  "Insurance Brokers": "保険ブローカー",
  "Integrated Freight & Logistics": "物流・フォワーダー",
  "Internet Content & Information": "インターネット・情報",
  "Internet Retail": "ネット通販",
  "Leisure": "レジャー",
  "Lodging": "宿泊",
  "Lumber & Wood Production": "木材",
  "Marine Shipping": "海運",
  "Medical Care Facilities": "医療施設",
  "Medical Devices": "医療機器",
  "Medical Distribution": "医療流通",
  "Medical Instruments & Supplies": "医療器具・消耗品",
  "Metal Fabrication": "金属加工",
  "Mortgage Finance": "住宅ローン金融",
  "Oil & Gas Drilling": "石油ガス掘削",
  "Oil & Gas E&P": "石油ガス開発",
  "Oil & Gas Equipment & Services": "石油ガス機材・サービス",
  "Oil & Gas Integrated": "石油ガス総合",
  "Oil & Gas Midstream": "石油ガス中流",
  "Oil & Gas Refining & Marketing": "石油精製・販売",
  "Other Industrial Metals & Mining": "その他工業金属・鉱業",
  "Other Precious Metals & Mining": "その他貴金属・鉱業",
  "Packaged Foods": "加工食品",
  "Packaging & Containers": "包装・容器",
  "Paper & Paper Products": "紙・パルプ",
  "Personal Services": "個人向けサービス",
  "Pharmaceutical Retailers": "薬局・薬小売",
  "Pollution & Treatment Controls": "環境・処理",
  "Publishing": "出版",
  "Railroads": "鉄道",
  "Real Estate - Development": "不動産開発",
  "Real Estate - Diversified": "不動産（総合）",
  "Real Estate Services": "不動産サービス",
  "Recreational Vehicles": "RV",
  "REIT - Diversified": "REIT（総合）",
  "REIT - Healthcare Facilities": "REIT（医療）",
  "REIT - Hotel & Motel": "REIT（ホテル）",
  "REIT - Industrial": "REIT（物流・工業）",
  "REIT - Mortgage": "REIT（モーゲージ）",
  "REIT - Office": "REIT（オフィス）",
  "REIT - Residential": "REIT（住宅）",
  "REIT - Retail": "REIT（商業）",
  "REIT - Specialty": "REIT（専門）",
  "Rental & Leasing Services": "レンタル・リース",
  "Residential Construction": "住宅建設",
  "Resorts & Casinos": "リゾート・カジノ",
  "Restaurants": "外食",
  "Scientific & Technical Instruments": "科学・精密機器",
  "Security & Protection Services": "警備・セキュリティ",
  "Semiconductor Equipment & Materials": "半導体製造装置・材料",
  "Semiconductors": "半導体",
  "Shell Companies": "SPAC・シェル",
  "Silver": "銀",
  "Software - Application": "ソフトウェア（アプリ）",
  "Software - Infrastructure": "ソフトウェア（基盤）",
  "Solar": "太陽光",
  "Specialty Business Services": "専門ビジネスサービス",
  "Specialty Chemicals": "特殊化学品",
  "Specialty Industrial Machinery": "特殊産業機械",
  "Specialty Retail": "専門小売",
  "Staffing & Employment Services": "人材・派遣",
  "Steel": "鉄鋼",
  "Telecom Services": "通信サービス",
  "Textile Manufacturing": "繊維",
  "Thermal Coal": "一般炭",
  "Tobacco": "たばこ",
  "Tools & Accessories": "工具・部品",
  "Travel Services": "旅行サービス",
  "Trucking": "トラック輸送",
  "Uranium": "ウラン",
  "Utilities - Diversified": "電力・ガス（総合）",
  "Utilities - Independent Power Producers": "独立系発電",
  "Utilities - Regulated Electric": "規制電力",
  "Utilities - Regulated Gas": "規制ガス",
  "Utilities - Regulated Water": "規制水道",
  "Utilities - Renewable": "再エネユーティリティ",
  "Waste Management": "廃棄物処理",
  // セクター級フォールバック
  "Information Technology": "情報技術",
  "Health Care": "ヘルスケア",
  "Healthcare": "ヘルスケア",
  "Financials": "金融",
  "Financial": "金融",
  "Consumer Discretionary": "一般消費財",
  "Consumer Cyclical": "一般消費財",
  "Consumer Staples": "生活必需品",
  "Consumer Defensive": "生活必需品",
  "Energy": "エネルギー",
  "Industrials": "資本財・産業",
  "Industrial": "資本財・産業",
  "Materials": "素材",
  "Basic Materials": "素材",
  "Utilities": "公益",
  "Real Estate": "不動産",
  "Communication Services": "通信サービス",
  "Technology": "テクノロジー",
  "Diversified Telecommunication Services": "多角通信サービス",
  "Software": "ソフトウェア",
  "Diversified Financial Services": "多角金融サービス",
  "Metals & Mining": "金属・鉱業",
  "Professional Services": "専門サービス",
  "Technology Hardware, Storage & Peripherals": "ITハードウェア・ストレージ",
  "Health Care Technology": "ヘルスケアテック",
  "Hotels, Restaurants & Leisure": "ホテル・外食・レジャー",
  "Capital Goods": "資本財",
  "Pharmaceuticals": "医薬品",
  "Textiles, Apparel & Luxury Goods": "繊維・アパレル・奢侈品",
  "Health Care Equipment & Supplies": "医療機器・用品",
  "Transportation Infrastructure": "交通インフラ",
  "Building Products": "建築製品",
  "Banks": "銀行",
  "Distributors": "卸売・ディストリビューター",
  "Oil, Gas & Consumable Fuels": "石油・ガス・燃料",
  "Construction & Engineering": "建設・エンジニアリング",
  "Machinery": "機械",
  "Electrical Equipment": "電気機器",
  "Automobiles": "自動車",
  "Media": "メディア",
  "Real Estate Management & Development": "不動産管理・開発",
  "Insurance": "保険",
  "Consumer Finance": "消費者金融",
  "IT Services": "ITサービス",
  "Interactive Media & Services": "インタラクティブメディア",
  "Wireless Telecommunication Services": "無線通信",
  "Electronic Equipment, Instruments & Components": "電子機器・計測・部品",
  "Semiconductors & Semiconductor Equipment": "半導体・製造装置",
  "Life Sciences Tools & Services": "ライフサイエンスツール",
  "Health Care Providers & Services": "ヘルスケア提供",
  "Thrifts & Mortgage Finance": "貯蓄・住宅金融",
  "Diversified Consumer Services": "多角消費者サービス",
  "Leisure Products": "レジャー用品",
  "Personal Products": "パーソナルケア",
  "Food Products": "食品",
  "Beverages": "飲料",
  "Household Products": "家庭用品",
  "Construction Materials": "建設資材",
  "Containers & Packaging": "容器・包装",
  "Paper & Forest Products": "紙・林業",
  "Trading Companies & Distributors": "商社・卸売",
  "Commercial Services & Supplies": "商業サービス",
  "Air Freight & Logistics": "航空貨物・物流",
  "Passenger Airlines": "旅客航空",
  "Ground Transportation": "陸上輸送",
  "Marine Transportation": "海上輸送",
  "Transportation": "運輸",
  "Multi-Utilities": "総合公益",
  "Water Utilities": "水道",
  "Independent Power and Renewable Electricity Producers": "独立・再エネ発電",
  "Equity Real Estate Investment Trusts (REITs)": "株式REIT",
  "Real Estate Investment Trusts (REITs)": "REIT",
  "Communications Equipment": "通信機器",
  "Internet & Direct Marketing Retail": "ネット・通販小売",
  "Energy Equipment & Services": "エネルギー機材・サービス",
  "Auto Components": "自動車部品",
  "Marine": "海運",
  "Diversified Financials": "多角金融",
  "Software & Services": "ソフトウェア・サービス",
  "Road & Rail": "道路・鉄道",
  "Electric Utilities": "電力",
  "Gas Utilities": "ガス",
  "Mortgage Real Estate Investment Trusts (REITs)": "モーゲージREIT",
};

function industryJa(raw) {
  if (raw == null || raw === "" || raw === "—") return "—";
  const s = String(raw).trim();
  if (INDUSTRY_JA[s]) return INDUSTRY_JA[s];
  // 部分一致（表記ゆれ用）
  const lower = s.toLowerCase();
  for (const [en, ja] of Object.entries(INDUSTRY_JA)) {
    if (en.toLowerCase() === lower) return ja;
  }
  return s; // 未登録は英語のまま
}

let DATA = null;

async function loadData() {
  const status = document.getElementById("lastUpdated");
  if (status) status.textContent = "読み込み中…";
  try {
    const res = await fetch("./data/screener.json?t=" + Date.now());
    if (!res.ok) throw new Error("HTTP " + res.status);
    const json = await res.json();
    if (!json || !Array.isArray(json.stocks)) throw new Error("stocks missing");
    DATA = json;
    console.log("[screener] loaded", DATA.stocks.length, "stocks", DATA.updated_at);
  } catch (e) {
    console.error("[screener] load failed", e);
    DATA = window.SAMPLE_DATA;
    if (status) status.textContent = "データ取得失敗 → サンプル表示 (" + e.message + ")";
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

function strengthClass(label) {
  if (label === "強い") return "strong";
  if (label === "普通") return "moderate";
  return "weak";
}

/** 業種別強度（フロントでも算出可能：現行JSONでも即反映） */
let INDUSTRY_SCORE_MAP = {}; // industry(en) -> {score, label, count}

function computeIndustryScores(stocks, minCount = 1) {
  const groups = {};
  for (const s of stocks || []) {
    const key = (s.industry || s.sector || "").trim();
    if (!key || key === "—" || key === "-") continue;
    (groups[key] || (groups[key] = [])).push(s);
  }
  const out = [];
  INDUSTRY_SCORE_MAP = {};
  for (const [name, rows] of Object.entries(groups)) {
    const score = Math.round(
      rows.reduce((a, s) => a + 0.6 * (Number(s.rs) || 0) + 0.4 * (Number(s.hqm) || 0), 0) / rows.length
    );
    const label = score >= 80 ? "強い" : score >= 55 ? "普通" : "弱い";
    INDUSTRY_SCORE_MAP[name] = { score, label, count: rows.length };
    if (rows.length < minCount) continue;
    const leaders = [...rows]
      .sort((a, b) => (b.rs || 0) - (a.rs || 0) || (b.hqm || 0) - (a.hqm || 0))
      .filter((s) => (s.rs || 0) >= 60)
      .slice(0, 3)
      .map((s) => s.ticker);
    out.push({ name, score, label, leaders, count: rows.length });
  }
  out.sort((a, b) => b.score - a.score);
  return out;
}

function industryScoreOf(s) {
  const key = ((s && (s.industry || s.sector)) || "").trim();
  if (!key || key === "—") return null;
  return INDUSTRY_SCORE_MAP[key] || null;
}

function renderIndustryStrength(list) {
  const el = document.getElementById("themeCards");
  if (!list || !list.length) {
    el.innerHTML = `<div class="sidebar-note">業種データが不足しています</div>`;
    return;
  }
  el.innerHTML = list
    .map(
      (t) => `
    <div class="theme-card ${strengthClass(t.label)}">
      <div class="theme-top">
        <div class="theme-name">${industryJa(t.name)}</div>
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

/** 本命: Stage2 + RS≥70 + TT強い + HQM≥80
 *  30週線上は Stage2 / TT強い の定義に含まれる（150日SMA上）
 */
function isHonmei(s) {
  if (!s) return false;
  const stage2 = String(s.stage || "").includes("2");
  const rs = Number(s.rs);
  const hqm = Number(s.hqm);
  const tt = String(s.tt || "").trim();
  const rsOk = !Number.isNaN(rs) && rs >= 70;
  const ttOk = tt === "強い";
  const hqmOk = !Number.isNaN(hqm) && hqm >= 80;
  const ind = industryScoreOf(s);
  const indOk = !!(ind && Number(ind.score) >= 55);
  return stage2 && rsOk && ttOk && hqmOk && indOk;
}

function sortedStocks(stocks) {
  const honmeiEl = document.getElementById("honmeiOnly");
  const honmeiOnly = honmeiEl ? honmeiEl.checked : true;
  const sortByEl = document.getElementById("sortBy");
  const sortBy = sortByEl ? sortByEl.value : "rs";
  let list = [...(stocks || [])];
  if (honmeiOnly) {
    list = list.filter(isHonmei);
  }
  list.sort((a, b) => {
    if (sortBy === "rs") return (b.rs || 0) - (a.rs || 0);
    if (sortBy === "hqm") return (b.hqm || 0) - (a.hqm || 0);
    if (sortBy === "tt") return (TT_RANK[b.tt] || 0) - (TT_RANK[a.tt] || 0);
    if (sortBy === "indScore") {
      const sa = (industryScoreOf(a) || {}).score || 0;
      const sb = (industryScoreOf(b) || {}).score || 0;
      return sb - sa;
    }
    if (sortBy === "industry") {
      return industryJa(a.industry).localeCompare(industryJa(b.industry), "ja");
    }
    return 0;
  });
  return list;
}

function renderTable(stocks) {
  const body = document.getElementById("stockBody");
  if (!body) return;
  const list = sortedStocks(stocks);
  const MAX_ROWS = 400;
  if (!list.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty">表示できる銘柄がありません。「本命のみ」のON/OFFやデータ更新を確認してください。</td></tr>`;
    return;
  }
  const shown = list.slice(0, MAX_ROWS);
  const extra = list.length > MAX_ROWS
    ? `<tr><td colspan="7" class="empty">…他 ${list.length - MAX_ROWS} 件（上位${MAX_ROWS}件のみ表示）</td></tr>`
    : "";
  body.innerHTML = shown
    .map((s) => {
      const h = hqmLabel(s.hqm);
      const ind = industryScoreOf(s);
      let indHtml = "—";
      if (ind) {
        const cls = ind.score >= 80 ? "high" : ind.score >= 55 ? "mid" : "low";
        indHtml = `<span class="rs ${cls}">${ind.score}</span>`;
      }
      return `
      <tr>
        <td>
          <span class="ticker">${s.ticker}</span>
          <span class="ticker-name">${s.name || ""}</span>
        </td>
        <td class="rs ${rsClass(s.rs)}">${s.rs}</td>
        <td><span class="badge ${stageBadge(s.stage)}">${s.stage}</span></td>
        <td>${industryJa(s.industry || s.sector)}</td>
        <td class="ind-score">${indHtml}</td>
        <td><span class="badge ${ttBadge(s.tt)}">${s.tt}</span></td>
        <td class="hqm-cell"><span class="badge ${h.cls}">${h.text}</span></td>
      </tr>`;
    })
    .join("") + extra;
}

function render() {
  if (!DATA) return;
  const stocks = DATA.stocks || [];
  // 先に業種スコアを構築（本命判定で使用）
  const industryList = computeIndustryScores(stocks, 3);
  const honmeiCount = stocks.filter(isHonmei).length;
  document.getElementById("lastUpdated").textContent =
    "更新: " + (DATA.updated_at || "—") +
    " ／ 全" + stocks.length + "件 ／ 本命" + honmeiCount + "件";

  renderIndustryStrength(industryList.slice(0, 40));
  renderTable(stocks);

  const emptyHint = document.getElementById("table-empty-hint");
  if (emptyHint) {
    const _h = document.getElementById("honmeiOnly"); const honmeiOnly = _h ? _h.checked : true;
    if (stocks.length === 0) {
      emptyHint.textContent = "銘柄データがありません。data/screener.json と Actions を確認してください。";
      emptyHint.hidden = false;
    } else if (honmeiOnly && honmeiCount === 0) {
      emptyHint.textContent = "本命条件に該当する銘柄は0件です。「本命のみ」を外すと全件を表示できます。";
      emptyHint.hidden = false;
    } else {
      emptyHint.hidden = true;
    }
  }
}

document.getElementById("honmeiOnly").addEventListener("change", render);
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
