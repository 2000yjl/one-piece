const $ = (id) => document.getElementById(id);
const state = { search: null, official: null, catalog: null, market: null, cards: new Map(), currentProductId: null, detail: null, condition: "PSA10", searchRequest: 0, detailRequest: 0 };
const recommendations = [
  { budget: "1万 - 10万日元", note: "适合建立第一组核心收藏", cards: [
    { code: "OP01-120", query: "OP01-120", name: "Shanks / 香克斯", rarity: "OP01 初代角色卡", reason: "初代卡池、核心角色、版本梯度完整，适合先从流动性较好的版本观察。" },
    { code: "OP01-121", query: "OP01-121", name: "Yamato / 大和", rarity: "SEC / Parallel", reason: "早期系列、人气角色、图面辨识度高，预算内可比较 A 品与 PSA10 溢价。" },
    { code: "OP01-016", query: "OP01-016", name: "Nami / 娜美", rarity: "R / Parallel", reason: "草帽团核心角色，收藏共识稳定，适合关注高人气插画版本。" },
  ]},
  { budget: "10万 - 50万日元", note: "适合关注漫画稀有与高共识版本", cards: [
    { code: "OP02-013", query: "OP02-013", name: "Portgas.D.Ace / 艾斯", rarity: "SR / Manga", reason: "高人气角色与漫画稀有版本组合，成交活跃度和收藏讨论度都值得跟踪。" },
    { code: "OP06-118", query: "OP06-118", name: "Roronoa Zoro / 索隆", rarity: "SEC / Manga", reason: "草帽团核心角色，漫画版本辨识度强，适合对比裸卡与 PSA10 成交曲线。" },
    { code: "OP05-119", query: "OP05-119", name: "Monkey.D.Luffy / 路飞", rarity: "SEC / Parallel", reason: "主角卡拥有最广泛的收藏共识，同编号版本较多，适合做横向比较。" },
  ]},
  { budget: "50万日元以上", note: "高价卡只适合充分核验版本后再判断", cards: [
    { code: "OP01-120", query: "OP01-120 シャンクス コミパラ", name: "Shanks Manga / 香克斯漫画", rarity: "OP01 Manga Rare", reason: "初代漫画稀有卡，系列历史地位明确。重点核对是否为目标版本与近期 PSA10 成交。" },
    { code: "OP05-119", query: "OP05-119 ルフィ コミパラ", name: "Luffy Manga / 路飞漫画", rarity: "Manga Rare", reason: "主角与高稀有度叠加，属于高共识收藏标的。价格高，必须逐笔检查成交。" },
    { code: "OP09-119", query: "OP09-119 ルフィ コミパラ", name: "Luffy Manga / 路飞漫画", rarity: "Manga Rare", reason: "主角漫画线的重要版本，适合与其他路飞漫画卡进行价格和人口对照。" },
  ]},
];
let recommendationsLoaded = false;

function yen(value) {
  return !hasPrice(value) ? "暂无数据" : `¥${Number(value).toLocaleString("ja-JP")}`;
}

function hasPrice(value) {
  return Number.isFinite(Number(value)) && Number(value) > 0;
}

function listingYen(value) {
  return hasPrice(value) ? yen(value) : "暂无挂售";
}

function trendText(value) {
  return value === undefined || value === null ? "等待更多成交" : `${value > 0 ? "+" : ""}${value}%`;
}

function trendClass(value) {
  if (value === undefined || value === null) return "neutral";
  return value >= 0 ? "up" : "down";
}

function remember(cards) {
  (cards || []).forEach((card) => state.cards.set(String(card.product_id), card));
}

function switchView(view) {
  document.querySelectorAll(".view").forEach((node) => node.classList.toggle("hidden", node.id !== `${view}View`));
  document.querySelectorAll(".tab").forEach((node) => node.classList.toggle("active", node.dataset.view === view));
  document.querySelector('[data-view="detail"]').classList.toggle("hidden", view !== "detail");
}

function sales(card) {
  return card.naked_sales || {};
}

function psa10(card) {
  return card.psa10_sales || {};
}

function recordCount(data) {
  const count = data?.sales_count || 0;
  return data?.sample_capped ? `至少 ${count}` : `${count}`;
}

function sortCards(cards) {
  const copy = [...cards];
  const mode = $("sortSelect").value;
  if (mode === "rise") return copy.sort((a, b) => (psa10(b).trend?.percent ?? -Infinity) - (psa10(a).trend?.percent ?? -Infinity));
  if (mode === "fall") return copy.sort((a, b) => (psa10(a).trend?.percent ?? Infinity) - (psa10(b).trend?.percent ?? Infinity));
  if (mode === "active") return copy.sort((a, b) => (psa10(b).sales_count || 0) - (psa10(a).sales_count || 0));
  if (mode === "release_desc") return copy.sort((a, b) => Date.parse(b.released_at || 0) - Date.parse(a.released_at || 0));
  if (mode === "price_desc") return copy.sort((a, b) => (hasPrice(psa10(b).listing_min_jpy) ? psa10(b).listing_min_jpy : -Infinity) - (hasPrice(psa10(a).listing_min_jpy) ? psa10(a).listing_min_jpy : -Infinity));
  if (mode === "price_asc") return copy.sort((a, b) => (hasPrice(psa10(a).listing_min_jpy) ? psa10(a).listing_min_jpy : Infinity) - (hasPrice(psa10(b).listing_min_jpy) ? psa10(b).listing_min_jpy : Infinity));
  return copy.sort((a, b) => (a.rank || Infinity) - (b.rank || Infinity));
}

function expandPsa10Listings(cards) {
  const rows = [];
  (cards || []).forEach((card) => {
    (psa10(card).listings || []).forEach((listing) => rows.push({ card, listing }));
  });
  const mode = $("sortSelect").value;
  rows.sort((a, b) => mode === "price_desc" ? b.listing.price_jpy - a.listing.price_jpy : a.listing.price_jpy - b.listing.price_jpy);
  return rows;
}

function cardTile(card, listing = null) {
  const a = sales(card);
  const p10 = psa10(card);
  const delta = p10.trend?.percent;
  const primaryPrice = listing ? listing.price_jpy : a.listing_min_jpy;
  const primaryLabel = listing ? "PSA10 当前挂售" : "A 品当前最低挂售";
  const badge = listing ? "PSA10挂售" : `#${card.rank || "-"}`;
  return `<button class="snk-card" data-product-id="${card.product_id}">
    <span class="snk-image">
      <span class="popular-rank">${badge}</span>
      <img src="${card.image}" alt="${card.title}" loading="lazy" />
    </span>
    <span class="snk-card-body">
      <b>${card.title}</b>
      <span class="snk-code">${card.code || `SNK #${card.product_id}`}</span>
      <strong>${listingYen(primaryPrice)}</strong>
      <small>${primaryLabel}${listing?.size_label ? ` · ${listing.size_label}` : ""}</small>
      <span class="sale-summary">
        <small>A 品成交 ${yen(a.latest_jpy)}</small>
        <small>PSA10 成交 ${yen(p10.latest_jpy)}</small>
        <small>PSA10 挂售 ${p10.listing_count || 0} 个</small>
        ${card.display_released_at ? `<small>发售 ${card.display_released_at}</small>` : ""}
        <small class="${trendClass(delta)}">PSA10 ${trendText(delta)}</small>
      </span>
    </span>
  </button>`;
}

function renderSearch() {
  const data = state.search;
  if (!data) return;
  const isPsaListingSort = ["price_desc", "price_asc"].includes($("sortSelect").value);
  const cards = sortCards(data.cards || []);
  if (isPsaListingSort) {
    const listings = expandPsa10Listings(data.cards || []);
    $("searchTitle").textContent = `${data.normalized || "全部"} · ${listings.length} 个 PSA10 实时挂售`;
    $("searchNote").textContent = `按 SNKRDUNK PSA10 当前挂售价逐条展开 · 同一张卡多个挂售会出现多格 · 搜索词 ${data.terms?.join(" / ") || data.normalized} · ${data.fetched_at}`;
    $("snkCardWall").innerHTML = listings.length ? listings.map((row) => cardTile(row.card, row.listing)).join("") : `<p class="empty">当前没有可确认的 PSA10 挂售。</p>`;
    return;
  }
  $("searchTitle").textContent = `${data.normalized || "全部"} · ${cards.length} 个实时在售商品`;
  $("searchNote").textContent = `SNKRDUNK 当前公开在售商品变体 · A 品裸卡参考价 · PSA10 成交涨跌 · 搜索词 ${data.terms?.join(" / ") || data.normalized} · ${data.fetched_at}`;
  $("snkCardWall").innerHTML = cards.length ? cards.map((card) => cardTile(card)).join("") : `<p class="empty">SNKRDUNK 当前没有公开在售商品，请查看下方 Bandai 官方卡图目录。</p>`;
}

function renderOfficial() {
  const data = state.official;
  if (!data) return;
  $("officialMeta").textContent = `${data.cards.length} 张官方匹配卡图`;
  $("officialCardWall").innerHTML = data.cards.length ? data.cards.map((card) => `<button class="official-card" data-query="${card.code}">
    <img src="${card.image}" alt="${card.name}" loading="lazy" />
    <span><b>${card.name}</b><small>${card.variant_id} · ${card.rarity || card.card_type}</small></span>
  </button>`).join("") : `<p class="empty">官方目录中没有找到匹配卡牌。</p>`;
}

function officialTile(card) {
  return `<button class="official-card" data-query="${card.code}">
    <img src="${card.image}" alt="${card.name}" loading="lazy" />
    <span><b>${card.name}</b><small>${card.variant_id} · ${card.rarity || card.card_type}</small></span>
  </button>`;
}

function renderCatalogPage(data) {
  state.catalog = data;
  $("allCatalogMeta").textContent = `${data.total.toLocaleString()} 张卡图 · 第 ${data.page} / ${data.pages} 页 · Bandai 官方目录`;
  $("allCatalogWall").innerHTML = data.cards.length ? data.cards.map(officialTile).join("") : `<p class="empty">没有找到匹配卡牌。</p>`;
  $("catalogPage").textContent = `${data.page} / ${data.pages}`;
  $("catalogPrev").disabled = data.page <= 1;
  $("catalogNext").disabled = data.page >= data.pages;
}

async function loadCatalogPage(page = 1) {
  switchView("catalog");
  $("allCatalogMeta").textContent = "正在建立或读取官方完整目录...";
  const query = $("catalogFilter").value.trim();
  try {
    const response = await fetch(`/api/catalog/all?q=${encodeURIComponent(query)}&page=${page}&per_page=72`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "目录读取失败");
    renderCatalogPage(data);
  } catch (error) {
    $("allCatalogMeta").textContent = `目录读取失败：${error.message}`;
  }
}

function rankRow(card, value) {
  return `<button class="rank-row" data-product-id="${card.product_id}">
    <span class="rank">#${card.rank || "-"}</span>
    <img src="${card.image}" alt="${card.title}" loading="lazy" />
    <span class="rank-name"><b>${card.title}</b><small>${card.code || `SNK #${card.product_id}`}</small></span>
    <strong>${value}</strong>
  </button>`;
}

function renderRanking(id, cards, formatter) {
  $(id).innerHTML = cards?.length ? cards.map((card) => rankRow(card, formatter(card))).join("") : `<p class="empty">暂无足够的 A 品成交数据。</p>`;
}

function renderMarket(data) {
  state.market = data;
  remember(data.cards);
  const rankings = data.rankings || {};
  $("refreshMeta").innerHTML = `A 品实时行情<br>${data.fetched_at}`;
  $("summaryBand").innerHTML = [
    ["已收录卡牌", data.card_count, "当前榜单样本"],
    ["裸卡口径", "A 品", "排除 B/C/D"],
    ["涨跌计算", "PSA10", "最近成交价变化"],
    ["数据来源", "SNKRDUNK", "站内整合展示"],
  ].map(([label, value, note]) => `<div class="summary-cell"><span>${label}</span><b>${value}</b><small>${note}</small></div>`).join("");
  renderRanking("highPrice", rankings.popular || [], (card) => yen(card.price_jpy));
  renderRanking("gainers", rankings.gainers || [], (card) => trendText(psa10(card).trend?.percent));
  renderRanking("losers", rankings.losers || [], (card) => trendText(psa10(card).trend?.percent));
  renderRanking("psaOverview", rankings.active || [], (card) => `${recordCount(psa10(card))} 条近期记录`);
  $("catalogMeta").textContent = `${data.card_count} 张 · A 品裸卡 + PSA10`;
  $("watchlist").innerHTML = (data.cards || []).slice(0, 18).map((card) => `<button class="watch-card" data-product-id="${card.product_id}">
    <img src="${card.image}" alt="${card.title}" loading="lazy" />
    <span><b>${card.title}</b><small>${card.code || `SNK #${card.product_id}`}</small></span>
    <strong>${yen(card.price_jpy)}</strong>
    <em class="${trendClass(psa10(card).trend?.percent)}">PSA10 ${trendText(psa10(card).trend?.percent)}</em>
  </button>`).join("");
}

function metric(label, value, note) {
  return `<div class="metric"><span>${label}</span><b>${value}</b><small>${note}</small></div>`;
}

function drawChart(items, condition = state.condition, chartPoints = []) {
  const canvas = $("historyChart");
  const ctx = canvas.getContext("2d");
  const rows = chartPoints.length
    ? chartPoints.map(([date, price]) => ({ date, price }))
    : [...items].filter((item) => item.condition === condition && item.price).reverse();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (rows.length < 2) {
    ctx.fillStyle = "#667085";
    ctx.font = "16px Arial";
    ctx.fillText(`暂无足够的 ${condition === "A" ? "A 品裸卡" : "PSA10"} 成交记录`, 24, 48);
    return;
  }
  const values = rows.map((item) => item.price);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const left = 56;
  const right = canvas.width - 24;
  const top = 24;
  const bottom = canvas.height - 36;
  ctx.strokeStyle = "#e2e8f0";
  ctx.lineWidth = 1;
  [0, 0.5, 1].forEach((ratio) => {
    const y = top + (bottom - top) * ratio;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(right, y);
    ctx.stroke();
  });
  ctx.strokeStyle = "#c92f36";
  ctx.lineWidth = 3;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = left + ((right - left) * index) / (values.length - 1);
    const y = bottom - ((value - min) / range) * (bottom - top);
    if (!index) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = "#667085";
  ctx.font = "13px Arial";
  ctx.fillText(yen(max), 6, top + 5);
  ctx.fillText(yen(min), 6, bottom + 5);
  ctx.fillText(`${rows.length} 个官方图表数据点`, left, canvas.height - 10);
}

function renderSalesCondition(condition) {
  state.condition = condition;
  const data = state.detail;
  if (!data) return;
  const label = condition === "A" ? "A 品裸卡" : "PSA10";
  const rows = (data.items || []).filter((item) => item.condition === condition);
  const grouped = [];
  const seen = new Set();
  rows.forEach((item) => {
    const key = `${item.condition}|${item.date}|${item.price}`;
    if (!seen.has(key)) {
      grouped.push(item);
      seen.add(key);
    }
  });
  document.querySelectorAll(".sales-toggle button").forEach((button) => button.classList.toggle("active", button.dataset.condition === condition));
  $("historyTitle").textContent = `${label}成交趋势`;
  $("salesListTitle").textContent = `${label}最近成交`;
  const conditionStats = condition === "A" ? data.naked : data.psa10;
  $("historyStatus").textContent = `${conditionStats?.sample_capped ? "至少 " : ""}${rows.length} 条近期 ${label} 公开成交记录`;
  $("priceRows").innerHTML = grouped.length ? `<p class="record-note">SNKRDUNK 未公开订单购买数量。相同显示时间与价格会合并为公开记录数，但不能据此断定为同一买家的一次批量订单。</p>` + grouped.map((item) => `<div class="row">
    <span><b>${label}</b><small>${item.date || "日期未公开"}${item.same_time_price_records > 1 ? ` · 同价同时段 ${item.same_time_price_records} 条公开记录` : ""}</small></span>
    <strong>${yen(item.price)}</strong>
  </div>`).join("") : `<p class="empty">暂无${label}公开成交记录。其他品相成交不纳入本站。</p>`;
  drawChart(data.items || [], condition, data.charts?.[condition] || []);
}

function renderRelated(productId) {
  const related = (state.search?.cards || []).filter((card) => String(card.product_id) !== String(productId)).slice(0, 12);
  $("results").innerHTML = related.map((card) => `<button class="result-card" data-product-id="${card.product_id}">
    <img src="${card.image}" alt="${card.title}" loading="lazy" />
    <b>${card.code || card.title}</b>
  </button>`).join("") || `<p class="empty">暂无相关卡牌。</p>`;
}

function platformStatus(status) {
  const labels = {
    live: "实时数据",
    "verify-required": "需人工核验",
  };
  return labels[status] || status;
}

async function loadMarketCompare(card) {
  const productId = String(card.product_id);
  $("compareStatus").textContent = "读取平台入口中";
  $("marketCompare").innerHTML = `<p class="empty">正在整理国内外交易平台...</p>`;
  try {
    const response = await fetch(`/api/markets/compare?q=${encodeURIComponent(card.code || card.title)}`, { cache: "no-store" });
    const data = await response.json();
    if (String(state.currentProductId) !== productId) return;
    if (!response.ok) throw new Error(data.error || "比价读取失败");
    $("compareStatus").textContent = `${data.platforms.length} 个平台`;
    $("marketCompare").innerHTML = data.platforms.map((platform) => {
      const isSnk = platform.name === "SNKRDUNK";
      const price = isSnk
        ? `<div class="compare-price"><b>A 品最低挂售 ${listingYen(sales(card).listing_min_jpy)}</b><strong>PSA10 最低挂售 ${listingYen(psa10(card).listing_min_jpy)}</strong></div>`
        : `<div class="compare-price muted">未展示未经严格确认的报价</div>`;
      const sold = platform.sold_url ? `<a href="${platform.sold_url}" target="_blank" rel="noreferrer">已成交</a>` : "";
      return `<article class="compare-card">
        <div class="compare-title"><div><h3>${platform.name}</h3><small>${platform.region}</small></div><span class="status ${platform.status === "live" ? "ok" : ""}">${platformStatus(platform.status)}</span></div>
        <div class="compare-types">${platform.types.map((type) => `<span>${type}</span>`).join("")}</div>
        ${price}
        <p>${platform.note}</p>
        <div class="compare-actions"><a href="${platform.url}" target="_blank" rel="noreferrer">打开平台</a>${sold}</div>
      </article>`;
    }).join("");
  } catch (error) {
    if (String(state.currentProductId) !== productId) return;
    $("compareStatus").textContent = "读取失败";
    $("marketCompare").innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

function renderRecommendations() {
  $("recommendGroups").innerHTML = recommendations.map((group) => `<section class="panel recommend-group">
    <div class="panel-title"><div><p class="eyebrow">BUDGET RANGE</p><h2>${group.budget}</h2></div><span class="status">${group.note}</span></div>
    <div class="recommend-grid">${group.cards.map((card) => `<article class="recommend-card">
      <img src="/api/image?url=${encodeURIComponent(`https://asia-en.onepiece-cardgame.com/images/cardlist/card/${card.code}.png`)}" alt="${card.name}" loading="lazy" />
      <div>
        <p class="eyebrow">${card.rarity}</p>
        <h3>${card.name}</h3>
        <strong>${card.code}</strong>
        <p>${card.reason}</p>
        <div class="recommend-live">Mercari 报价未展示：公开搜索无法严格确认具体版本</div>
        <button class="recommend-search" data-query="${card.query}">查看站内实时行情</button>
      </div>
    </article>`).join("")}</div>
  </section>`).join("");
}

async function loadRecommendationMarkets() {
  recommendationsLoaded = true;
}

async function loadDetail(productId, options = {}) {
  const card = state.cards.get(String(productId));
  if (!card) return;
  const requestId = ++state.detailRequest;
  state.currentProductId = String(productId);
  state.detail = null;
  syncUrl({ q: $("query").value.trim(), product: productId }, options.replace);
  switchView("detail");
  $("cardImage").src = card.image;
  $("cardCode").textContent = card.code || `SNKRDUNK 商品 #${card.product_id}`;
  $("cardName").textContent = card.title;
  $("cardLine").textContent = "本站详情页 · A 品裸卡参考价 · PSA10 涨跌";
  $("metrics").innerHTML = metric("A 品最低挂售", listingYen(sales(card).listing_min_jpy), "SNKRDUNK 当前最低挂售") +
    metric("A 品最近成交", yen(sales(card).latest_jpy), sales(card).latest_at || "等待成交") +
    metric("PSA10 最低挂售", listingYen(psa10(card).listing_min_jpy), "SNKRDUNK 当前最低挂售") +
    metric("PSA10 最近成交", yen(psa10(card).latest_jpy), psa10(card).latest_at || "等待成交") +
    metric("PSA10 成交涨跌", trendText(psa10(card).trend?.percent), "对比前一笔不同成交价");
  $("sourceStrip").innerHTML = `<span class="source-chip ok">A 品裸卡</span><span class="source-chip">PSA10</span><span class="source-chip">站内整合行情</span>`;
  $("historyStatus").textContent = "读取成交中";
  $("priceRows").innerHTML = `<p class="empty">正在读取最近成交...</p>`;
  $("altSources").innerHTML = `<div class="feed-item">读取原始来源中...</div>`;
  loadMarketCompare(card);
  renderRelated(productId);
  try {
    const response = await fetch(`/api/snkrdunk/sales?product_id=${encodeURIComponent(productId)}`, { cache: "no-store" });
    const data = await response.json();
    if (requestId !== state.detailRequest) return;
    if (!response.ok) throw new Error(data.error || "读取失败");
    state.detail = data;
    const preferred = data.psa10?.sales_count ? "PSA10" : data.naked?.sales_count ? "A" : state.condition;
    renderSalesCondition(preferred);
    $("altSources").innerHTML = `<div class="feed-item">页面中的行情已整理为站内视图。<a href="${data.source}" target="_blank" rel="noreferrer">查看 SNKRDUNK 原始成交页</a></div>`;
  } catch (error) {
    if (requestId !== state.detailRequest) return;
    $("historyStatus").textContent = "读取失败";
    $("priceRows").innerHTML = `<p class="empty">${error.message}</p>`;
    drawChart([], state.condition, []);
  }
}

function syncUrl({ q = "", product = "" } = {}, replace = false) {
  const url = new URL(window.location.href);
  q ? url.searchParams.set("q", q) : url.searchParams.delete("q");
  product ? url.searchParams.set("product", product) : url.searchParams.delete("product");
  history[replace ? "replaceState" : "pushState"]({}, "", `${url.pathname}${url.search}`);
}

async function loadSearch(query, options = {}) {
  query = query.trim();
  if (!query) return;
  const requestId = ++state.searchRequest;
  switchView("search");
  state.currentProductId = null;
  state.detail = null;
  syncUrl({ q: query, product: options.productId || "" }, options.replace);
  $("query").value = query;
  $("searchTitle").textContent = "正在读取相关卡牌";
  $("searchNote").textContent = "抓取 SNKRDUNK A 品裸卡与 PSA10 成交中...";
  try {
    const [marketResponse, officialResponse] = await Promise.all([
      fetch(`/api/snkrdunk/search?q=${encodeURIComponent(query)}`, { cache: "no-store" }),
      fetch(`/api/catalog/search?q=${encodeURIComponent(query)}`, { cache: "no-store" }),
    ]);
    const [data, official] = await Promise.all([marketResponse.json(), officialResponse.json()]);
    if (requestId !== state.searchRequest) return;
    if (!marketResponse.ok) throw new Error(data.error || "行情查询失败");
    if (!officialResponse.ok) throw new Error(official.error || "官方目录查询失败");
    state.search = data;
    state.official = official;
    remember(data.cards);
    $("refreshMeta").innerHTML = `A 品 + PSA10 实时行情<br>${data.fetched_at}`;
    renderSearch();
    renderOfficial();
    if (options.productId && state.cards.has(String(options.productId))) loadDetail(String(options.productId), { replace: true });
  } catch (error) {
    if (requestId !== state.searchRequest) return;
    $("searchTitle").textContent = `查询失败：${error.message}`;
    $("searchNote").textContent = "请稍后重试。";
  }
}

async function loadMarket() {
  switchView("overview");
  $("refreshMeta").textContent = "正在读取行情总览...";
  try {
    const response = await fetch("/api/snkrdunk/market", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "总览读取失败");
    renderMarket(data);
  } catch (error) {
    $("refreshMeta").textContent = `读取失败：${error.message}`;
  }
}

document.addEventListener("click", (event) => {
  const recommended = event.target.closest("[data-query]");
  if (recommended) {
    loadSearch(recommended.dataset.query);
    return;
  }
  const card = event.target.closest("[data-product-id]");
  if (card) loadDetail(card.dataset.productId);
});
$("searchForm").addEventListener("submit", (event) => { event.preventDefault(); loadSearch($("query").value.trim()); });
$("quickRow").addEventListener("click", (event) => { if (event.target.dataset.q) loadSearch(event.target.dataset.q); });
$("sortSelect").addEventListener("change", renderSearch);
$("overviewRefresh").addEventListener("click", loadMarket);
$("backButton").addEventListener("click", () => {
  state.detailRequest += 1;
  state.currentProductId = null;
  syncUrl({ q: $("query").value.trim() });
  switchView("search");
});
document.querySelector(".sales-toggle").addEventListener("click", (event) => {
  if (event.target.dataset.condition) renderSalesCondition(event.target.dataset.condition);
});
$("catalogFilterForm").addEventListener("submit", (event) => { event.preventDefault(); loadCatalogPage(1); });
$("catalogPrev").addEventListener("click", () => loadCatalogPage((state.catalog?.page || 1) - 1));
$("catalogNext").addEventListener("click", () => loadCatalogPage((state.catalog?.page || 1) + 1));
document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  if (tab.dataset.view === "overview") return loadMarket();
  if (tab.dataset.view === "catalog") return loadCatalogPage(state.catalog?.page || 1);
  if (tab.dataset.view === "recommend") loadRecommendationMarkets();
  switchView(tab.dataset.view);
}));
renderRecommendations();
window.addEventListener("popstate", () => {
  const params = new URLSearchParams(window.location.search);
  loadSearch(params.get("q") || "路飞", { replace: true, productId: params.get("product") });
});
const initialParams = new URLSearchParams(window.location.search);
loadSearch(initialParams.get("q") || "路飞", { replace: true, productId: initialParams.get("product") });
