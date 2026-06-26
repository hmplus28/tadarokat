window.state = {
  user: null,
  view: "dashboard",
  filter: "",
  search: "",
  advExpert: "",
  advStatus: "",
  advWarehouse: "",
  advUrgency: "",
  advPurchaseType: "",
  dashExpert: "",
  searchTimer: null,
  page: 1,
  pageSize: 50,
  total: 0,
  totalPages: 0,
  selectedRow: null,
  data: [],
  stats: {},
  refreshTimer: null,
  charts: {},
  loadingCount: 0,
};

const REFRESH_MS = 60000;

const EXPORTABLE_VIEWS = new Set([
  "dashboard", "requests", "inquiries", "inquiry_review", "my_inquiries",
  "orders", "deliveries", "report_purchase", "report_expert", "report_my", "report_reorder",
  "report_duration", "history",
  "warehouse_dashboard", "warehouse_purchases",
]);

function isManager() {
  return ["admin", "manager"].includes(window.state?.user?.role);
}

function isAdmin() {
  return window.state?.user?.role === "admin";
}

function isExpert() {
  return window.state?.user?.role === "expert";
}

function isWarehouse() {
  return window.state?.user?.role === "warehouse";
}

function isReadOnly() {
  return isWarehouse();
}

function rowBelongsToExpert(row) {
  const role = window.state?.user?.role;
  if (role === "admin") return true;
  if (role !== "expert") return false;
  const expertName = window.state?.user?.expert || window.state?.user?.name || "";
  if (!expertName) return false;
  const assigned = String(row["کارشناس خرید"] || "");
  return assigned.includes(expertName);
}

function canIssueInquiry(row) {
  if (!row) return false;
  const role = window.state?.user?.role;
  if (role === "manager" || role === "warehouse") return false;
  if (role === "expert" && !rowBelongsToExpert(row)) return false;
  if (role !== "expert" && role !== "admin") return false;
  const has = row.has_local_inquiry === true || row.has_local_inquiry === "true" || row.has_local_inquiry === 1;
  const approved = row.inquiry_approved === true || row.inquiry_approved === "true" || row.inquiry_approved === 1;
  return !has && !approved;
}

window.isManager = isManager;
window.isAdmin = isAdmin;
window.isExpert = isExpert;
window.isWarehouse = isWarehouse;
window.isReadOnly = isReadOnly;
window.canIssueInquiry = canIssueInquiry;
window.rowBelongsToExpert = rowBelongsToExpert;
const PAGINATED_VIEWS = new Set([
  "requests", "inquiries", "inquiry_review", "my_inquiries",
  "orders", "deliveries", "warehouse_purchases", "warehouse_deliveries",
  "report_reorder", "history",
]);

const VIEWS = {
  dashboard: { title: "داشبورد", endpoint: "/reports/dashboard", dashboard: true },
  requests: { title: "درخواست‌های خرید", endpoint: "/requests", paginated: true },
  inquiries: { title: "فهرست استعلام", endpoint: "/inquiries", paginated: true },
  inquiry_review: { title: "بررسی استعلام‌ها", endpoint: "/inquiries/local", paginated: true, managerOnly: true },
  my_inquiries: { title: "استعلام‌های من", endpoint: "/inquiries/mine", paginated: true, expertOnly: true },
  orders: { title: "فهرست دستور خرید", endpoint: "/orders", paginated: true, customTable: "orders" },
  deliveries: { title: "فهرست تحویل", endpoint: "/deliveries", paginated: true, customTable: "deliveries" },
  warehouse_dashboard: { title: "گزارش انبار", warehouseOnly: true, warehouseDashboard: true },
  warehouse_lookup: { title: "استعلام کالا", warehouseOnly: true, warehouseLookup: true },
  warehouse_purchases: { title: "وضعیت خریدهای ثبت‌شده", endpoint: "/warehouse/purchases", paginated: true, customTable: "warehouse_purchases", warehouseOnly: true },
  warehouse_deliveries: { title: "تحویل‌های انبار", endpoint: "/deliveries", paginated: true, customTable: "deliveries", warehouseOnly: true },
  notifications: { title: "اعلان‌ها", notifications: true, warehouseOnly: true },
  report_purchase: { title: "گزارش خرید", endpoint: "/reports/purchase", report: true },
  report_my: { title: "گزارش من", endpoint: "/reports/my", report: true, expertOnly: true },
  report_duration: { title: "مدت زمان مراحل", duration: true, managerOnly: true },
  report_expert: { title: "گزارش کارشناس", endpoint: "/reports/expert", report: true, managerOnly: true },
  report_reorder: { title: "نقطه سفارش", endpoint: "/reports/reorder", paginated: true },
  users: { title: "مدیریت کاربران", admin: true },
  history: { title: "تاریخچه ویرایش", endpoint: "/history", paginated: true, admin: true },
  settings: { title: "پنل مدیریت سیستم", admin: true, settings: true },
};

const PURCHASE_COLUMNS = [
  ["شماره", "شماره خرید"],
  ["شماره مبنا", "درخواست کالا"],
  ["تاریخ درخواست کالا", "تاریخ ثبت"],
  ["عنوان قلم خریدنی", "عنوان کالا"],
  ["کد قلم خریدنی", "کد"],
  ["نوع قلم خریدنی", "دسته"],
  ["تاریخ", "تاریخ تبدیل"],
  ["تاریخ نیاز", "تاریخ نیاز"],
  ["وضعیت", "وضعیت"],
  ["رمز فوریت", "اولویت"],
  ["کارشناس خرید", "کارشناس"],
  ["نوع خرید", "نوع خرید"],
  ["local_inquiry_number", "استعلام محلی"],
  ["وضعیت فعلی خرید", "وضعیت فعلی خرید"],
  ["درخواست کننده", "درخواست‌کننده"],
  ["توضیحات", "توضیحات"],
];

const STATUS_CLASS = {
  "در جریان": "badge-blue",
  "بسته شده": "badge-green",
  "تایید شده": "badge-green",
  "تحویل شده": "badge-green",
  "معلق": "badge-amber",
  "ثبت شده": "badge-slate",
  "صدور دستور": "badge-slate",
  "دستور خرید": "badge-slate",
  "سفارش": "badge-blue",
  "ثبت پرداخت": "badge-blue",
  "تبدیل وضعیت پرداخت": "badge-blue",
  "تحویل": "badge-green",
  "در انتظار": "badge-slate",
  "ثبت استعلام": "badge-blue",
  "دستور شده": "badge-purple",
};

function $(id) { return document.getElementById(id); }

function showLoading(msg = "در حال بارگذاری...") {
  state.loadingCount++;
  const el = $("loadingPopup");
  if (el) {
    $("loadingText").textContent = msg;
    el.classList.remove("hidden");
  }
}

function hideLoading() {
  state.loadingCount = Math.max(0, state.loadingCount - 1);
  if (state.loadingCount === 0) $("loadingPopup")?.classList.add("hidden");
}

function statusBadge(s) {
  return `<span class="badge ${STATUS_CLASS[s] || "badge-slate"}">${s || "—"}</span>`;
}

function truncate(t, n = 45) {
  if (!t) return "—";
  const s = String(t);
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function setView(view, options = {}) {
  const cfg = VIEWS[view];
  if (!cfg) return;
  if (cfg?.admin && state.user?.role !== "admin") return;
  if (cfg?.managerOnly && !isManager()) return;
  if (cfg?.expertOnly && !isExpert()) return;
  if (cfg?.warehouseOnly && !isWarehouse()) return;
  if (isWarehouse() && !cfg.warehouseOnly && view !== "warehouse_dashboard" && view !== "warehouse_lookup" && view !== "warehouse_purchases" && view !== "warehouse_deliveries" && view !== "notifications") {
    view = "warehouse_dashboard";
    return setView(view);
  }
  if (isExpert() && (cfg?.managerOnly || view === "report_purchase" || view === "report_reorder" || view === "inquiries" || view === "inquiry_review")) {
    view = "report_my";
    return setView(view);
  }

  state.view = view;
  state.page = 1;
  if (options.filter !== undefined) {
    state.filter = options.filter;
    document.querySelectorAll(".filter-chip").forEach((el) => {
      el.classList.toggle("active", el.dataset.filter === state.filter);
    });
  }
  document.querySelectorAll(".nav-link").forEach((el) => {
    el.classList.toggle("active", isNavLinkActive(el, view));
  });
  $("pageTitle").textContent = (view === "requests" && state.filter === "no_inquiry")
    ? "صدور استعلام"
    : cfg.title;
  $("pageSubtitle").textContent = getSubtitle(view);

  const isPurchaseReport = view === "report_purchase";
  const isExpertReport = view === "report_expert" || view === "report_my";
  const showTable = !cfg.dashboard && !cfg.duration && !cfg.notifications && !cfg.settings
    && !cfg.warehouseLookup && !cfg.warehouseDashboard && view !== "users"
    && !isPurchaseReport && !isExpertReport;
  $("tableSection").classList.toggle("hidden", !showTable);
  $("purchaseReportSection")?.classList.toggle("hidden", !isPurchaseReport);
  $("expertReportSection")?.classList.toggle("hidden", !isExpertReport);
  $("dashFilterBar")?.classList.toggle("hidden", view !== "dashboard" || !isManager());
  $("warehouseLookupSection")?.classList.toggle("hidden", view !== "warehouse_lookup");
  $("warehouseDashboardSection")?.classList.toggle("hidden", view !== "warehouse_dashboard");
  $("dashboardSection").classList.toggle("hidden", view !== "dashboard");
  $("settingsSection")?.classList.toggle("hidden", view !== "settings");
  $("usersSection").classList.toggle("hidden", view !== "users");
  $("durationSection").classList.toggle("hidden", view !== "report_duration");
  $("notificationsSection").classList.toggle("hidden", view !== "notifications");
  $("filterBar").classList.toggle("hidden", view !== "requests" || isWarehouse());
  const hideSearch = view === "warehouse_lookup";
  $("searchInput")?.classList.toggle("hidden", hideSearch);
  document.querySelector('button[onclick="doSearch()"]')?.classList.toggle("hidden", hideSearch);
  $("paginationBar").classList.toggle("hidden", !PAGINATED_VIEWS.has(view));
  $("deliveriesToolbar")?.classList.toggle("hidden", view !== "deliveries" || isReadOnly());
  $("btnExportExcel")?.classList.toggle("hidden", !EXPORTABLE_VIEWS.has(view));
  $("kpiRow")?.classList.toggle("hidden", view !== "dashboard");
  updateAdvFiltersUI(view);

  if (view === "users") loadUsers();
  else if (view === "notifications" && typeof loadNotifications === "function") loadNotifications();
  else if (view === "report_duration") loadDurationReport();
  else if (view === "settings" && typeof loadSystemPaths === "function") loadSystemPaths();
  else if (view === "warehouse_dashboard" && typeof loadWarehouseDashboard === "function") loadWarehouseDashboard();
  else if (view === "warehouse_lookup" && typeof loadWarehouseLookup === "function") loadWarehouseLookup();
  else loadViewData();
}

function getSubtitle(view) {
  const map = {
    dashboard: "نمای کلی وضعیت تدارکات",
    requests: state.filter === "no_inquiry"
      ? "درخواست‌های خرید بدون استعلام — آماده صدور استعلام"
      : "مدیریت و پیگیری درخواست‌های خرید",
    users: "ایجاد، ویرایش و حذف کاربران سیستم",
    report_purchase: "تحلیل وضعیت و نوع خریدها",
    report_my: "خلاصه خریدها و وضعیت جریان — فقط موارد شما",
    report_expert: "عملکرد کارشناسان خرید",
    report_duration: "میانگین روز بین مراحل — ماهانه و سالانه",
    orders: "دستورات صادرشده از پنل مدیر — فقط فایل محلی (بدون اکسل)",
    deliveries: "ثبت و پیگیری تحویل — مستقل از اکسل",
    warehouse_dashboard: "داشبورد گزارش — وضعیت خریدهای ثبت‌شده انبار شما",
    warehouse_lookup: "جستجو بر اساس کد و عنوان — درخواست ثبت قلم و آخرین خرید",
    warehouse_purchases: "لیست خریدهای ثبت‌شده با مرحله جریان",
    warehouse_deliveries: "مشاهده تحویل‌های مرتبط با انبار شما",
    notifications: "فقط اعلان‌های مرحله تحویل",
    history: "ثبت تمام تغییرات — فقط مدیر سیستم",
    settings: "تنظیم Share، اکسل ورودی/خروجی، پایگاه داده و پشتیبان",
  };
  return map[view] || "داده محلی سامانه";
}

function setFilter(filter) {
  state.filter = filter;
  state.page = 1;
  document.querySelectorAll(".filter-chip").forEach((el) => {
    el.classList.toggle("active", el.dataset.filter === filter);
  });
  if (state.view !== "requests") setView("requests", { filter });
  else {
    syncRequestsNavActive();
    if ($("pageSubtitle")) $("pageSubtitle").textContent = getSubtitle("requests");
    loadViewData();
  }
}

function isNavLinkActive(el, view = state.view) {
  const navView = el.dataset.view;
  if (navView !== view) return false;
  const navFilter = el.dataset.defaultFilter;
  if (navFilter) return navFilter === state.filter;
  if (view === "requests") return state.filter !== "no_inquiry";
  return true;
}

function syncRequestsNavActive() {
  document.querySelectorAll(".nav-link").forEach((el) => {
    el.classList.toggle("active", isNavLinkActive(el));
  });
}

function toggleSidebar() {
  $("sidebar").classList.toggle("open");
}

function updateStatsUI(stats) {
  $("statTotal").textContent = stats.total.toLocaleString("fa-IR");
  $("statActive").textContent = stats.purchase.toLocaleString("fa-IR");
  $("statInquiry").textContent = stats.inquiry.toLocaleString("fa-IR");
  $("statPending").textContent = stats.returned.toLocaleString("fa-IR");
  $("statClosed").textContent = stats.closed.toLocaleString("fa-IR");
  $("badgeTotal").textContent = stats.total.toLocaleString("fa-IR");
  $("badgePurchase").textContent = stats.purchase.toLocaleString("fa-IR");
  if ($("badgeLines")) $("badgeLines").textContent = (stats.total_lines ?? stats.total).toLocaleString("fa-IR");
  $("lastUpdate").textContent = new Date().toLocaleTimeString("fa-IR");
}

async function loadStats() {
  const stats = await api("/stats");
  state.stats = stats;
  updateStatsUI(stats);
}

function getExpertFilter() {
  if (state.view === "dashboard") {
    const v = $("dashFilterExpert")?.value ?? state.dashExpert ?? "";
    state.dashExpert = v;
    return v;
  }
  const v = $("filterExpert")?.value ?? state.advExpert ?? "";
  state.advExpert = v;
  return v;
}

function buildUrl(cfg) {
  const params = new URLSearchParams();
  if (state.search) params.set("search", state.search);
  if (state.view === "requests" && state.filter) params.set("filter", state.filter);
  const expertFilter = getExpertFilter();
  if (expertFilter) params.set("expert", expertFilter);
  if (state.advStatus) params.set("status", state.advStatus);
  if (state.advWarehouse) params.set("warehouse", state.advWarehouse);
  const usePurchaseFilters = state.view === "requests" || state.view === "report_purchase";
  if (usePurchaseFilters && state.advUrgency) params.set("urgency", state.advUrgency);
  if (usePurchaseFilters && state.advPurchaseType) params.set("purchase_type", state.advPurchaseType);
  if (state.view === "report_duration") {
    params.set("period", $("durationPeriod")?.value || state.durationPeriod || "month");
  }
  if (cfg.paginated) {
    params.set("page", state.page);
    params.set("page_size", state.pageSize);
  }
  const qs = params.toString();
  return `${cfg.endpoint}${qs ? "?" + qs : ""}`;
}

function updateAdvFiltersUI(view) {
  const bar = $("advFilters");
  const inquiryViews = new Set(["inquiries", "inquiry_review", "my_inquiries"]);
  const requestViews = new Set(["requests"]);
  const reportViews = new Set(["report_purchase", "report_expert", "report_my"]);
  const showBar = inquiryViews.has(view) || requestViews.has(view) || reportViews.has(view);
  if (bar) bar.classList.toggle("hidden", !showBar);
  const showExpert = isManager() && (showBar || view === "dashboard");
  $("filterExpert")?.classList.toggle("hidden", !showExpert || view === "dashboard");
  $("filterInquiryStatus")?.classList.toggle("hidden", !inquiryViews.has(view));
  $("filterWarehouse")?.classList.toggle("hidden", !inquiryViews.has(view));
  const showPurchaseTypeFilters = requestViews.has(view) || view === "report_purchase";
  $("filterUrgency")?.classList.toggle("hidden", !showPurchaseTypeFilters);
  $("filterPurchaseType")?.classList.toggle("hidden", !showPurchaseTypeFilters);
}

function applyDashFilter() {
  state.dashExpert = $("dashFilterExpert")?.value || "";
  if ($("filterExpert") && state.dashExpert) $("filterExpert").value = state.dashExpert;
  loadViewData();
}

function syncDashExpertSelect() {
  const dash = $("dashFilterExpert");
  const header = $("filterExpert");
  if (!dash || !header) return;
  const cur = state.dashExpert || dash.value || "";
  dash.innerHTML = header.innerHTML;
  if (cur && [...dash.options].some((o) => o.value === cur)) dash.value = cur;
}

function applyAdvFilters() {
  state.advExpert = $("filterExpert")?.value || "";
  if ($("dashFilterExpert") && state.view !== "dashboard") {
    $("dashFilterExpert").value = state.advExpert;
    state.dashExpert = state.advExpert;
  }
  state.advStatus = $("filterInquiryStatus")?.value || "";
  state.advWarehouse = $("filterWarehouse")?.value || "";
  state.advUrgency = $("filterUrgency")?.value || "";
  state.advPurchaseType = $("filterPurchaseType")?.value || "";
  state.page = 1;
  loadViewData();
}

function clearSearch() {
  state.search = "";
  state.advExpert = "";
  state.dashExpert = "";
  state.advStatus = "";
  state.advWarehouse = "";
  state.advUrgency = "";
  state.advPurchaseType = "";
  if ($("searchInput")) $("searchInput").value = "";
  ["filterExpert", "filterInquiryStatus", "filterWarehouse", "filterUrgency", "filterPurchaseType", "dashFilterExpert"].forEach((id) => {
    const el = $(id);
    if (el) el.value = "";
  });
  state.page = 1;
  loadViewData();
}

function scheduleSearch() {
  clearTimeout(state.searchTimer);
  state.searchTimer = setTimeout(() => {
    state.search = $("searchInput")?.value?.trim() || "";
    state.page = 1;
    loadViewData();
  }, 350);
}

async function loadViewData(silent = false) {
  const cfg = VIEWS[state.view];
  if (!cfg || cfg.notifications || cfg.duration || cfg.settings || cfg.warehouseLookup || cfg.warehouseDashboard || state.view === "users") return;

  if (!silent) showLoading("در حال دریافت داده‌ها...");
  try {
    if (cfg.dashboard) {
      const data = await api(buildUrl(cfg));
      renderDashboard(data);
      if (isExpert()) await loadStats().catch(() => {});
      return;
    }

    const result = await api(buildUrl(cfg));

    if (cfg.report) {
      renderReport(state.view, result);
    } else if (cfg.paginated) {
      state.data = result.items || [];
      state.total = result.total || 0;
      state.totalPages = result.total_pages || 0;
      if (cfg.customTable === "orders" && typeof renderOrdersTable === "function") {
        renderOrdersTable(state.data);
      } else if (cfg.customTable === "deliveries" && typeof renderDeliveriesTable === "function") {
        renderDeliveriesTable(state.data);
      } else if (cfg.customTable === "warehouse_purchases" && typeof renderWarehousePurchasesTable === "function") {
        renderWarehousePurchasesTable(state.data);
      } else {
        renderTable(state.data);
      }
      renderPagination();
    } else {
      state.data = Array.isArray(result) ? result : [result];
      renderTable(state.data);
    }

  } catch (e) {
    if ($("tableBody")) {
      $("tableBody").innerHTML = `<tr><td colspan="20" class="text-center py-10 text-red-500">${e.message}</td></tr>`;
    }
  } finally {
    if (!silent) hideLoading();
  }
}

function renderPagination() {
  const bar = $("paginationBar");
  if (!bar) return;
  const { page, totalPages, total, pageSize } = state;
  $("pageInfo").textContent = `صفحه ${page.toLocaleString("fa-IR")} از ${(totalPages || 1).toLocaleString("fa-IR")} — ${total.toLocaleString("fa-IR")} ردیف`;
  $("btnPrev").disabled = page <= 1;
  $("btnNext").disabled = page >= totalPages;
  $("pageSizeSelect").value = String(pageSize);
}

function goPage(p) {
  if (p < 1 || (state.totalPages && p > state.totalPages)) return;
  state.page = p;
  loadViewData();
}

function changePageSize(size) {
  state.pageSize = parseInt(size, 10) || 50;
  state.page = 1;
  loadViewData();
}

function renderKpiCards(kpis) {
  const row = $("kpiRow");
  if (!row) return;
  const cards = (kpis?.cards || []).filter((c) => c && c.label);
  if (!cards.length) {
    row.innerHTML = "";
    return;
  }
  row.innerHTML = cards.map((c) =>
    `<div class="stat-card !p-3 text-center border-slate-100" title="${c.hint || ""}">
      <p class="text-[10px] text-slate-500 leading-tight">${c.label}</p>
      <p class="text-xl font-bold text-indigo-600 mt-1">${Number(c.value ?? 0).toLocaleString("fa-IR")}<span class="text-[10px] font-normal text-slate-400 mr-0.5">${c.unit || ""}</span></p>
      ${c.hint ? `<p class="text-[9px] text-slate-400 mt-0.5 truncate">${c.hint}</p>` : ""}
    </div>`
  ).join("");
}

function renderManagerDurationBlock(data, activeExpert, tl) {
  const box = $("managerFilteredTimeline");
  if (!box || !isManager()) {
    box?.classList.add("hidden");
    return;
  }

  const unit = data.duration_unit || "روز";
  const unitNote = data.duration_unit_note || "روز تقویمی — فاصله بین تاریخ‌های ثبت‌شده در پنل";
  const expertsDur = data.experts_duration || [];

  if (activeExpert) {
    const stages = tl?.stages || [];
    box.classList.remove("hidden");
    if (!stages.length) {
      box.innerHTML = `<div class="chart-box">
        <h4 class="font-bold text-sm mb-2">میانگین مدت مراحل — ${activeExpert}</h4>
        <p class="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg p-3">برای این کارشناس هنوز تاریخ مراحل در پنل ثبت نشده.</p>
        <p class="text-[10px] text-slate-400 mt-2">واحد: <strong>${unit}</strong> — ${unitNote}</p>
      </div>`;
      return;
    }
    box.innerHTML = `<div class="chart-box">
      <div class="flex flex-wrap justify-between items-center gap-2 mb-2">
        <h4 class="font-bold text-sm">میانگین مدت مراحل — ${activeExpert}</h4>
        <span class="text-[10px] text-slate-600 bg-indigo-50 text-indigo-800 px-2 py-1 rounded border border-indigo-100">واحد: ${unit}</span>
      </div>
      <p class="text-[10px] text-slate-400 mb-3">${unitNote}</p>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2">${stages.map((s) =>
        `<div class="stat-card !p-2 text-center border-indigo-50">
          <p class="text-[10px] text-slate-500 leading-tight">${s.stage}</p>
          <p class="text-lg font-bold text-indigo-600 mt-1">${Number(s.avg_days || 0).toLocaleString("fa-IR")} <span class="text-xs font-normal text-slate-500">${unit}</span></p>
          <p class="text-[9px] text-slate-400">${s.count || 0} نمونه</p>
        </div>`
      ).join("")}</div>
    </div>`;
    return;
  }

  if (!expertsDur.length) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }

  const stageNames = [...new Set(expertsDur.flatMap((e) => (e.stages || []).map((s) => s.stage)))];
  box.classList.remove("hidden");
  box.innerHTML = `<div class="chart-box">
    <div class="flex flex-wrap justify-between items-center gap-2 mb-2">
      <h4 class="font-bold text-sm">میانگین مدت مراحل — همه کارشناسان</h4>
      <span class="text-[10px] text-slate-600 bg-indigo-50 text-indigo-800 px-2 py-1 rounded border border-indigo-100">واحد: ${unit}</span>
    </div>
    <p class="text-[10px] text-slate-400 mb-3">${unitNote} · برای جزئیات مراحل، یک کارشناس را از فیلتر بالا انتخاب کنید.</p>
    <div class="table-wrap report-table-wrap">
      <table class="data-table report-data-table !text-xs">
        <thead><tr>
          <th>کارشناس</th><th>تعداد نمونه</th><th>میانگین کل (${unit})</th>
          ${stageNames.map((st) => `<th title="${unit}">${st}</th>`).join("")}
        </tr></thead>
        <tbody>${expertsDur.map((row) => {
          const stageMap = Object.fromEntries((row.stages || []).map((s) => [s.stage, s]));
          return `<tr>
            <td class="font-medium whitespace-nowrap">${row.expert}</td>
            <td>${row.has_data ? row.sample_count : "—"}</td>
            <td class="font-medium text-indigo-700">${row.has_data ? `${row.overall_avg_days} ${unit}` : '<span class="text-amber-600 font-normal">بدون داده</span>'}</td>
            ${stageNames.map((st) => {
              const s = stageMap[st];
              return `<td>${s ? `${s.avg_days} ${unit} <span class="text-slate-400">(${s.count})</span>` : "—"}</td>`;
            }).join("")}
          </tr>`;
        }).join("")}</tbody>
      </table>
    </div>
  </div>`;
}

function renderDashboard(data) {
  const { stats, summary, experts, expert_timeline: tl, kpis, filtered_expert: filteredExp } = data;
  const activeExpert = filteredExp || getExpertFilter() || "";
  destroyCharts();
  // آمار هدر/بج «درخواست‌های خرید» فقط از /api/stats (ERP) — نه از داشبورد محلی کارشناس
  if (!isExpert()) {
    updateStatsUI(stats);
    state.stats = stats;
  }
  renderKpiCards(kpis);

  const expertPanel = $("dashboardExpertPanel");
  const managerPanel = $("dashboardManagerPanel");

  if ($("pageSubtitle") && state.view === "dashboard") {
    $("pageSubtitle").textContent = activeExpert
      ? `نمای فیلترشده — کارشناس: ${activeExpert}`
      : getSubtitle("dashboard");
  }

  if (isExpert() && tl) {
    expertPanel?.classList.remove("hidden");
    managerPanel?.classList.add("hidden");

    const durUnit = data.duration_unit || tl.unit || "روز";
    const durNote = data.duration_unit_note || tl.unit_note || "";
    $("expertStageCards").innerHTML = (tl.stages || []).map((s) =>
      `<div class="stat-card text-center border-indigo-100">
        <p class="text-xs text-slate-500">${s.stage}</p>
        <p class="text-2xl font-bold text-indigo-600 mt-1">${Number(s.avg_days || 0).toLocaleString("fa-IR")} <span class="text-sm font-normal text-slate-500">${durUnit}</span></p>
        <p class="text-[10px] text-slate-400 mt-1">بر اساس ${s.count || 0} نمونه</p>
      </div>`
    ).join("") || `<p class="text-slate-400 col-span-4 text-sm">هنوز تاریخ مراحل در پنل ثبت نشده — ${durNote || "واحد: روز تقویمی"}</p>`;

    const trend = tl.trend || {};
    const tLabels = Object.keys(trend);
    const tVals = Object.values(trend);
    if (tLabels.length) renderChart("chartExpertTrend", "line", tLabels, tVals, ["#6366f1"]);

    $("expertRecentItems").innerHTML = (tl.items || []).map((it) =>
      `<div class="flex justify-between items-start p-2 rounded-lg bg-slate-50 border border-slate-100">
        <div><p class="text-xs font-bold">${it.type} ${it.ref}</p><p class="text-[10px] text-slate-500">${truncate(it.title, 40)}</p></div>
        <span class="badge badge-slate text-[10px]">${it.status}</span>
      </div>`
    ).join("") || '<p class="text-slate-400 text-xs">موردی نیست</p>';

    renderChart("chartStatus", "doughnut", Object.keys(stats.by_status || {}), Object.values(stats.by_status || {}), ["#6366f1", "#10b981", "#f59e0b", "#94a3b8"]);
    const trendEntries = Object.entries(summary.monthly_trend || summary.urgency_breakdown || {});
    const urgency = trendEntries.map(([k, v]) =>
      `<div class="flex justify-between py-2 border-b border-slate-100 text-sm"><span>${k || "—"}</span><strong>${v}</strong></div>`
    ).join("");
    $("urgencyList").innerHTML = urgency || '<p class="text-slate-400 text-sm">بدون داده</p>';
    return;
  }

  expertPanel?.classList.add("hidden");
  managerPanel?.classList.remove("hidden");

  renderChart("chartStatusMgr", "doughnut", Object.keys(stats.by_status || {}), Object.values(stats.by_status || {}), ["#6366f1", "#10b981", "#f59e0b", "#94a3b8"]);
  renderChart("chartType", "bar", Object.keys(stats.by_type || {}), Object.values(stats.by_type || {}), ["#8b5cf6", "#06b6d4"]);
  if (isManager() && experts && !activeExpert) {
    $("expertChartBox")?.classList.remove("hidden");
    renderChart("chartExpert", "bar", experts.map((e) => e["کارشناس خرید"] || "—"), experts.map((e) => e.total), ["#6366f1"]);
  } else {
    $("expertChartBox")?.classList.add("hidden");
  }

  renderManagerDurationBlock(data, activeExpert, tl);

  $("dashTotal").textContent = stats.total.toLocaleString("fa-IR");
  $("dashActive").textContent = stats.in_progress.toLocaleString("fa-IR");
  $("dashClosed").textContent = stats.closed.toLocaleString("fa-IR");

  const urgencyMgr = Object.entries(summary.urgency_breakdown || {}).map(([k, v]) =>
    `<div class="flex justify-between py-2 border-b border-slate-100 text-sm"><span>${k || "عادی"}</span><strong>${v}</strong></div>`
  ).join("");
  $("urgencyListMgr").innerHTML = urgencyMgr || '<p class="text-slate-400 text-sm">بدون داده</p>';
}

function destroyCharts() {
  Object.values(state.charts).forEach((c) => c.destroy());
  state.charts = {};
}

function renderChart(canvasId, type, labels, values, colors) {
  const ctx = $(canvasId);
  if (!ctx || !window.Chart) return;
  const isLine = type === "line";
  const dataset = isLine
    ? { data: values, borderColor: colors[0] || "#6366f1", backgroundColor: "rgba(99,102,241,.1)", fill: true, tension: 0.3, borderWidth: 2, pointRadius: 4 }
    : { data: values, backgroundColor: colors, borderRadius: type === "bar" ? 6 : 0, borderWidth: 0 };
  state.charts[canvasId] = new Chart(ctx, {
    type,
    data: { labels, datasets: [dataset] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: isLine ? false : true, position: "bottom", labels: { font: { family: "Vazir" }, padding: 14 } } },
      scales: (type === "bar" || isLine) ? { y: { beginAtZero: true }, x: { ticks: { font: { family: "Vazir" } } } } : {},
    },
  });
}

function renderTable(rows) {
  const head = $("tableHead");
  const body = $("tableBody");

  if (state.view === "requests") {
    const restCols = PURCHASE_COLUMNS.slice(1);
    head.innerHTML = `<tr><th>${PURCHASE_COLUMNS[0][1]}</th><th class="!min-w-[7rem]">صدور استعلام</th>${restCols.map(([, l]) => `<th>${l}</th>`).join("")}</tr>`;
    body.innerHTML = rows.map((row, idx) => {
      const firstCell = `<td class="font-medium">${row["شماره"] ?? "—"}</td>`;
      const canIssue = canIssueInquiry(row);
      const issueCell = canIssue
        ? `<td><button class="btn btn-primary !py-1 !px-2.5 !text-[11px] whitespace-nowrap" onclick="event.stopPropagation();openIssue(${idx})">📄 صدور استعلام</button></td>`
        : `<td>${row.inquiry_approved
          ? `<span class="badge badge-green text-[10px]">✓ ${row.local_inquiry_number || "تایید"}</span>`
          : row.has_local_inquiry
            ? `<span class="badge badge-slate text-[10px]">${row.local_inquiry_number || "استعلام"}</span>`
            : !rowBelongsToExpert(row) && isExpert()
              ? `<span class="text-xs text-slate-400">ارجاع دیگر</span>`
              : `<span class="text-xs text-slate-300">—</span>`}</td>`;
      const cells = restCols.map(([key]) => {
        let val = row[key];
        if (key === "local_inquiry_number") val = row.has_local_inquiry ? (row.local_inquiry_number || "—") : "—";
        if (key === "وضعیت فعلی خرید") return `<td>${statusBadge(val)}</td>`;
        if (key === "وضعیت") return `<td>${val ?? "—"}</td>`;
        if (key === "توضیحات") return `<td title="${val || ""}">${truncate(val)}</td>`;
        return `<td>${val ?? "—"}</td>`;
      }).join("");
      const adminEdit = isAdmin()
        ? ` oncontextmenu="openAdminContext(event,${idx})"`
        : ` oncontextmenu="openContextMenu(event,${idx})"`;
      return `<tr class="cursor-pointer hover:bg-slate-50" ondblclick="openDetail(${idx})"${adminEdit}>${firstCell}${issueCell}${cells}</tr>`;
    }).join("") || '<tr><td colspan="20" class="text-center py-12 text-slate-400">داده‌ای یافت نشد</td></tr>';
  } else if (state.view === "history") {
    head.innerHTML = "<tr><th>زمان</th><th>نوع</th><th>شناسه</th><th>عملیات</th><th>فیلد</th><th>قبلی</th><th>جدید</th><th>کاربر</th></tr>";
    body.innerHTML = rows.map((row) => `<tr>
      <td class="text-xs whitespace-nowrap">${String(row.created_at || "").slice(0, 16).replace("T", " ")}</td>
      <td class="text-xs">${row["نوع موجودیت"] || "—"}</td>
      <td class="font-medium text-xs">${row["شناسه"] || "—"}</td>
      <td class="text-xs">${row["عملیات"] || "—"}</td>
      <td class="text-xs">${row["فیلد"] || "—"}</td>
      <td class="text-xs text-slate-500 max-w-[120px] truncate" title="${row["مقدار قبلی"] || ""}">${row["مقدار قبلی"] ?? "—"}</td>
      <td class="text-xs max-w-[120px] truncate" title="${row["مقدار جدید"] || ""}">${row["مقدار جدید"] ?? "—"}</td>
      <td class="text-xs">${row["کاربر"] || "—"}</td>
    </tr>`).join("") || '<tr><td colspan="8" class="text-center py-12 text-slate-400">تاریخچه‌ای ثبت نشده</td></tr>';
  } else if (state.view === "inquiry_review" || state.view === "my_inquiries") {
    const isMine = state.view === "my_inquiries";
    head.innerHTML = isMine
      ? "<tr><th>شماره استعلام</th><th>شماره خرید</th><th>تاریخ</th><th>وضعیت</th><th>تاییدکننده</th><th>زمان تایید</th><th>دستور</th><th>عملیات</th></tr>"
      : "<tr><th>شماره استعلام</th><th>شماره خرید</th><th>کارشناس</th><th>انبار</th><th>نوع خرید</th><th>وضعیت</th><th>تایید</th><th>رد</th><th>در انتظار</th><th>عملیات</th></tr>";
    body.innerHTML = rows.map((row, idx) => {
      const st = row.manager_status || "—";
      const stCls = st.includes("تایید") ? "badge-green" : st.includes("رد") ? "badge-amber" : st.includes("انتظار") ? "badge-blue" : "badge-slate";
      const action = isMine
        ? `<button class="text-indigo-600 text-xs font-semibold hover:underline" onclick="openExpertInquiryDetail('${row["شماره استعلام"]}')">جزئیات</button>`
        : `<button class="text-indigo-600 text-xs font-semibold hover:underline" onclick="openInquiryReview('${row["شماره استعلام"]}')">بررسی استعلام</button>`;
      const adminCtx = isAdmin() ? ` oncontextmenu="openAdminContext(event,${idx})"` : "";
      if (isMine) {
        return `<tr${adminCtx}>
          <td class="font-medium">${row["شماره استعلام"]}</td>
          <td>${row["شماره درخواست خرید"]}</td>
          <td class="text-xs">${row["تاریخ استعلام"] || "—"}</td>
          <td><span class="badge ${stCls}">${st}</span></td>
          <td class="text-xs">${row.manager_reviewer || "—"}</td>
          <td class="text-xs whitespace-nowrap">${row.manager_reviewed_at || "—"}</td>
          <td class="text-xs">${row.has_orders ? `${row.order_count || "✓"} دستور` : row.pending_order_lines ? `${row.pending_order_lines} در انتظار` : "—"}</td>
          <td>${action}</td>
        </tr>`;
      }
      return `<tr${adminCtx}>
        <td class="font-medium">${row["شماره استعلام"]}</td>
        <td>${row["شماره درخواست خرید"]}</td>
        <td class="text-xs">${row["کارشناس خرید"] || row["صادر کننده سند"] || "—"}</td>
        <td class="text-xs">${row["انبار"] || "—"}</td>
        <td>${row["نوع خرید"] || "—"}</td>
        <td><span class="badge ${stCls}">${st}</span></td>
        <td class="text-green-600">${row.approved_count ?? 0}</td>
        <td class="text-amber-600">${row.rejected_count ?? 0}</td>
        <td>${row.pending_review ?? 0}</td>
        <td>${action}</td>
      </tr>`;
    }).join("") || '<tr><td colspan="10" class="text-center py-12 text-slate-400">استعلامی یافت نشد</td></tr>';
  } else {
    const keys = rows.length ? Object.keys(rows[0]).filter((k) => !k.startsWith("_")) : [];
    head.innerHTML = `<tr>${keys.map((k) => `<th>${k}</th>`).join("")}${isManager() ? "<th>عملیات</th>" : ""}</tr>`;
    body.innerHTML = rows.map((row, idx) => {
      const cells = keys.map((k) => `<td>${row[k] ?? "—"}</td>`).join("");
      const compareBtn = (state.view === "inquiries" && isManager() && row._source === "local")
        ? `<td><button class="text-indigo-600 text-xs hover:underline" onclick="openInquiryReview('${row["شماره استعلام"]}')">بررسی</button></td>`
        : (isManager() && state.view === "inquiries" ? "<td>—</td>" : "");
      const adminCtx = isAdmin() && ADMIN_ENTITY_VIEWS[state.view]
        ? ` oncontextmenu="openAdminContext(event,${idx})"`
        : "";
      return `<tr class="cursor-pointer hover:bg-slate-50" ondblclick="openDetail(${idx})"${adminCtx}>${cells}${compareBtn}</tr>`;
    }).join("") || '<tr><td colspan="20" class="text-center py-12 text-slate-400">داده‌ای یافت نشد</td></tr>';
  }

  const count = state.total || rows.length;
  $("rowCount").textContent = PAGINATED_VIEWS.has(state.view)
    ? `${rows.length.toLocaleString("fa-IR")} از ${count.toLocaleString("fa-IR")} ردیف`
    : `${rows.length.toLocaleString("fa-IR")} ردیف`;
}

function renderPurchaseReport(data) {
  const grid = $("purchaseReportGrid");
  if (!grid) return;
  const note = $("purchaseReportNote");
  if (note) note.textContent = data.data_source_note || "اولویت و نوع خرید از تغییرات پنل";
  $("purchaseReportCount").textContent = `${Number(data.total_amount_items || 0).toLocaleString("fa-IR")} قلم`;
  const finRow = (data.financial_totals && Object.values(data.financial_totals).some((v) => Number(v) > 0))
    ? `<div class="col-span-full grid grid-cols-2 lg:grid-cols-4 gap-3 mb-1">${[
      renderMoneyCard("مبلغ درخواست", data.financial_totals.requested_amount),
      renderMoneyCard("مبلغ دستور‌شده", data.financial_totals.ordered_amount, "text-violet-600"),
      renderMoneyCard("مبلغ تحویل‌شده", data.financial_totals.delivered_amount, "text-emerald-600"),
      renderMoneyCard("مانده تحویل", data.financial_totals.pending_amount, "text-amber-600"),
    ].join("")}</div>`
    : "";
  grid.innerHTML = [
    finRow,
    renderSummaryCard("کل اقلام", data.total_amount_items),
    renderBarBlock("وضعیت", data.status_breakdown),
    renderBarBlock("نوع خرید (پنل)", data.purchase_type_breakdown),
    renderBarBlock("اولویت (پنل)", data.urgency_breakdown),
  ].filter(Boolean).join("");
}

function renderExpertMyReport(data) {
  const summary = (data.summary || [])[0] || {};
  const itemCount = data.item_count ?? summary.total ?? 0;
  const kpiRow = $("expertMyKpiRow");
  const chartsRow = $("expertMyChartsRow");
  const hint = $("expertMyExcelHint");

  $("expertSummaryBlock")?.classList.add("hidden");
  $("expertDetailBlock")?.classList.add("hidden");
  $("expertFinancialRow")?.classList.add("hidden");

  if (kpiRow) {
    kpiRow.classList.remove("hidden");
    kpiRow.innerHTML = [
      renderSummaryCard("کل خریدها", summary.total ?? 0),
      renderSummaryCard("در جریان", summary.in_progress ?? 0),
      renderSummaryCard("بسته شده", summary.closed ?? 0),
      renderSummaryCard("معلق", summary.suspended ?? 0),
      renderSummaryCard("استعلام صادر", summary.inquiry_issued ?? 0),
      renderSummaryCard("دستور خرید", summary.orders ?? 0),
      renderSummaryCard("تحویل", summary.deliveries ?? 0),
      renderSummaryCard("مقدار تحویل", summary.delivered_qty ?? 0),
      renderMoneyCard("مبلغ درخواست", summary.requested_amount),
      renderMoneyCard("مبلغ دستور", summary.ordered_amount, "text-violet-600"),
      renderMoneyCard("مبلغ تحویل‌شده", summary.delivered_amount, "text-emerald-600"),
      renderMoneyCard("مانده", summary.pending_amount, "text-amber-600"),
    ].join("");
  }

  if (chartsRow) {
    chartsRow.classList.remove("hidden");
    chartsRow.innerHTML = [
      renderBarBlock("وضعیت اکسل", {
        "در جریان": summary.in_progress ?? 0,
        "بسته شده": summary.closed ?? 0,
        "معلق": summary.suspended ?? 0,
      }),
      renderBarBlock("وضعیت جریان", {
        "ثبت استعلام": summary.flow_inquiry ?? 0,
        "دستور شده": summary.flow_ordered ?? 0,
        "تحویل شده": summary.flow_delivered ?? 0,
      }),
    ].join("");
  }

  if (hint) {
    hint.classList.remove("hidden");
    hint.innerHTML = `لیست جزئیات <strong>${Number(itemCount).toLocaleString("fa-IR")}</strong> خرید در پنل نمایش داده نمی‌شود. برای مشاهده کامل از دکمه <strong>اکسل</strong> در بالای صفحه استفاده کنید.`;
  }

  const note = $("expertReportNote");
  if (note) {
    const name = window.state?.user?.expert || window.state?.user?.name || "کارشناس";
    note.textContent = `${data.data_source_note || "بر اساس داده پنل"} — ${name}`;
  }
}

function renderExpertReportItems(items, opts = {}) {
  const hideExpert = opts.hideExpertCol;
  const detHead = $("expertDetailHead");
  const detBody = $("expertDetailBody");
  if (!detHead || !detBody) return;
  detHead.innerHTML = `<tr>
    ${hideExpert ? "" : "<th>کارشناس</th>"}
    <th>شماره خرید</th><th>کالا</th><th>وضعیت اکسل</th><th>وضعیت جریان</th>
    <th>نوع خرید</th><th>اولویت</th><th>استعلام</th><th>دستور</th><th>تحویل</th>
    <th>مقدار درخواست</th><th>مقدار تحویل</th><th>درصد تحویل</th>
    <th>مبلغ درخواست</th><th>مبلغ دستور</th><th>مبلغ تحویل</th><th>مانده</th><th>تاریخ نیاز</th>
  </tr>`;
  const colSpan = hideExpert ? 17 : 18;
  detBody.innerHTML = items.map((r) => `<tr>
    ${hideExpert ? "" : `<td class="font-medium">${r["کارشناس خرید"] || "—"}</td>`}
    <td>${r["شماره خرید"] || "—"}</td>
    <td title="${r["عنوان کالا"] || ""}">${truncate(r["عنوان کالا"], 35)}</td>
    <td>${r["وضعیت اکسل"] || "—"}</td>
    <td>${statusBadge(r["وضعیت جریان"])}</td>
    <td>${r["نوع خرید"] || "—"}</td>
    <td>${r["اولویت"] || "—"}</td>
    <td>${r["شماره استعلام"] || "—"}</td>
    <td>${r["تعداد دستور"] ?? 0}</td>
    <td>${r["تعداد تحویل"] ?? 0}</td>
    <td>${r["مقدار درخواست"] ?? "—"}</td>
    <td>${r["مقدار تحویل شده"] ?? "—"}</td>
    <td>${r["درصد تحویل"] != null ? `${r["درصد تحویل"]}%` : "—"}</td>
    <td class="text-xs whitespace-nowrap">${formatMoney(r["مبلغ درخواست"])}</td>
    <td class="text-xs whitespace-nowrap">${formatMoney(r["مبلغ دستور"])}</td>
    <td class="text-xs whitespace-nowrap text-emerald-700">${formatMoney(r["مبلغ تحویل‌شده"])}</td>
    <td class="text-xs whitespace-nowrap text-amber-700">${formatMoney(r["مبلغ باقیمانده"])}</td>
    <td class="text-xs">${r["تاریخ نیاز"] || "—"}</td>
  </tr>`).join("") || `<tr><td colspan="${colSpan}" class="text-center py-8 text-slate-400">موردی ثبت نشده</td></tr>`;
  $("expertDetailCount").textContent = `${items.length.toLocaleString("fa-IR")} ردیف`;
}

function renderExpertReport(data) {
  const summary = data.summary || (Array.isArray(data) ? data : []);
  const items = data.items || [];
  const note = $("expertReportNote");
  if (note) note.textContent = data.data_source_note || "بر اساس داده پنل";

  $("expertMyKpiRow")?.classList.add("hidden");
  $("expertMyChartsRow")?.classList.add("hidden");
  $("expertMyExcelHint")?.classList.add("hidden");
  renderFinancialTotalsRow("expertFinancialRow", data.financial_totals);
  $("expertSummaryBlock")?.classList.remove("hidden");
  $("expertDetailBlock")?.classList.remove("hidden");
  const sumTitle = $("expertSummaryTitle");
  if (sumTitle) sumTitle.textContent = "خلاصه کارشناسان";
  const detTitle = $("expertDetailTitle");
  if (detTitle) detTitle.textContent = "جزئیات موارد هر کارشناس";

  const sumHead = $("expertSummaryHead");
  const sumBody = $("expertSummaryBody");
  if (sumHead && sumBody) {
    sumHead.innerHTML = `<tr>
      <th>کارشناس</th><th>کل</th><th>در جریان</th><th>بسته</th><th>معلق</th>
      <th>استعلام</th><th>دستور</th><th>تحویل</th><th>مقدار تحویل</th>
      <th>مبلغ درخواست</th><th>مبلغ دستور</th><th>مبلغ تحویل</th><th>مانده</th>
      <th>جریان: استعلام</th><th>جریان: دستور</th><th>جریان: تحویل</th>
    </tr>`;
    sumBody.innerHTML = summary.map((r) => `<tr>
      <td class="font-medium">${r["کارشناس خرید"] || "—"}</td>
      <td>${r.total ?? 0}</td>
      <td class="text-blue-600">${r.in_progress ?? 0}</td>
      <td class="text-green-600">${r.closed ?? 0}</td>
      <td class="text-amber-600">${r.suspended ?? 0}</td>
      <td>${r.inquiry_issued ?? 0}</td>
      <td>${r.orders ?? 0}</td>
      <td>${r.deliveries ?? 0}</td>
      <td>${Number(r.delivered_qty || 0).toLocaleString("fa-IR")}</td>
      <td class="text-xs whitespace-nowrap">${formatMoney(r.requested_amount)}</td>
      <td class="text-xs whitespace-nowrap">${formatMoney(r.ordered_amount)}</td>
      <td class="text-xs whitespace-nowrap text-emerald-700">${formatMoney(r.delivered_amount)}</td>
      <td class="text-xs whitespace-nowrap text-amber-700">${formatMoney(r.pending_amount)}</td>
      <td>${r.flow_inquiry ?? 0}</td>
      <td>${r.flow_ordered ?? 0}</td>
      <td>${r.flow_delivered ?? 0}</td>
    </tr>`).join("") || '<tr><td colspan="16" class="text-center py-8 text-slate-400">داده‌ای نیست</td></tr>';
  }

  renderExpertReportItems(items, { hideExpertCol: false });
}

function renderReport(view, data) {
  const head = $("tableHead");
  const body = $("tableBody");
  head.innerHTML = "";

  if (view === "report_purchase") {
    renderPurchaseReport(data);
    return;
  }

  if (view === "report_my") {
    renderExpertMyReport(data);
    return;
  }

  if (view === "report_expert") {
    renderExpertReport(data);
    return;
  }

  if (PAGINATED_VIEWS.has(view) && data.items) {
    state.data = data.items;
    state.total = data.total;
    state.totalPages = data.total_pages;
    renderTable(state.data);
    renderPagination();
    return;
  }

  renderTable(Array.isArray(data) ? data : [data]);
}

function renderSummaryCard(title, val) {
  return `<div class="chart-box"><p class="text-sm text-slate-500">${title}</p><p class="text-3xl font-bold text-indigo-600 mt-2">${Number(val).toLocaleString("fa-IR")}</p></div>`;
}

function formatMoney(val) {
  const n = Number(val);
  if (!val && val !== 0) return "—";
  if (!Number.isFinite(n) || n === 0) return "—";
  return `${Math.round(n).toLocaleString("fa-IR")} <span class="text-xs font-normal text-slate-400">ریال</span>`;
}

function renderMoneyCard(title, val, colorClass = "text-indigo-600") {
  return `<div class="chart-box border-indigo-100"><p class="text-sm text-slate-500">${title}</p><p class="text-xl font-bold ${colorClass} mt-2">${formatMoney(val)}</p></div>`;
}

function renderFinancialTotalsRow(containerId, totals) {
  const row = $(containerId);
  if (!row || !totals) return;
  const hasValue = Object.values(totals).some((v) => Number(v) > 0);
  row.classList.toggle("hidden", !hasValue);
  if (!hasValue) return;
  row.innerHTML = [
    renderMoneyCard("مبلغ درخواست / فاکتور", totals.requested_amount),
    renderMoneyCard("مبلغ دستور‌شده", totals.ordered_amount, "text-violet-600"),
    renderMoneyCard("مبلغ تحویل‌شده", totals.delivered_amount, "text-emerald-600"),
    renderMoneyCard("مانده تحویل", totals.pending_amount, "text-amber-600"),
  ].join("");
}

function renderBarBlock(title, obj) {
  const entries = Object.entries(obj || {});
  const max = Math.max(...entries.map(([, v]) => v), 1);
  const bars = entries.map(([l, v]) => `<div class="mb-2"><div class="flex justify-between text-xs mb-1"><span>${l || "—"}</span><span>${v}</span></div><div class="h-2 bg-slate-100 rounded-full"><div class="h-full bg-indigo-500 rounded-full" style="width:${v / max * 100}%"></div></div></div>`).join("");
  return `<div class="chart-box report-bar-block"><h4 class="font-bold text-sm mb-3">${title}</h4><div class="report-bar-scroll">${bars || '<p class="text-slate-400 text-sm">بدون داده</p>'}</div></div>`;
}

const ADMIN_ENTITY_VIEWS = {
  requests: { type: "purchase", idKey: "شماره", label: "درخواست خرید" },
  inquiries: { type: "inquiry", idKey: "شماره استعلام", label: "استعلام" },
  inquiry_review: { type: "inquiry", idKey: "شماره استعلام", label: "استعلام" },
  my_inquiries: { type: "inquiry", idKey: "شماره استعلام", label: "استعلام" },
  orders: { type: "order", idKey: "id", label: "دستور خرید" },
  deliveries: { type: "delivery", idKey: "id", label: "تحویل" },
};

async function openDetail(idx) {
  const row = state.data[idx];
  if (!row) return;
  const cfg = ADMIN_ENTITY_VIEWS[state.view];
  showLoading("در حال دریافت جزئیات...");
  try {
    let full = row;
    if (cfg?.idKey && row[cfg.idKey]) {
      if (cfg.type === "purchase") {
        full = await api(`/requests/detail/${row[cfg.idKey]}`);
      } else if (isAdmin()) {
        try {
          full = await api(`/admin/entities/${cfg.type}/${encodeURIComponent(row[cfg.idKey])}`);
        } catch {
          full = row;
        }
      }
    }
    state.selectedRow = full;
    renderDetailModal(full);
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

function renderDetailModal(row) {
  const ctx = typeof buildDetailEditContext === "function" ? buildDetailEditContext(row) : null;
  if (typeof setDetailEditContext === "function") setDetailEditContext(ctx);
  const skipDetail = new Set(["purchase_lines", "pre_invoices", "lines", "approval_summary"]);
  const entries = Object.entries(row || {}).filter(([k, v]) => {
    if (skipDetail.has(k) || k.startsWith("_")) return false;
    if (typeof v === "object") return false;
    if (!isAdmin()) {
      if (v == null) return false;
      const s = String(v).trim();
      return s && s !== "—" && s.toLowerCase() !== "nan" && s !== "None";
    }
    return true;
  });
  let html = entries.length && typeof renderEditableFieldRow === "function"
    ? entries.map(([k, v]) => renderEditableFieldRow(k, v, ctx)).join("")
    : entries.map(([k, v]) =>
      `<div class="grid grid-cols-3 gap-3 py-2.5 border-b border-slate-100"><span class="text-slate-500 text-sm">${k}</span><span class="col-span-2 text-sm break-words">${v ?? "—"}</span></div>`
    ).join("");
  if (row?.purchase_lines?.length) {
    html += `<div class="mt-4 pt-3 border-t border-slate-200"><h4 class="font-bold text-sm text-slate-800 mb-2">اقلام درخواست (${row.purchase_lines.length})</h4>`;
    row.purchase_lines.forEach((line, li) => {
      html += `<div class="mb-3 p-2 bg-slate-50 rounded-lg"><p class="text-[10px] text-slate-500 mb-1">ردیف ${li + 1}</p>`;
      Object.entries(line || {}).forEach(([k, v]) => {
        if (typeof v === "object" || k.startsWith("_")) return;
        if (typeof renderEditableFieldRow === "function") {
          html += renderEditableFieldRow(k, v, ctx);
        }
      });
      html += "</div>";
    });
    html += "</div>";
  }
  $("detailContent").innerHTML = html || '<p class="text-center text-slate-400 py-8">اطلاعاتی ثبت نشده</p>';
  const cfg = ADMIN_ENTITY_VIEWS[state.view];
  $("detailAdminActions")?.classList.toggle("hidden", !(isAdmin() && cfg && row?.[cfg.idKey]));
  $("detailModal").classList.remove("hidden");
}

function closeDetail() { $("detailModal").classList.add("hidden"); }

const EDIT_SKIP_FIELDS = new Set([
  "شماره", "شماره خرید", "purchase_lines", "line_count", "pre_invoices", "lines",
  "approval_summary", "has_orders", "order_count", "fully_locked", "locked",
  "partially_approved", "has_manager_decision", "manager_status", "manager_reviewer",
  "manager_reviewed_at", "pending_order_lines", "pending_row_decisions", "total_rows",
  "lines_with_orders", "preinvoice_count", "pending_review", "approved_count",
  "rejected_count", "order_id", "order_stage",
  "has_local_inquiry", "local_inquiry_number", "inquiry_approved", "وضعیت فعلی خرید",
  "updated_at", "updated_by", "created_at", "created_by", "overrides_json", "_source",
]);

function escFieldAttr(v) {
  return String(v ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function renderAdminEditFields(data) {
  const box = $("editDynamicFields");
  if (!box) return;
  const entries = Object.entries(data || {}).filter(([k, v]) => {
    if (EDIT_SKIP_FIELDS.has(k) || k.startsWith("_")) return false;
    if (v != null && typeof v === "object") return false;
    return true;
  });
  box.innerHTML = entries.map(([k, v]) => {
    const val = v == null ? "" : String(v);
    const isLong = k === "توضیحات" || k === "مشخصه فنی" || k === "شرح" || val.length > 80;
    const input = isLong
      ? `<textarea class="input !text-sm min-h-[4rem] resize-y" data-edit-field="${escFieldAttr(k)}">${escFieldAttr(val)}</textarea>`
      : `<input class="input !text-sm" data-edit-field="${escFieldAttr(k)}" value="${escFieldAttr(val)}">`;
    return `<div class="form-field ${isLong ? "sm:col-span-2" : ""}"><label class="!text-[11px]">${k}</label>${input}</div>`;
  }).join("") || '<p class="text-slate-400 text-sm">فیلدی برای ویرایش نیست</p>';
}

function showAdminEditModal(data, label, entityType, entityId) {
  state.adminEdit = { entityType, entityId, label };
  const isPurchase = entityType === "purchase";
  $("editModalTitle").textContent = `ویرایش ${label}`;
  $("editModalSubtitle").textContent = `شناسه: ${entityId}`;
  $("editPurchaseInfo")?.classList.toggle("hidden", !isPurchase);
  $("editAdminFields")?.classList.remove("hidden");
  $("editStandardFields")?.classList.add("hidden");
  if (isPurchase) {
    $("editRequestNumber").value = entityId;
    $("editDisplayNumber").textContent = entityId;
    $("editProductTitle").textContent = data["عنوان قلم خریدنی"] || data["عنوان کالا"] || "—";
    $("editProductCode").textContent = data["کد قلم خریدنی"] || "—";
    $("editRequester").textContent = data["درخواست کننده"] || "—";
    $("editPurchaseType").textContent = data["نوع خرید"] || "—";
  }
  renderAdminEditFields(data);
  $("editModal").classList.remove("hidden");
}

async function openAdminEntityEdit(entityType, entityId, previewRow, label) {
  if (!isAdmin() || !entityId) return;
  showLoading("در حال بارگذاری...");
  try {
    let full = previewRow || {};
    if (entityType === "purchase") {
      full = await api(`/requests/detail/${entityId}`);
    } else {
      full = await api(`/admin/entities/${entityType}/${encodeURIComponent(entityId)}`);
    }
    state.selectedRow = { ...previewRow, ...full };
    showAdminEditModal(state.selectedRow, label, entityType, entityId);
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

async function openEdit(idx) {
  if (!isAdmin()) return;
  const row = state.data[idx];
  const cfg = ADMIN_ENTITY_VIEWS[state.view] || ADMIN_ENTITY_VIEWS.requests;
  if (!row?.[cfg.idKey]) return;
  await openAdminEntityEdit(cfg.type, row[cfg.idKey], row, cfg.label);
}

async function openEditFromDetail() {
  const row = state.selectedRow;
  const cfg = ADMIN_ENTITY_VIEWS[state.view];
  if (!isAdmin() || !cfg || !row?.[cfg.idKey]) return;
  closeDetail();
  await openAdminEntityEdit(cfg.type, row[cfg.idKey], row, cfg.label);
}

async function openEditForPurchase(purchaseNumber, previewRow) {
  await openAdminEntityEdit("purchase", purchaseNumber, previewRow, "درخواست خرید");
}

function closeEdit() { $("editModal").classList.add("hidden"); }

async function saveEdit() {
  if (!isAdmin()) return;
  const payload = {};
  document.querySelectorAll("[data-edit-field]").forEach((el) => {
    const key = el.dataset.editField;
    if (key) payload[key] = el.value;
  });
  if (!Object.keys(payload).length) {
    toast("فیلدی برای ذخیره نیست");
    return;
  }
  const edit = state.adminEdit || { entityType: "purchase", entityId: $("editRequestNumber")?.value };
  showLoading("در حال ذخیره...");
  try {
    if (edit.entityType === "purchase") {
      await api(`/requests/${edit.entityId}`, { method: "PATCH", body: JSON.stringify(payload) });
    } else {
      await api(`/admin/entities/${edit.entityType}/${encodeURIComponent(edit.entityId)}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    }
    closeEdit();
    loadViewData();
    if (edit.entityType === "purchase") loadStats();
    toast("تغییرات ذخیره شد");
  } catch (e) { alert(e.message); }
  finally { hideLoading(); }
}

function openContextMenu(e, idx) {
  if (state.view !== "requests") return;
  const row = state.data[idx];
  if (!canIssueInquiry(row)) return;
  e.preventDefault();
  state.contextIdx = idx;
  state.selectedRow = row;
  $("ctxEdit")?.classList.add("hidden");
  $("ctxIssue")?.classList.remove("hidden");
  const m = $("contextMenu");
  m.style.left = `${e.pageX}px`;
  m.style.top = `${e.pageY}px`;
  m.classList.remove("hidden");
}

function openAdminContext(e, idx) {
  if (!isAdmin()) return;
  const cfg = ADMIN_ENTITY_VIEWS[state.view];
  if (!cfg && state.view !== "requests") return;
  e.preventDefault();
  const row = state.data[idx];
  if (!row) return;
  state.contextIdx = idx;
  state.selectedRow = row;
  $("ctxEdit")?.classList.remove("hidden");
  $("ctxIssue")?.classList.toggle("hidden", state.view !== "requests" || !canIssueInquiry(row));
  const m = $("contextMenu");
  m.style.left = `${e.pageX}px`;
  m.style.top = `${e.pageY}px`;
  m.classList.remove("hidden");
}

document.addEventListener("click", () => $("contextMenu")?.classList.add("hidden"));

function ctxAction(action) {
  $("contextMenu")?.classList.add("hidden");
  const idx = state.contextIdx;
  const row = state.data[idx] ?? state.selectedRow;
  if (!row) return;
  if (action === "edit") return openEdit(idx);
  if (action === "issue") {
    if (typeof openIssue === "function") return openIssue(idx);
    return alert("خطا در بارگذاری ماژول استعلام");
  }
}

window.openEditFromDetail = openEditFromDetail;
window.openEdit = openEdit;
window.saveEdit = saveEdit;
window.openAdminContext = openAdminContext;
window.openAdminEntityEdit = openAdminEntityEdit;
window.ADMIN_ENTITY_VIEWS = ADMIN_ENTITY_VIEWS;

function closeAction() { $("actionModal").classList.add("hidden"); }

function doSearch() {
  state.search = $("searchInput").value.trim();
  state.page = 1;
  loadViewData();
}

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden", "opacity-0");
  setTimeout(() => el.classList.add("opacity-0"), 2500);
  setTimeout(() => el.classList.add("hidden"), 3000);
}

function buildExportQuery() {
  const params = new URLSearchParams();
  params.set("view", state.view);
  if (state.search) params.set("search", state.search);
  if (state.view === "requests" && state.filter) params.set("filter", state.filter);
  const expertFilter = getExpertFilter();
  if (expertFilter) params.set("expert", expertFilter);
  if (state.advStatus) params.set("status", state.advStatus);
  if (state.advWarehouse) params.set("warehouse", state.advWarehouse);
  const usePurchaseFilters = state.view === "requests" || state.view === "report_purchase";
  if (usePurchaseFilters && state.advUrgency) params.set("urgency", state.advUrgency);
  if (usePurchaseFilters && state.advPurchaseType) params.set("purchase_type", state.advPurchaseType);
  if (state.view === "report_duration") {
    params.set("period", $("durationPeriod")?.value || "month");
  }
  return params.toString();
}

async function exportCurrentViewExcel() {
  if (!EXPORTABLE_VIEWS.has(state.view)) {
    toast("این بخش خروجی اکسل ندارد");
    return;
  }
  showLoading("در حال تولید فایل اکسل...");
  try {
    const token = getToken();
    const res = await fetch(`${API_BASE}/export/excel?${buildExportQuery()}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "خطا در تولید اکسل");
    }
    const blob = await res.blob();
    const disp = res.headers.get("Content-Disposition") || "";
    const m = disp.match(/filename="?([^";]+)"?/);
    const fname = m ? m[1] : `tadarokat-${state.view}.xlsx`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fname;
    a.click();
    URL.revokeObjectURL(url);
    toast("فایل اکسل دانلود شد");
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

function formatDbTime(iso) {
  if (!iso) return "—";
  return String(iso).slice(0, 16).replace("T", " ");
}

async function refreshDataFromDb() {
  showLoading("دریافت آخرین داده از پایگاه...");
  try {
    const res = await api("/data/refresh", { method: "POST" });
    const lastImp = res.database?.last_import_at;
    if ($("lastUpdate")) {
      $("lastUpdate").textContent = lastImp
        ? `DB ${formatDbTime(lastImp)} · ${new Date().toLocaleTimeString("fa-IR")}`
        : new Date().toLocaleTimeString("fa-IR");
    }
    const view = state.view;
    if (view === "notifications" && typeof loadNotifications === "function") await loadNotifications();
    else if (view === "warehouse_dashboard" && typeof loadWarehouseDashboard === "function") await loadWarehouseDashboard();
    else if (view === "warehouse_lookup" && typeof loadWarehouseLookup === "function") await loadWarehouseLookup();
    else if (view === "report_duration") await loadDurationReport();
    else if (view === "settings" && typeof loadSystemPaths === "function") await loadSystemPaths();
    else await loadViewData(true);
    await loadStats().catch(() => {});
    toast(res.message || "آخرین داده دریافت شد");
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

function startRefresh() {
  loadViewData();
  loadStats().catch(() => {});
  stopRefresh();
  state.refreshTimer = setInterval(() => {
    refreshDataFromDb().catch(() => {});
  }, REFRESH_MS);
}

function stopRefresh() {
  if (state.refreshTimer) clearInterval(state.refreshTimer);
}

async function loadDurationReport() {
  const period = $("durationPeriod")?.value || "month";
  showLoading("در حال بارگذاری گزارش...");
  try {
    const data = await api(`/reports/duration?period=${period}`);
    renderDurationDashboard(data);
  } catch (e) {
    $("durationSummary").innerHTML = `<p class="text-red-500 col-span-4">${e.message}</p>`;
  } finally {
    hideLoading();
  }
}

function renderDurationDashboard(data) {
  const unit = data.unit || "روز";
  const unitNote = data.unit_note || "روز تقویمی بین تاریخ‌های ثبت‌شده در پنل";
  const noteEl = $("durationUnitNote");
  if (noteEl) {
    noteEl.textContent = `واحد زمان: ${unit} — ${unitNote}`;
    noteEl.classList.remove("hidden");
  }

  const summary = data.summary || {};
  $("durationSummary").innerHTML = Object.entries(summary).map(([stage, info]) =>
    `<div class="stat-card text-center">
      <p class="text-xs text-slate-500">${stage}</p>
      <p class="text-2xl font-bold text-indigo-600 mt-1">${Number(info.avg_days || 0).toLocaleString("fa-IR")} <span class="text-sm font-normal text-slate-500">${unit}</span></p>
      <p class="text-[10px] text-slate-400 mt-1">${info.count || 0} نمونه</p>
    </div>`
  ).join("") || `<p class="text-slate-400 col-span-4">داده‌ای برای محاسبه وجود ندارد — تاریخ مراحل را در پنل ثبت کنید (واحد: ${unit})</p>`;

  const wh = data.by_warehouse || {};
  $("durationByWarehouse").innerHTML = Object.entries(wh).map(([name, stages]) => {
    const rows = Object.entries(stages).map(([st, info]) =>
      `<div class="flex justify-between text-xs py-1"><span class="text-slate-500">${st}</span><strong>${info.avg_days} روز</strong></div>`
    ).join("");
    return `<div class="mb-3 pb-2 border-b"><p class="font-bold text-xs mb-1">${name}</p>${rows}</div>`;
  }).join("") || '<p class="text-slate-400 text-sm">—</p>';

  const products = data.by_product || [];
  $("durationProductBody").innerHTML = products.map((p) => {
    const stages = Object.entries(p.stages || {}).map(([st, info]) =>
      `${st}: ${info.avg_days}روز (${info.count})`
    ).join(" · ");
    return `<tr>
      <td class="font-medium text-xs">${p.product}</td>
      <td class="text-xs text-slate-600">${stages || "—"}</td>
      <td class="text-indigo-600 font-bold">${p.total_avg}</td>
    </tr>`;
  }).join("") || '<tr><td colspan="3" class="text-center py-8 text-slate-400">داده‌ای یافت نشد</td></tr>';

  destroyCharts();
  const trend = data.trend || {};
  const labels = Object.keys(trend);
  const values = Object.values(trend);
  if (labels.length) {
    renderChart("chartDurationTrend", "line", labels, values, ["#6366f1"]);
  }
}

function startApp() {
  loadPurchaseExperts().then(() => syncDashExpertSelect()).catch(() => {});
  if (typeof loadWarehouseOptions === "function") loadWarehouseOptions().catch(() => {});
  if (isWarehouse()) {
    if (typeof loadNotifications === "function") {
      loadNotifications();
      setInterval(loadNotifications, REFRESH_MS);
    }
    setView("warehouse_dashboard");
  } else {
    setView("dashboard");
  }
  startRefresh();
}

window.loadDurationReport = loadDurationReport;

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".nav-link").forEach((el) => {
    el.addEventListener("click", () => {
      const view = el.dataset.view;
      const defaultFilter = el.dataset.defaultFilter;
      if (defaultFilter !== undefined) {
        setView(view, { filter: defaultFilter });
      } else if (view === "requests") {
        setView(view, { filter: "" });
      } else {
        setView(view);
      }
    });
  });
  document.querySelectorAll(".filter-chip").forEach((el) => {
    el.addEventListener("click", () => setFilter(el.dataset.filter));
  });
  $("searchInput")?.addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });
  $("searchInput")?.addEventListener("input", scheduleSearch);
});

window.applyAdvFilters = applyAdvFilters;
window.applyDashFilter = applyDashFilter;
window.clearSearch = clearSearch;
window.exportCurrentViewExcel = exportCurrentViewExcel;
window.refreshDataFromDb = refreshDataFromDb;