let whCharts = {};
let whReportData = [];
const WH_HIDDEN_KPI_KEYS = new Set(["in_progress", "open_orders"]);

function destroyWhCharts() {
  Object.values(whCharts).forEach((c) => c.destroy());
  whCharts = {};
}

function renderWhChart(canvasId, type, labels, values, colors) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !window.Chart) return;
  whCharts[canvasId]?.destroy();
  const isLine = type === "line";
  const dataset = isLine
    ? { data: values, borderColor: colors[0] || "#6366f1", backgroundColor: "rgba(99,102,241,.1)", fill: true, tension: 0.3, borderWidth: 2, pointRadius: 4 }
    : { data: values, backgroundColor: colors, borderRadius: type === "bar" ? 6 : 0, borderWidth: 0 };
  whCharts[canvasId] = new Chart(ctx, {
    type,
    data: { labels, datasets: [{ ...dataset }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: !isLine, position: "bottom", labels: { font: { family: "Vazir" }, padding: 14 } } },
      scales: (type === "bar" || isLine) ? { y: { beginAtZero: true }, x: { ticks: { font: { family: "Vazir" } } } } : {},
    },
  });
}

function whEscAttr(val) {
  return String(val ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function bindWarehouseTableActions() {
  ["tableBody", "whReportTableBody"].forEach((id) => {
    const body = document.getElementById(id);
    if (!body || body._whStagesBound) return;
    body._whStagesBound = true;
    body.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-wh-stages]");
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      const inq = btn.getAttribute("data-wh-stages");
      if (inq && typeof openWarehousePurchaseStages === "function") {
        openWarehousePurchaseStages(inq);
      }
    });
  });
}

function renderWarehouseKpiCards(kpis) {
  const row = document.getElementById("warehouseKpiRow");
  if (!row) return;
  const cards = (kpis?.cards || []).filter((c) => c && c.label && !WH_HIDDEN_KPI_KEYS.has(c.key));
  row.innerHTML = cards.map((c) =>
    `<div class="stat-card !p-3 text-center border-slate-100" title="${c.hint || ""}">
      <p class="text-[10px] text-slate-500 leading-tight">${c.label}</p>
      <p class="text-xl font-bold text-indigo-600 mt-1">${Number(c.value ?? 0).toLocaleString("fa-IR")}<span class="text-[10px] font-normal text-slate-400 mr-0.5">${c.unit || ""}</span></p>
      ${c.hint ? `<p class="text-[9px] text-slate-400 mt-0.5 truncate">${c.hint}</p>` : ""}
    </div>`
  ).join("");
}

function renderWarehouseItemRows(rows) {
  return rows.map((row) => {
    const inq = row["شماره استعلام"] || row.id;
    const viewBtn = inq
      ? `<button type="button" class="text-indigo-600 text-xs font-semibold hover:underline" data-wh-stages="${whEscAttr(inq)}">مشاهده</button>`
      : "—";
    return `<tr>
      <td class="font-medium">${inq || "—"}</td>
      <td>${row["شماره خرید"] || "—"}</td>
      <td title="${whEscAttr(row["عنوان کالا"] || "")}">${typeof truncate === "function" ? truncate(row["عنوان کالا"], 35) : (row["عنوان کالا"] || "—")}</td>
      <td class="text-xs">${row["کد قلم خریدنی"] || "—"}</td>
      <td>${typeof statusBadge === "function" ? statusBadge(row["مرحله فعلی"]) : (row["مرحله فعلی"] || "—")}</td>
      <td class="text-xs whitespace-nowrap">${row["تاریخ استعلام"] || "—"}</td>
      <td class="text-xs">${row["کارشناس خرید"] || "—"}</td>
      <td>${viewBtn}</td>
    </tr>`;
  }).join("");
}

function renderWarehousePurchasesTable(rows) {
  const head = document.getElementById("tableHead");
  const body = document.getElementById("tableBody");
  if (!head || !body) return;

  head.innerHTML = `<tr>
    <th>شماره استعلام</th><th>شماره خرید</th><th>کالا</th><th>کد</th>
    <th>مرحله فعلی</th><th>تاریخ</th><th>کارشناس</th><th>مراحل</th>
  </tr>`;
  body.innerHTML = renderWarehouseItemRows(rows)
    || '<tr><td colspan="8" class="text-center py-12 text-slate-400">خرید ثبت‌شده‌ای برای انبار شما نیست</td></tr>';
  bindWarehouseTableActions();
}

function populateWhReportFilters(options = {}) {
  const stageSel = document.getElementById("whFilterStage");
  const expertSel = document.getElementById("whFilterExpert");
  const curStage = stageSel?.value || "";
  const curExpert = expertSel?.value || "";

  if (stageSel) {
    const stages = options.stages || [];
    stageSel.innerHTML = `<option value="">همه مراحل</option>${stages.map((s) =>
      `<option value="${whEscAttr(s)}">${s}</option>`
    ).join("")}`;
    stageSel.value = stages.includes(curStage) ? curStage : "";
  }
  if (expertSel) {
    const experts = options.experts || [];
    expertSel.innerHTML = `<option value="">همه کارشناسان</option>${experts.map((e) =>
      `<option value="${whEscAttr(e)}">${e}</option>`
    ).join("")}`;
    expertSel.value = experts.includes(curExpert) ? curExpert : "";
  }
}

function filterWhReportRows() {
  const q = (document.getElementById("whFilterSearch")?.value || "").trim().toLowerCase();
  const stage = document.getElementById("whFilterStage")?.value || "";
  const expert = document.getElementById("whFilterExpert")?.value || "";

  return whReportData.filter((row) => {
    if (stage && String(row["مرحله فعلی"] || "") !== stage) return false;
    if (expert && !String(row["کارشناس خرید"] || "").includes(expert)) return false;
    if (q) {
      const hay = [
        row["شماره استعلام"], row["شماره خرید"], row["عنوان کالا"],
        row["کد قلم خریدنی"], row["مرحله فعلی"], row["کارشناس خرید"], row["شماره دستور"],
      ].map((v) => String(v || "")).join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function renderWhReportTable(rows) {
  const body = document.getElementById("whReportTableBody");
  const count = document.getElementById("whReportCount");
  if (!body) return;
  const list = rows ?? filterWhReportRows();
  body.innerHTML = renderWarehouseItemRows(list)
    || '<tr><td colspan="8" class="text-center py-12 text-slate-400">موردی با این فیلتر یافت نشد</td></tr>';
  if (count) {
    count.textContent = `${list.length.toLocaleString("fa-IR")} ردیف از ${whReportData.length.toLocaleString("fa-IR")}`;
  }
  bindWarehouseTableActions();
  highlightWhStageCards();
}

function highlightWhStageCards() {
  const active = document.getElementById("whFilterStage")?.value || "";
  document.querySelectorAll("[data-wh-stage-filter]").forEach((el) => {
    const on = el.getAttribute("data-wh-stage-filter") === active;
    el.classList.toggle("ring-2", on);
    el.classList.toggle("ring-indigo-400", on);
    el.classList.toggle("border-indigo-300", on);
  });
}

function applyWhReportFilters() {
  renderWhReportTable();
}

function clearWhReportFilters() {
  const search = document.getElementById("whFilterSearch");
  const stage = document.getElementById("whFilterStage");
  const expert = document.getElementById("whFilterExpert");
  if (search) search.value = "";
  if (stage) stage.value = "";
  if (expert) expert.value = "";
  renderWhReportTable();
}

function filterWhReportByStage(stageName) {
  const stage = document.getElementById("whFilterStage");
  if (!stage) return;
  const cur = stage.value;
  stage.value = cur === stageName ? "" : stageName;
  renderWhReportTable();
}

async function loadWarehouseDashboard() {
  const errEl = document.getElementById("whDashboardError");
  errEl?.classList.add("hidden");
  try {
    const data = await api("/warehouse/dashboard");
    renderWarehouseKpiCards(data.kpis);
    whReportData = data.table_items || [];
    populateWhReportFilters(data.filter_options || {});
    renderWhReportTable(whReportData);

    const meta = document.getElementById("whDashboardMeta");
    if (meta) {
      const wh = data.warehouse || window.state?.user?.warehouse || "—";
      meta.textContent = `گزارش انبار «${wh}» — آخرین بروزرسانی: ${new Date().toLocaleTimeString("fa-IR")}`;
    }

    const stageCards = document.getElementById("whStageCards");
    if (stageCards) {
      const stages = data.stage_cards || Object.entries(data.by_stage || {}).map(([stage, count]) => ({ stage, count }));
      stageCards.innerHTML = stages.length
        ? stages.map((s) =>
          `<button type="button" data-wh-stage-filter="${whEscAttr(s.stage)}" onclick="filterWhReportByStage(this.getAttribute('data-wh-stage-filter'))"
            class="stat-card text-center border-indigo-100 !p-3 cursor-pointer hover:border-indigo-300 transition-colors w-full">
            <p class="text-[10px] text-slate-500 leading-tight">${s.stage}</p>
            <p class="text-2xl font-bold text-indigo-600 mt-1">${Number(s.count ?? 0).toLocaleString("fa-IR")}</p>
            <p class="text-[10px] text-slate-400 mt-1">مورد · کلیک برای فیلتر</p>
          </button>`
        ).join("")
        : '<p class="text-slate-400 col-span-6 text-sm">هنوز خرید ثبت‌شده‌ای برای انبار شما نیست</p>';
      highlightWhStageCards();
    }

    destroyWhCharts();
    const stageEntries = Object.entries(data.by_stage || {});
    if (stageEntries.length) {
      renderWhChart(
        "chartWhStage",
        "bar",
        stageEntries.map(([k]) => k),
        stageEntries.map(([, v]) => v),
        ["#6366f1"]
      );
    }
    const trend = data.trend || {};
    const trendLabels = Object.keys(trend);
    if (trendLabels.length) {
      renderWhChart("chartWhTrend", "line", trendLabels, Object.values(trend), ["#6366f1"]);
    }

    const recent = document.getElementById("whRecentList");
    if (recent) {
      recent.innerHTML = (data.recent_items || []).map((it) => {
        const inq = it["شماره استعلام"];
        const viewBtn = inq
          ? `<button type="button" class="text-indigo-600 text-[10px] font-semibold hover:underline shrink-0" data-wh-stages="${whEscAttr(inq)}">مشاهده</button>`
          : "";
        return `<div class="flex justify-between items-center gap-2 p-2 rounded-lg bg-slate-50 border border-slate-100 text-sm">
          <div class="min-w-0"><span class="font-medium">${inq || "—"}</span> · ${typeof truncate === "function" ? truncate(it["عنوان کالا"], 30) : it["عنوان کالا"]}</div>
          <div class="flex items-center gap-2 shrink-0">${typeof statusBadge === "function" ? statusBadge(it["مرحله فعلی"]) : it["مرحله فعلی"]}${viewBtn}</div>
        </div>`;
      }).join("") || '<p class="text-slate-400 text-sm">موردی نیست</p>';
      bindWarehouseTableActions();
    }
  } catch (e) {
    if (errEl) {
      errEl.textContent = e.message;
      errEl.classList.remove("hidden");
    }
  }
}

async function loadWarehouseLookup() {
  await loadWarehouseDashboard();
}

function renderWhRegisteredPurchasesTable(title, rows) {
  if (!rows?.length) {
    return `<div class="chart-box"><h4 class="font-bold text-sm mb-2">${title}</h4><p class="text-sm text-slate-400">موردی نیست</p></div>`;
  }
  const body = rows.map((row) => {
    const inq = row["شماره استعلام"];
    const viewBtn = inq
      ? `<button type="button" class="text-indigo-600 text-xs font-semibold hover:underline" data-wh-stages="${whEscAttr(inq)}">مشاهده</button>`
      : "—";
    return `<tr>
      <td class="text-xs">${row["شماره دستور"] ?? "—"}</td>
      <td class="text-xs">${row["شماره استعلام"] ?? "—"}</td>
      <td class="text-xs">${row["مرحله فعلی"] ?? "—"}</td>
      <td class="text-xs">${row["تاریخ دستور"] ?? "—"}</td>
      <td class="text-xs">${row["کارشناس"] ?? "—"}</td>
      <td>${viewBtn}</td>
    </tr>`;
  }).join("");
  return `<div class="chart-box overflow-x-auto"><h4 class="font-bold text-sm mb-2">${title}</h4>
    <table class="data-table !text-xs"><thead><tr>
      <th>دستور</th><th>استعلام</th><th>مرحله</th><th>تاریخ</th><th>کارشناس</th><th>مراحل</th>
    </tr></thead><tbody>${body}</tbody></table></div>`;
}

function renderWhTable(title, rows, cols) {
  if (!rows?.length) {
    return `<div class="chart-box"><h4 class="font-bold text-sm mb-2">${title}</h4><p class="text-sm text-slate-400">موردی نیست</p></div>`;
  }
  const head = cols.map((c) => `<th>${c.label}</th>`).join("");
  const body = rows.map((row) =>
    `<tr>${cols.map((c) => `<td class="text-xs">${row[c.key] ?? "—"}</td>`).join("")}</tr>`
  ).join("");
  return `<div class="chart-box overflow-x-auto"><h4 class="font-bold text-sm mb-2">${title}</h4>
    <table class="data-table !text-xs"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function renderWarehouseLookupResult(data) {
  const box = document.getElementById("whLookupResult");
  if (!box) return;

  const summaryCls = data.has_material_requests || data.has_purchase_requests
    ? "bg-emerald-50 border-emerald-200 text-emerald-900"
    : "bg-amber-50 border-amber-200 text-amber-900";

  box.innerHTML = `
    <div class="rounded-xl border px-4 py-3 text-sm ${summaryCls}">${data.summary || "—"}</div>
    ${renderWhTable("درخواست‌های ثبت قلم (درخواست کالا)", data.material_requests, [
      { key: "شماره درخواست کالا", label: "شماره درخواست کالا" },
      { key: "شماره خرید", label: "شماره خرید" },
      { key: "عنوان قلم", label: "عنوان" },
      { key: "کد قلم", label: "کد" },
      { key: "تاریخ درخواست", label: "تاریخ" },
      { key: "وضعیت", label: "وضعیت" },
    ])}
    ${renderWhTable("درخواست‌های خرید انبار شما", data.purchase_requests, [
      { key: "شماره خرید", label: "شماره خرید" },
      { key: "عنوان قلم خریدنی", label: "عنوان" },
      { key: "کد قلم خریدنی", label: "کد" },
      { key: "وضعیت", label: "وضعیت" },
      { key: "تاریخ درخواست کالا", label: "تاریخ" },
    ])}
    ${renderWhTable("آخرین خریدها", data.last_purchases, [
      { key: "تاریخ", label: "تاریخ" },
      { key: "عنوان کالا", label: "کالا" },
      { key: "فی", label: "فی" },
      { key: "تعداد", label: "تعداد" },
      { key: "تامین‌کننده", label: "تامین‌کننده" },
      { key: "شماره خرید", label: "خرید" },
    ])}
    ${renderWhRegisteredPurchasesTable("وضعیت خریدهای ثبت‌شده مرتبط", data.orders)}`;
}

async function searchWarehouseProduct() {
  const code = document.getElementById("whProductCode")?.value?.trim() || "";
  const title = document.getElementById("whProductTitle")?.value?.trim() || "";
  const errEl = document.getElementById("whLookupError");
  errEl?.classList.add("hidden");
  if (!code && !title) {
    if (errEl) {
      errEl.textContent = "حداقل کد یا عنوان کالا را وارد کنید";
      errEl.classList.remove("hidden");
    }
    return;
  }
  showLoading("در حال جستجو...");
  try {
    const params = new URLSearchParams();
    if (code) params.set("code", code);
    if (title) params.set("title", title);
    const data = await api(`/warehouse/product-lookup?${params}`);
    renderWarehouseLookupResult(data);
  } catch (e) {
    if (errEl) {
      errEl.textContent = e.message;
      errEl.classList.remove("hidden");
    }
  } finally {
    hideLoading();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bindWarehouseTableActions();
  document.getElementById("whFilterSearch")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") applyWhReportFilters();
  });
  const recent = document.getElementById("whRecentList");
  recent?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-wh-stages]");
    if (!btn) return;
    e.preventDefault();
    const inq = btn.getAttribute("data-wh-stages");
    if (inq && typeof openWarehousePurchaseStages === "function") openWarehousePurchaseStages(inq);
  });
  document.getElementById("whLookupResult")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-wh-stages]");
    if (!btn) return;
    e.preventDefault();
    const inq = btn.getAttribute("data-wh-stages");
    if (inq && typeof openWarehousePurchaseStages === "function") openWarehousePurchaseStages(inq);
  });
});

window.loadWarehouseDashboard = loadWarehouseDashboard;
window.loadWarehouseLookup = loadWarehouseLookup;
window.renderWarehousePurchasesTable = renderWarehousePurchasesTable;
window.searchWarehouseProduct = searchWarehouseProduct;
window.applyWhReportFilters = applyWhReportFilters;
window.clearWhReportFilters = clearWhReportFilters;
window.filterWhReportByStage = filterWhReportByStage;