import { buildPlaybackIndexes } from "./playback-utils.js";
import { applyListingYearToStartInput } from "./form-utils.js";
import {
  DEFAULT_VIEWPORT_MONTHS,
  autoViewportStartFrame,
  manualViewportEndFrame,
  maxViewportStartFrame,
  seriesColor,
  viewportValueDomain,
} from "./chart-utils.js";

const stockList = document.querySelector("#stockList");
const addStockButton = document.querySelector("#addStockButton");
const form = document.querySelector("#backtestForm");
const workspace = document.querySelector("#workspace");
const collapseButton = document.querySelector("#collapseButton");
const expandButton = document.querySelector("#expandButton");
const chartWrap = document.querySelector(".chart-wrap");
const chart = document.querySelector("#chart");
const chartEmpty = document.querySelector("#chartEmpty");
const finalResultOverlay = document.querySelector("#finalResultOverlay");
const resultText = document.querySelector("#resultText");
const yearSlider = document.querySelector("#yearSlider");
const pauseButton = document.querySelector("#pauseButton");
const replayButton = document.querySelector("#replayButton");
const resultButton = document.querySelector("#resultButton");
const yearTrigger = document.querySelector("#yearTrigger");
const yearPicker = document.querySelector("#yearPicker");
const yearRangeText = document.querySelector("#yearRangeText");
const startYear = document.querySelector("#startYear");
const endYear = document.querySelector("#endYear");
const marketIndexPanel = document.querySelector("#marketIndexPanel");
const selectedIndexes = document.querySelector("#selectedIndexes");

let playback = null;
let activeResult = null;
let activeFrame = 0;
let paused = false;
let playbackIndexes = [];
let chartState = null;
let playbackComplete = false;
let fullChartMode = false;
let selectedBenchmarks = [];
const watchedSymbolInputs = new WeakSet();
const stockInfoTimers = new WeakMap();
const preloadControllers = new WeakMap();

const PROFIT_COLOR = "#ec0203";
const LOSS_COLOR = "#5bfff8";
const DATA_COLOR = "#5f2225";

function formatMoney(value) {
  return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`;
}

function formatIndexPercent(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function formatSignedIndex(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}`;
}

function seriesTitle(series) {
  return series.name && series.name !== series.symbol ? `${series.name} ${series.symbol}` : series.symbol;
}

function seriesName(series) {
  return series.name || series.symbol;
}

function componentTitle(component) {
  const name = component.name || component.symbol;
  return `${name} ${(Number(component.allocation || 0) * 100).toFixed(0)}%`;
}

function renderMarketIndexes(indexes) {
  if (!marketIndexPanel || !indexes?.length) return;
  marketIndexPanel.innerHTML = indexes.map((item) => {
    const trendClass = Number(item.change) >= 0 ? "up" : "down";
    return `
      <div class="market-index-card ${trendClass}" draggable="true" data-index-code="${item.code}" data-index-name="${item.name}">
        <span class="market-index-name">${item.name}</span>
        <strong>${Number(item.value || 0).toFixed(2)}</strong>
        <span>${formatSignedIndex(item.change)}&nbsp;&nbsp;${formatIndexPercent(item.change_pct)}</span>
      </div>
    `;
  }).join("");
}

async function loadMarketIndexes() {
  try {
    const response = await fetch("/api/market-indexes");
    const payload = await response.json();
    if (response.ok && payload.indexes?.length) {
      renderMarketIndexes(payload.indexes);
    }
  } catch {
    // The static cards in the HTML are the no-network fallback.
  }
}

function renderSelectedBenchmarks() {
  if (!selectedIndexes) return;
  if (!selectedBenchmarks.length) {
    selectedIndexes.textContent = "把左侧宽基指数拖到这里，可和股票一起对比收益曲线";
    return;
  }
  selectedIndexes.innerHTML = selectedBenchmarks.map((item) => `
    <span class="selected-index-chip">
      ${item.name}
      <button type="button" data-remove-benchmark="${item.code}" title="移除 ${item.name}">×</button>
    </span>
  `).join("");
}

function addBenchmark(code, name) {
  if (!code || selectedBenchmarks.some((item) => item.code === code)) return;
  selectedBenchmarks = [...selectedBenchmarks, { code, name: name || code }];
  renderSelectedBenchmarks();
}

function benchmarkFromCard(card) {
  return {
    code: card?.dataset.indexCode || "",
    name: card?.dataset.indexName || card?.querySelector(".market-index-name")?.textContent?.trim() || "",
  };
}

function addStockRow(symbol = "", percent = "") {
  const row = document.createElement("div");
  row.className = "stock-row";
  const displaySymbol = symbol ? symbol : "";
  row.innerHTML = `
    <input class="stock-symbol" placeholder="股票代码 / 股票名称" value="${displaySymbol}" data-symbol="${symbol}">
    <input class="stock-percent" placeholder="100%" value="${percent}">
    <button class="row-remove" type="button" title="删除">-</button>
    <div class="stock-cache-status"></div>
  `;
  row.querySelector(".row-remove").addEventListener("click", () => {
    if (stockList.children.length > 1) {
      row.remove();
      updateStockRowControls();
    }
  });
  stockList.appendChild(row);
  updateStockRowControls();
  attachStockWatchers();
}

function updateStockRowControls() {
  stockList.classList.toggle("single-row", stockList.children.length === 1);
}

function attachStockWatchers() {
  document.querySelectorAll(".stock-symbol").forEach((input) => {
    if (watchedSymbolInputs.has(input)) return;
    watchedSymbolInputs.add(input);
    input.addEventListener("input", () => {
      input.dataset.symbol = "";
      scheduleStockInfoFetch(input);
    });
    input.addEventListener("blur", () => resolveStockInput(input));
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      resolveStockInput(input);
    });
  });
}

function scheduleStockInfoFetch(input) {
  window.clearTimeout(stockInfoTimers.get(input));
  stockInfoTimers.set(input, window.setTimeout(() => {
    if (stockSymbolForInput(input)) {
      fetchStockInfo(input);
    }
  }, 450));
}

function scheduleAllStockPreloads() {
  document.querySelectorAll(".stock-symbol").forEach((input) => {
    if (stockSymbolForInput(input)) {
      scheduleStockInfoFetch(input);
    }
  });
}

function stockSymbolForInput(input) {
  return input.dataset.symbol || parseSymbolFromDisplay(input.value);
}

function parseSymbolFromDisplay(value) {
  const match = String(value || "").match(/\d{6}/);
  return match ? match[0] : "";
}

function formatStockDisplay(symbol, name) {
  return name && name !== symbol ? `${symbol}    ${name}` : symbol;
}

function setStockStatus(row, text, state = "") {
  const status = row?.querySelector(".stock-cache-status");
  if (!status) return;
  status.textContent = text;
  status.className = `stock-cache-status ${state}`.trim();
}

async function fetchStockInfo(input) {
  const row = input.closest(".stock-row");
  const symbol = stockSymbolForInput(input);
  if (!/^\d{6}$/.test(symbol || "")) {
    setStockStatus(row, "", "");
    return;
  }

  try {
    setStockStatus(row, "正在读取股票信息...", "loading");
    const response = await fetch(`/api/stock-info?symbol=${encodeURIComponent(symbol)}`);
    const payload = await response.json();
    if (!response.ok || payload.error) throw new Error(payload.error || "股票信息读取失败");
    if (input === document.querySelector(".stock-symbol")) {
      applyListingYearToStartInput(startYear, yearRangeText, endYear, payload);
    }
    await preloadStock(row, symbol, Number(startYear.value), Number(endYear.value));
  } catch (error) {
    if (error.name === "AbortError") return;
    try {
      await preloadStock(row, symbol, Number(startYear.value), Number(endYear.value));
    } catch (preloadError) {
      if (preloadError.name !== "AbortError") {
        setStockStatus(row, "行情准备失败，播放时会再次尝试", "error");
      }
    }
  }
}

async function resolveStockInput(input) {
  const row = input.closest(".stock-row");
  const query = input.value.trim();
  if (!query) {
    input.dataset.symbol = "";
    setStockStatus(row, "", "");
    return;
  }

  try {
    setStockStatus(row, "正在识别股票...", "loading");
    const response = await fetch(`/api/resolve-stock?q=${encodeURIComponent(query)}`);
    const payload = await response.json();
    if (!response.ok || payload.error) throw new Error(payload.error || "股票识别失败");
    input.dataset.symbol = payload.symbol;
    input.dataset.name = payload.name;
    input.value = formatStockDisplay(payload.symbol, payload.name);
    await fetchStockInfo(input);
  } catch {
    input.dataset.symbol = "";
    setStockStatus(row, "未识别到股票，请输入代码或完整股票名", "error");
  }
}

async function preloadStock(row, symbol, preloadStartYear, preloadEndYear) {
  if (!Number.isFinite(preloadStartYear) || !Number.isFinite(preloadEndYear)) return;
  const existing = preloadControllers.get(row);
  if (existing) existing.abort();

  const controller = new AbortController();
  preloadControllers.set(row, controller);
  setStockStatus(row, `正在准备 ${symbol} ${preloadStartYear}-${preloadEndYear} 行情...`, "loading");
  const params = new URLSearchParams({
    symbol,
    startYear: String(preloadStartYear),
    endYear: String(preloadEndYear),
  });
  const response = await fetch(`/api/preload-stock?${params.toString()}`, { signal: controller.signal });
  const payload = await response.json();
  if (!response.ok || payload.error) throw new Error(payload.error || "行情准备失败");
  setStockStatus(row, `行情已就绪：${payload.first_date || preloadStartYear} - ${payload.last_date || preloadEndYear}`, "ready");
}

function collectPayload() {
  const stocks = [...document.querySelectorAll(".stock-row")].map((row) => ({
    symbol: stockSymbolForInput(row.querySelector(".stock-symbol")),
    percent: row.querySelector(".stock-percent").value.trim(),
  })).filter((item) => item.symbol);

  return {
    stocks,
    benchmarks: selectedBenchmarks.map((item) => item.code),
    buyMethod: document.querySelector("#buyMethod").value,
    amount: Number(document.querySelector("#amount").value),
    startYear: Number(startYear.value),
    endYear: Number(endYear.value),
  };
}

async function runBacktest(play = true) {
  stopPlayback();
  chartEmpty.hidden = true;
  finalResultOverlay.hidden = true;
  resultText.textContent = "";

  const response = await fetch("/api/backtest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectPayload()),
  });
  const payload = await response.json();
  if (!response.ok || payload.error) {
    activeResult = null;
    playbackIndexes = [];
    activeFrame = 0;
    chart.innerHTML = "";
    finalResultOverlay.hidden = true;
    chartEmpty.hidden = false;
    chartEmpty.textContent = payload.error || "回测失败";
    buildProgressSlider();
    return;
  }

  activeResult = payload;
  playbackIndexes = buildPlaybackIndexes(payload);
  activeFrame = 0;
  playbackComplete = false;
  fullChartMode = false;
  workspace.classList.add("collapsed");
  buildProgressSlider();
  if (play) {
    startPlayback();
  } else {
    activeFrame = playbackIndexes.length - 1;
    playbackComplete = true;
    buildViewportSlider();
    showManualViewport(maxViewportStartFrame(playbackIndexes.length, DEFAULT_VIEWPORT_MONTHS));
    showFinalResult(payload, true);
  }
}

function buildProgressSlider() {
  yearSlider.max = String(Math.max(playbackIndexes.length - 1, 0));
  yearSlider.value = "0";
}

function buildViewportSlider() {
  yearSlider.max = String(maxViewportStartFrame(playbackIndexes.length, DEFAULT_VIEWPORT_MONTHS));
  yearSlider.value = yearSlider.max;
}

function showFullChart() {
  if (!activeResult || !playbackIndexes.length) return;
  stopPlayback(false);
  playbackComplete = true;
  fullChartMode = true;
  finalResultOverlay.hidden = true;
  buildViewportSlider();
  yearSlider.value = "0";
  activeFrame = playbackIndexes.length - 1;
  renderChart(activeResult, playbackIndexes[activeFrame], playbackIndexes[0], "整体收益曲线");
}

function startPlayback() {
  paused = false;
  fullChartMode = false;
  pauseButton.textContent = "暂停";
  showFrame(0);
  playback = window.setInterval(() => {
    if (paused || !activeResult) return;
    activeFrame += 1;
    if (activeFrame >= playbackIndexes.length - 1) {
      activeFrame = playbackIndexes.length - 1;
      stopPlayback(false);
      playbackComplete = true;
      buildViewportSlider();
      showManualViewport(Number(yearSlider.value));
      showFinalResult(activeResult, true);
      return;
    }
    showFrame(activeFrame);
  }, 760);
}

function stopPlayback(clear = true) {
  if (playback) window.clearInterval(playback);
  playback = null;
  if (clear) activeFrame = 0;
}

function showFrame(frameIndex) {
  if (!activeResult || !playbackIndexes.length) return;
  activeFrame = Number(frameIndex);
  yearSlider.value = String(activeFrame);
  const snapshotIndex = playbackIndexes[activeFrame];
  const viewportStartFrame = autoViewportStartFrame(activeFrame, DEFAULT_VIEWPORT_MONTHS);
  renderChart(activeResult, snapshotIndex, playbackIndexes[viewportStartFrame]);
}

function showManualViewport(startFrame) {
  if (!activeResult || !playbackIndexes.length) return;
  fullChartMode = false;
  finalResultOverlay.hidden = true;
  const start = Number(startFrame);
  const endFrame = manualViewportEndFrame(start, playbackIndexes.length, DEFAULT_VIEWPORT_MONTHS);
  activeFrame = endFrame;
  yearSlider.value = String(start);
  renderChart(activeResult, playbackIndexes[endFrame], playbackIndexes[start]);
}

function frameForSeries(series, snapshotIndex) {
  return series.snapshots[Math.min(snapshotIndex, series.snapshots.length - 1)];
}

function renderChart(result, snapshotIndex, viewportStartSnapshot = 0, modeLabel = "正在回放") {
  chartEmpty.hidden = true;
  const allPoints = result.series.flatMap((series) => series.snapshots.slice(viewportStartSnapshot, snapshotIndex + 1));
  const baselineValue = result.series[0].snapshots[viewportStartSnapshot]?.value || allPoints[0]?.value || 1;
  const domain = viewportValueDomain(allPoints.map((point) => point.value), baselineValue);
  const maxValue = domain.maxValue;
  const minValue = domain.minValue;
  const span = Math.max(maxValue - minValue, 1);
  const comparisonMode = result.series.length > 1;

  const width = 1200;
  const height = 620;
  const pad = { left: 72, right: comparisonMode ? 190 : 34, top: 44, bottom: 58 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;

  const paths = result.series.map((series, index) => {
    const seriesEnd = Math.min(snapshotIndex, series.snapshots.length - 1);
    if (seriesEnd < 0) return "";
    const seriesStart = Math.min(viewportStartSnapshot, seriesEnd);
    const visible = series.snapshots.slice(seriesStart, seriesEnd + 1);
    const denom = Math.max(visible.length - 1, 1);
    const fixedSeriesColor = seriesColor(index);
    const segments = visible.slice(1).map((point, pointIndex) => {
      const previous = visible[pointIndex];
      const x1 = pointToX(pointIndex, denom, pad.left, plotWidth);
      const y1 = pointToY(previous.value, minValue, span, pad.top, plotHeight);
      const x2 = pointToX(pointIndex + 1, denom, pad.left, plotWidth);
      const y2 = pointToY(point.value, minValue, span, pad.top, plotHeight);
      const color = comparisonMode ? fixedSeriesColor : point.profit >= 0 ? PROFIT_COLOR : LOSS_COLOR;
      return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${comparisonMode ? 3.4 : 4}" stroke-linecap="round" />`;
    }).join("");
    const last = visible[visible.length - 1];
    const lastColor = comparisonMode ? fixedSeriesColor : last.profit >= 0 ? PROFIT_COLOR : LOSS_COLOR;
    const lastX = pointToX(visible.length - 1, denom, pad.left, plotWidth);
    const lastY = pointToY(last.value, minValue, span, pad.top, plotHeight);
    const labelX = Number(lastX) + 12;
    const labelY = Math.min(height - pad.bottom - 10, Math.max(pad.top + 18, Number(lastY) + 6));
    return `
      ${segments || `<circle cx="${lastX}" cy="${lastY}" r="4" fill="${lastColor}" />`}
      <circle cx="${lastX}" cy="${lastY}" r="5" fill="${lastColor}" />
      <text x="${labelX}" y="${labelY}" fill="${lastColor}" font-size="17" font-weight="800">${seriesName(series)}</text>
    `;
  }).join("");

  const first = result.series[0].snapshots[viewportStartSnapshot];
  const last = frameForSeries(result.series[0], snapshotIndex);
  const current = frameForSeries(result.series[0], snapshotIndex);
  const currentReturn = current.return_rate || 0;
  const profitColor = current.profit >= 0 ? PROFIT_COLOR : LOSS_COLOR;
  const componentLegend = result.series[0].components?.length
    ? `
      <g class="portfolio-components">
        <rect x="${pad.left + 10}" y="${pad.top + 14}" width="170" height="${28 + result.series[0].components.length * 26}" rx="8" fill="#040301" stroke="${DATA_COLOR}" opacity="0.88" />
        <text x="${pad.left + 24}" y="${pad.top + 40}" fill="${DATA_COLOR}" font-size="16" font-weight="800">配置明细</text>
        ${result.series[0].components.map((component, index) => `
          <text x="${pad.left + 24}" y="${pad.top + 68 + index * 26}" fill="${seriesColor(index)}" font-size="16" font-weight="800">${componentTitle(component)}</text>
        `).join("")}
      </g>
    `
    : "";

  chart.innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" fill="#181818" />
    <text x="${pad.left}" y="28" fill="${DATA_COLOR}" font-size="18" font-weight="700">${modeLabel}</text>
    <text x="${pad.left + 92}" y="28" fill="${PROFIT_COLOR}" font-size="28" font-weight="800">${current.year} 年</text>
    <text x="${pad.left + 218}" y="28" fill="${DATA_COLOR}" font-size="18">累计投入 ${formatMoney(current.invested)} 元</text>
    <text x="${pad.left + 430}" y="28" fill="${DATA_COLOR}" font-size="18">收益率 ${formatPercent(currentReturn)}</text>
    <text x="${pad.left + 610}" y="28" fill="${profitColor}" font-size="22" font-weight="800">浮盈 ${current.profit >= 0 ? "+" : ""}${formatMoney(current.profit)} 元</text>
    <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" stroke="${DATA_COLOR}" stroke-width="1.5" />
    <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" stroke="${DATA_COLOR}" stroke-width="1.5" />
    <text x="${pad.left}" y="${height - 20}" fill="${DATA_COLOR}" font-size="18">${String(first.date).slice(0, 7)}</text>
    <text x="${width - pad.right - 72}" y="${height - 20}" fill="${DATA_COLOR}" font-size="18">${String(last.date).slice(0, 7)}</text>
    ${componentLegend}
    ${paths}
    <g id="hoverLayer"></g>
  `;
  chartState = {
    width,
    height,
    pad,
    plotWidth,
    plotHeight,
    minValue,
    span,
    points: result.series[0].snapshots.slice(viewportStartSnapshot, snapshotIndex + 1).map((point, pointIndex) => {
      const denom = Math.max(snapshotIndex - viewportStartSnapshot, 1);
      return {
        point,
        color: comparisonMode ? seriesColor(0) : null,
        x: Number(pointToX(pointIndex, denom, pad.left, plotWidth)),
        y: Number(pointToY(point.value, minValue, span, pad.top, plotHeight)),
      };
    }),
  };
}

function pointToX(pointIndex, denom, left, plotWidth) {
  return (left + (pointIndex / denom) * plotWidth).toFixed(1);
}

function pointToY(value, minValue, span, top, plotHeight) {
  return (top + (1 - ((value - minValue) / span)) * plotHeight).toFixed(1);
}

function showFinalResult(result, showOverlay = false) {
  const lines = result.series.map((series) => {
    const summary = series.summary;
    return `${seriesTitle(series)}：投入 ${formatMoney(summary.total_invested)} 元，当前市值 ${formatMoney(summary.final_value)} 元，盈亏 <strong>${summary.profit >= 0 ? "+" : ""}${formatMoney(summary.profit)} 元</strong>，总收益 ${formatPercent(summary.return_rate)}，年化 ${formatPercent(summary.annualized_return)}，最大回撤 ${formatPercent(summary.max_drawdown)}。`;
  });
  resultText.innerHTML = showOverlay ? "" : lines.join("<br>");
  if (showOverlay) {
    const primary = result.series[0];
    const summary = primary.summary;
    const profitClass = summary.profit >= 0 ? "profit" : "loss";
    finalResultOverlay.innerHTML = `
      <div class="final-result-card">
        <h2>${seriesTitle(primary)}</h2>
        <p>最终市值 <strong>${formatMoney(summary.final_value)} 元</strong></p>
        <p>累计投入 ${formatMoney(summary.total_invested)} 元，盈亏 <strong class="${profitClass}">${summary.profit >= 0 ? "+" : ""}${formatMoney(summary.profit)} 元</strong></p>
        <p>总收益 ${formatPercent(summary.return_rate)}，年化 ${formatPercent(summary.annualized_return)}，最大回撤 ${formatPercent(summary.max_drawdown)}</p>
      </div>
    `;
    finalResultOverlay.hidden = false;
  }
}

addStockButton.addEventListener("click", () => addStockRow());
new MutationObserver(() => attachStockWatchers()).observe(stockList, { childList: true, subtree: true });
collapseButton.addEventListener("click", () => workspace.classList.add("collapsed"));
expandButton.addEventListener("click", () => workspace.classList.remove("collapsed"));
marketIndexPanel.addEventListener("dragstart", (event) => {
  const card = event.target.closest(".market-index-card");
  if (!card) return;
  const item = benchmarkFromCard(card);
  event.dataTransfer.setData("application/json", JSON.stringify(item));
  event.dataTransfer.effectAllowed = "copy";
});
marketIndexPanel.addEventListener("click", (event) => {
  const card = event.target.closest(".market-index-card");
  if (!card) return;
  const item = benchmarkFromCard(card);
  addBenchmark(item.code, item.name);
});
chartWrap.addEventListener("dragover", (event) => {
  event.preventDefault();
  chartWrap.classList.add("drag-over");
  event.dataTransfer.dropEffect = "copy";
});
chartWrap.addEventListener("dragleave", (event) => {
  if (!chartWrap.contains(event.relatedTarget)) {
    chartWrap.classList.remove("drag-over");
  }
});
chartWrap.addEventListener("drop", (event) => {
  event.preventDefault();
  chartWrap.classList.remove("drag-over");
  const raw = event.dataTransfer.getData("application/json");
  if (!raw) return;
  try {
    const item = JSON.parse(raw);
    addBenchmark(item.code, item.name);
  } catch {
    // Ignore malformed drag payloads.
  }
});
selectedIndexes.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-benchmark]");
  if (!button) return;
  selectedBenchmarks = selectedBenchmarks.filter((item) => item.code !== button.dataset.removeBenchmark);
  renderSelectedBenchmarks();
});
yearTrigger.addEventListener("click", () => {
  yearPicker.hidden = !yearPicker.hidden;
});
[startYear, endYear].forEach((input) => {
  input.addEventListener("input", () => {
    yearRangeText.textContent = `${startYear.value} - ${endYear.value}`;
    scheduleAllStockPreloads();
  });
});
form.addEventListener("submit", (event) => {
  event.preventDefault();
  runBacktest(true);
});
resultButton.addEventListener("click", () => runBacktest(false));
pauseButton.addEventListener("click", () => {
  paused = !paused;
  pauseButton.textContent = paused ? "继续" : "暂停";
});
replayButton.addEventListener("click", () => {
  if (!activeResult) return;
  showFullChart();
});
chart.addEventListener("mousemove", (event) => {
  if (!chartState || !chartState.points.length) return;
  const rect = chart.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width) * chartState.width;
  const nearest = chartState.points.reduce((best, item) => (
    Math.abs(item.x - x) < Math.abs(best.x - x) ? item : best
  ));
  const layer = chart.querySelector("#hoverLayer");
  if (!layer) return;
  const color = nearest.color || (nearest.point.profit >= 0 ? PROFIT_COLOR : LOSS_COLOR);
  const dateText = String(nearest.point.date).slice(0, 7);
  layer.innerHTML = `
    <line x1="${nearest.x}" y1="${chartState.pad.top}" x2="${nearest.x}" y2="${chartState.height - chartState.pad.bottom}" stroke="${DATA_COLOR}" stroke-width="1.2" stroke-dasharray="5 6" />
    <circle cx="${nearest.x}" cy="${nearest.y}" r="6" fill="${color}" />
    <rect x="${Math.max(chartState.pad.left, nearest.x - 118)}" y="4" width="236" height="30" rx="6" fill="#040301" stroke="${color}" />
    <text x="${Math.max(chartState.pad.left + 10, nearest.x - 106)}" y="25" fill="${color}" font-size="16" font-weight="700">浮盈 ${nearest.point.profit >= 0 ? "+" : ""}${formatMoney(nearest.point.profit)} 元</text>
    <rect x="${Math.max(chartState.pad.left, nearest.x + 10)}" y="${Math.max(chartState.pad.top + 8, nearest.y - 20)}" width="138" height="28" rx="6" fill="#040301" stroke="${color}" />
    <text x="${Math.max(chartState.pad.left + 10, nearest.x + 20)}" y="${Math.max(chartState.pad.top + 28, nearest.y)}" fill="${color}" font-size="15">收益率 ${formatPercent(nearest.point.return_rate)}</text>
    <rect x="${Math.max(chartState.pad.left, nearest.x - 45)}" y="${chartState.height - 42}" width="90" height="26" rx="6" fill="#040301" stroke="${DATA_COLOR}" />
    <text x="${Math.max(chartState.pad.left + 8, nearest.x - 36)}" y="${chartState.height - 23}" fill="${DATA_COLOR}" font-size="15">${dateText}</text>
  `;
});
chart.addEventListener("mouseleave", () => {
  const layer = chart.querySelector("#hoverLayer");
  if (layer) layer.innerHTML = "";
});
yearSlider.addEventListener("input", () => {
  if (playbackComplete) {
    if (fullChartMode) {
      fullChartMode = false;
    }
    showManualViewport(Number(yearSlider.value));
    return;
  }
  paused = true;
  pauseButton.textContent = "继续";
  showFrame(Number(yearSlider.value));
});

addStockRow("600519", "100%");
scheduleAllStockPreloads();
renderSelectedBenchmarks();
loadMarketIndexes();
