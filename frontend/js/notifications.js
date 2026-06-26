/** اعلان‌های انبار — badge، خوانده‌شدن، UI */

let notifItems = [];
let notifFilter = "all";

function isNotificationRead(item) {
  const v = item?.["خوانده شده"];
  if (v === true || v === 1) return true;
  const s = String(v ?? "").trim().toLowerCase();
  return s === "true" || s === "1" || s === "yes";
}

function notifEsc(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/"/g, "&quot;");
}

function formatNotifTime(raw) {
  if (!raw) return "—";
  const text = String(raw).slice(0, 19).replace("T", " ");
  try {
    const d = new Date(raw);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleString("fa-IR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    }
  } catch { /* ignore */ }
  return text;
}

function updateNotificationBadge(items) {
  const list = items ?? notifItems ?? [];
  const unread = list.filter((n) => !isNotificationRead(n));
  const badge = document.getElementById("badgeNotif");
  if (!badge) return;
  if (unread.length) {
    badge.textContent = unread.length > 99 ? "۹۹+" : unread.length.toLocaleString("fa-IR");
    badge.classList.remove("hidden");
  } else {
    badge.textContent = "0";
    badge.classList.add("hidden");
  }
}

function renderNotifStats(items) {
  const row = document.getElementById("notifStatsRow");
  if (!row) return;
  const total = items.length;
  const unread = items.filter((n) => !isNotificationRead(n)).length;
  const read = total - unread;
  row.innerHTML = `
    <div class="stat-card !p-3 text-center border-indigo-100">
      <p class="text-[10px] text-slate-500">کل اعلان‌ها</p>
      <p class="text-2xl font-bold text-slate-700 mt-1">${total.toLocaleString("fa-IR")}</p>
    </div>
    <div class="stat-card !p-3 text-center border-amber-100 bg-amber-50/40">
      <p class="text-[10px] text-amber-700">خوانده‌نشده</p>
      <p class="text-2xl font-bold text-amber-600 mt-1">${unread.toLocaleString("fa-IR")}</p>
    </div>
    <div class="stat-card !p-3 text-center border-emerald-100 bg-emerald-50/30">
      <p class="text-[10px] text-emerald-700">خوانده‌شده</p>
      <p class="text-2xl font-bold text-emerald-600 mt-1">${read.toLocaleString("fa-IR")}</p>
    </div>`;

  const markAll = document.getElementById("notifMarkAllBtn");
  if (markAll) markAll.classList.toggle("hidden", unread === 0);
}

function filteredNotifications() {
  if (notifFilter === "unread") {
    return notifItems.filter((n) => !isNotificationRead(n));
  }
  return notifItems;
}

function renderNotificationsList() {
  const list = document.getElementById("notificationsList");
  if (!list) return;
  const items = filteredNotifications();

  if (!items.length) {
    list.innerHTML = `<div class="notif-empty">
      <span class="notif-empty-icon">🔔</span>
      <p class="font-medium text-slate-600">${notifFilter === "unread" ? "اعلان خوانده‌نشده‌ای نیست" : "اعلانی وجود ندارد"}</p>
      <p class="text-xs text-slate-400 mt-1">با ثبت تحویل کامل (مجوز ورود + تاریخ) اعلان اینجا نمایش داده می‌شود</p>
    </div>`;
    return;
  }

  list.innerHTML = items.map((n) => {
    const read = isNotificationRead(n);
    const id = notifEsc(n.id);
    const title = notifEsc(n["عنوان"] || "اعلان تحویل");
    const message = notifEsc(n["پیام"] || "");
    const time = formatNotifTime(n.created_at);
    return `<article class="notif-card ${read ? "notif-card-read" : "notif-card-unread"}" data-notification-id="${id}">
      <div class="notif-card-icon" aria-hidden="true">📦</div>
      <div class="notif-card-body">
        <div class="flex justify-between items-start gap-2">
          <div class="min-w-0">
            <p class="notif-card-title">${title}</p>
            <p class="notif-card-msg">${message}</p>
            <p class="notif-card-time">${time}</p>
          </div>
          ${read
            ? '<span class="notif-read-pill">خوانده شده</span>'
            : `<button type="button" class="notif-read-btn" data-mark-read="${id}">خواندم</button>`}
        </div>
      </div>
    </article>`;
  }).join("");
}

function setNotifFilter(filter) {
  notifFilter = filter;
  document.querySelectorAll(".notif-filter-chip").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-notif-filter") === filter);
  });
  renderNotificationsList();
}

async function loadNotifications() {
  try {
    const res = await api("/notifications?unread=false");
    notifItems = res.items || [];
    updateNotificationBadge(notifItems);
    renderNotifStats(notifItems);
    renderNotificationsList();

    const subtitle = document.getElementById("notifSubtitle");
    const wh = window.state?.user?.warehouse;
    if (subtitle && wh) {
      subtitle.textContent = `تحویل‌های کامل انبار «${wh}»`;
    }
  } catch (e) {
    const list = document.getElementById("notificationsList");
    if (list) {
      list.innerHTML = `<div class="notif-empty"><p class="text-red-500 text-sm">${notifEsc(e.message)}</p></div>`;
    }
  }
}

async function markNotificationRead(id) {
  if (!id) return;
  try {
    await api(`/notifications/${encodeURIComponent(id)}/read`, { method: "PATCH" });
    const item = notifItems.find((n) => String(n.id) === String(id));
    if (item) item["خوانده شده"] = true;
    updateNotificationBadge(notifItems);
    renderNotifStats(notifItems);
    renderNotificationsList();
    if (typeof toast === "function") toast("اعلان خوانده شد");
  } catch (e) {
    if (typeof toast === "function") toast(e.message);
  }
}

async function markAllNotificationsRead() {
  try {
    const res = await api("/notifications/read-all", { method: "PATCH" });
    notifItems.forEach((n) => { n["خوانده شده"] = true; });
    updateNotificationBadge(notifItems);
    renderNotifStats(notifItems);
    renderNotificationsList();
    if (typeof toast === "function") toast(`${(res.marked ?? 0).toLocaleString("fa-IR")} اعلان خوانده شد`);
  } catch (e) {
    if (typeof toast === "function") toast(e.message);
  }
}

function bindNotificationUI() {
  document.getElementById("notifRefreshBtn")?.addEventListener("click", () => loadNotifications());
  document.getElementById("notifMarkAllBtn")?.addEventListener("click", () => markAllNotificationsRead());

  document.getElementById("notifFilterBar")?.addEventListener("click", (e) => {
    const chip = e.target.closest("[data-notif-filter]");
    if (!chip) return;
    setNotifFilter(chip.getAttribute("data-notif-filter") || "all");
  });

  document.getElementById("notificationsList")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-mark-read]");
    if (!btn) return;
    e.preventDefault();
    markNotificationRead(btn.getAttribute("data-mark-read"));
  });
}

document.addEventListener("DOMContentLoaded", bindNotificationUI);

window.loadNotifications = loadNotifications;
window.markNotificationRead = markNotificationRead;
window.markAllNotificationsRead = markAllNotificationsRead;
window.updateNotificationBadge = updateNotificationBadge;