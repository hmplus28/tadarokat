let pathsCache = {};
let pathsOverview = {};

function escPath(v) {
  return String(v ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

function statusBadge(exists, kind) {
  if (exists) return `<span class="badge badge-green text-[10px]">موجود</span>`;
  if (kind === "dir") return `<span class="badge badge-amber text-[10px]">ایجاد می‌شود</span>`;
  return `<span class="badge badge-slate text-[10px]">یافت نشد</span>`;
}

function renderAdminStatusCards(runtime) {
  const el = document.getElementById("adminStatusCards");
  if (!el) return;
  const locked = runtime?.locked;
  const db = runtime?.database || {};
  const src = runtime?.storage?.source_excel || {};
  const cards = [
    { label: "وضعیت سیستم", value: locked ? "قفل swap" : "فعال", hint: locked ? "import در جریان" : "آماده", cls: locked ? "text-amber-600" : "text-green-600" },
    { label: "اقلام خرید", value: Number(db.purchase_count || 0).toLocaleString("fa-IR"), hint: "در پایگاه فعال", cls: "text-indigo-600" },
    { label: "نسخه DB", value: db.db_version || "—", hint: db.last_import_at ? `آخرین import: ${String(db.last_import_at).slice(0, 16).replace("T", " ")}` : "—", cls: "text-slate-700" },
    { label: "آخرین Export", value: db.last_export_at ? String(db.last_export_at).slice(0, 16).replace("T", " ") : "—", hint: "تبدیل DB به output.xlsx", cls: "text-violet-600" },
    { label: "اکسل ورودی", value: src.size_mb ? `${src.size_mb} MB` : "—", hint: src.exists ? "فایل موجود" : "فایل نیست", cls: src.exists ? "text-green-600" : "text-amber-600" },
  ];
  el.innerHTML = cards.map((c) =>
    `<div class="stat-card !p-3 border-slate-100">
      <p class="text-[10px] text-slate-500">${c.label}</p>
      <p class="text-xl font-bold mt-1 ${c.cls}">${c.value}</p>
      <p class="text-[9px] text-slate-400 mt-0.5 truncate" title="${c.hint}">${c.hint}</p>
    </div>`
  ).join("");
}

function renderFileStatusList(groups) {
  const el = document.getElementById("settingsFileStatus");
  if (!el) return;
  el.innerHTML = (groups || []).map((g) => {
    const rows = (g.items || []).map((it) =>
      `<div class="flex flex-wrap items-center gap-2 py-2 border-b border-slate-50 last:border-0">
        <span class="w-40 shrink-0 text-slate-600">${it.label}</span>
        <code dir="ltr" class="flex-1 min-w-0 text-[10px] text-slate-500 truncate bg-slate-50 px-2 py-1 rounded">${escPath(it.path)}</code>
        ${statusBadge(it.exists, it.kind)}
        <span class="text-slate-400 w-16 text-left">${it.size_human || "—"}</span>
      </div>`
    ).join("");
    return `<div class="mb-3"><p class="font-bold text-slate-700 text-xs mb-1">${g.title}</p>${rows}</div>`;
  }).join("") || '<p class="text-slate-400">بدون داده</p>';
}

function renderSettingsForm(groups, paths) {
  const form = document.getElementById("settingsForm");
  if (!form) return;
  form.innerHTML = (groups || []).map((g) => {
    const fields = (g.items || []).map((it) => {
      const val = paths[it.key] || it.path || "";
      return `<div>
        <div class="flex items-center justify-between gap-2 mb-0.5">
          <label class="text-xs text-slate-600" for="path_${it.key}">${it.label}</label>
          ${statusBadge(it.exists, it.kind)}
        </div>
        <input id="path_${it.key}" class="input mt-0.5 text-xs font-mono" dir="ltr" value="${escPath(val)}">
        ${it.modified_at ? `<p class="text-[9px] text-slate-400 mt-0.5">آخرین تغییر: ${it.modified_at.slice(0, 16).replace("T", " ")} · ${it.size_human}</p>` : ""}
      </div>`;
    }).join("");
    return `<div class="border border-slate-100 rounded-xl p-4 bg-slate-50/50">
      <h4 class="font-bold text-sm text-slate-800">${g.title}</h4>
      <p class="text-[10px] text-slate-500 mb-3">${g.description || ""}</p>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">${fields}</div>
    </div>`;
  }).join("");
}

function renderImportSchedule(sched) {
  const enabled = document.getElementById("importScheduleEnabled");
  const hour = document.getElementById("importScheduleHour");
  const minute = document.getElementById("importScheduleMinute");
  const status = document.getElementById("importScheduleStatus");
  if (!sched) return;
  if (enabled) enabled.checked = !!sched.enabled;
  if (hour) hour.value = String(sched.hour ?? 8);
  if (minute) minute.value = String(sched.minute ?? 0);
  if (status) {
    const last = sched.last_run_at ? String(sched.last_run_at).slice(0, 16).replace("T", " ") : "—";
    const runner = sched.runner_host || "تعیین نشده";
    const mine = sched.this_machine_is_runner
      ? '<span class="text-green-600 font-medium">این سیستم</span>'
      : '<span class="text-amber-600">سیستم دیگر</span>';
    status.innerHTML = `
      <p>اجراکننده: <code dir="ltr">${runner}</code> — ${mine}</p>
      <p class="mt-1">آخرین import: ${last} · ${sched.last_run_status || "—"}</p>
      <p class="mt-1 text-slate-500">زمان‌بندی: هر روز ساعت ${String(sched.hour).padStart(2, "0")}:${String(sched.minute).padStart(2, "0")} (${sched.timezone || "Asia/Tehran"})</p>`;
  }
}

async function loadImportSchedule() {
  try {
    const sched = await api("/system/import-schedule");
    renderImportSchedule(sched);
  } catch {
    /* optional */
  }
}

function renderExcelImportStatus(runtime) {
  const el = document.getElementById("excelImportStatus");
  if (!el) return;
  const src = runtime?.storage?.source_excel || {};
  const db = runtime?.database || {};
  const last = db.last_import_at ? String(db.last_import_at).slice(0, 16).replace("T", " ") : "—";
  const excelOk = src.exists
    ? '<span class="text-green-600">موجود</span>'
    : '<span class="text-red-600">یافت نشد — ابتدا input.xlsx را در share بگذارید</span>';
  el.innerHTML = `
    <p>فایل ورودی: <code dir="ltr" class="text-[10px]">${src.path || "—"}</code> — ${excelOk}</p>
    <p class="mt-1">آخرین import به دیتابیس: <strong>${last}</strong> · نسخه DB: ${db.db_version || "—"}</p>`;
}

async function runExcelToDatabase() {
  if (!confirm("اکسل input.xlsx الان به دیتابیس مشترک import شود؟\n(چند دقیقه طول می‌کشد)")) return;
  showLoading("در حال import اکسل به دیتابیس...");
  try {
    await api("/system/import-excel", { method: "POST" });
    toast("اکسل با موفقیت به دیتابیس import شد");
    if (typeof refreshDataFromDb === "function") await refreshDataFromDb();
    else await loadSystemPaths();
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

async function loadSystemPaths() {
  const form = document.getElementById("settingsForm");
  if (!form) return;
  showLoading("در حال بارگذاری پنل سیستم...");
  try {
    const res = await api("/system/paths");
    pathsOverview = res;
    pathsCache = res.paths || {};
    renderAdminStatusCards(res.runtime);
    renderExcelImportStatus(res.runtime);
    renderSettingsForm(res.groups, pathsCache);
    renderFileStatusList(res.groups);
    await loadImportSchedule();
    const meta = document.getElementById("settingsMeta");
    if (meta && pathsCache.updated_at) {
      meta.textContent = `آخرین ذخیره: ${pathsCache.updated_at} · توسط ${pathsCache.updated_by || "—"}`;
    }
  } catch (e) {
    form.innerHTML = `<p class="text-red-500">${e.message}</p>`;
  } finally {
    hideLoading();
  }
}

async function saveImportSchedule() {
  showLoading("در حال ذخیره...");
  try {
    const sched = await api("/system/import-schedule", {
      method: "PATCH",
      body: JSON.stringify({
        enabled: document.getElementById("importScheduleEnabled")?.checked ?? true,
        hour: parseInt(document.getElementById("importScheduleHour")?.value || "8", 10),
        minute: parseInt(document.getElementById("importScheduleMinute")?.value || "0", 10),
      }),
    });
    renderImportSchedule(sched);
    toast("زمان‌بندی import ذخیره شد");
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

async function setThisMachineAsImportRunner() {
  showLoading("در حال ثبت...");
  try {
    const sched = await api("/system/import-schedule", {
      method: "PATCH",
      body: JSON.stringify({ set_this_machine_runner: true }),
    });
    renderImportSchedule(sched);
    toast("این سیستم به عنوان اجراکننده import ثبت شد");
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}



async function applyShareDefaults() {
  const share = document.getElementById("path_shared_data_dir")?.value?.trim();
  if (!share) {
    toast("ابتدا مسیر پوشه Share را وارد کنید");
    return;
  }
  showLoading("در حال پیش‌فرض‌گذاری...");
  try {
    const res = await api(`/system/paths/defaults?share_dir=${encodeURIComponent(share)}`);
    const defaults = res.paths || {};
    Object.entries(defaults).forEach(([key, val]) => {
      const el = document.getElementById(`path_${key}`);
      if (el) el.value = val;
    });
    toast("مسیرهای فرعی از Share پر شد — ذخیره را بزنید");
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

async function saveSystemPaths() {
  const errEl = document.getElementById("settingsError");
  errEl?.classList.add("hidden");
  const payload = {};
  document.querySelectorAll("[id^='path_']").forEach((el) => {
    const key = el.id.replace(/^path_/, "");
    if (el.value?.trim()) payload[key] = el.value.trim();
  });
  showLoading("در حال ذخیره...");
  try {
    await api("/system/paths", { method: "PATCH", body: JSON.stringify(payload) });
    toast("مسیرها ذخیره و اعمال شد");
    await loadSystemPaths();
    if (typeof loadViewData === "function") loadViewData(true);
    if (typeof loadStats === "function") loadStats();
  } catch (e) {
    if (errEl) {
      errEl.textContent = e.message;
      errEl.classList.remove("hidden");
    }
  } finally {
    hideLoading();
  }
}

async function runSystemImport() {
  return runExcelToDatabase();
}

async function runSystemExport() {
  showLoading("در حال export...");
  try {
    const res = await api("/system/export-excel", { method: "POST" });
    toast(`خروجی: ${res.path || "ذخیره شد"}`);
    await loadSystemPaths();
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

function openChangePasswordModal() {
  document.getElementById("cpCurrent").value = "";
  document.getElementById("cpNew").value = "";
  document.getElementById("cpConfirm").value = "";
  document.getElementById("changePasswordError")?.classList.add("hidden");
  document.getElementById("changePasswordModal")?.classList.remove("hidden");
}

function closeChangePasswordModal() {
  document.getElementById("changePasswordModal")?.classList.add("hidden");
}

async function submitChangePassword() {
  const errEl = document.getElementById("changePasswordError");
  const current = document.getElementById("cpCurrent")?.value || "";
  const newPass = document.getElementById("cpNew")?.value || "";
  const confirm = document.getElementById("cpConfirm")?.value || "";
  if (!current || !newPass) {
    errEl.textContent = "رمز فعلی و جدید الزامی است";
    errEl.classList.remove("hidden");
    return;
  }
  if (newPass.length < 6) {
    errEl.textContent = "رمز جدید حداقل ۶ کاراکتر";
    errEl.classList.remove("hidden");
    return;
  }
  if (newPass !== confirm) {
    errEl.textContent = "تکرار رمز با رمز جدید یکسان نیست";
    errEl.classList.remove("hidden");
    return;
  }
  showLoading("در حال ذخیره...");
  try {
    await api("/auth/change-password", {
      method: "PATCH",
      body: JSON.stringify({ current_password: current, new_password: newPass }),
    });
    closeChangePasswordModal();
    toast("رمز عبور تغییر کرد");
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove("hidden");
  } finally {
    hideLoading();
  }
}

async function downloadAdminBlob(path, defaultName) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "خطا در دانلود");
  }
  const blob = await res.blob();
  const disp = res.headers.get("Content-Disposition") || "";
  const m = disp.match(/filename="?([^";]+)"?/);
  const fname = m ? m[1] : defaultName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fname;
  a.click();
  URL.revokeObjectURL(url);
}

async function downloadWorkflowTemplate() {
  showLoading("در حال تولید تمپلیت...");
  try {
    await downloadAdminBlob("/admin/workflow-import/template", "workflow-import-template.xlsx");
    toast("تمپلیت اکسل دانلود شد");
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

async function downloadWorkflowGuide() {
  showLoading("در حال تولید راهنما...");
  try {
    await downloadAdminBlob("/admin/workflow-import/guide", "workflow-import-guide.docx");
    toast("راهنمای Word دانلود شد");
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

async function runWorkflowImport() {
  const input = document.getElementById("workflowImportFile");
  const file = input?.files?.[0];
  if (!file) {
    toast("ابتدا فایل اکسل را انتخاب کنید");
    return;
  }
  if (!confirm(`فایل «${file.name}» وارد شود؟ ردیف‌های موجود به‌روز و ردیف‌های جدید اضافه می‌شوند.`)) return;
  showLoading("در حال import...");
  const resultEl = document.getElementById("workflowImportResult");
  try {
    const fd = new FormData();
    fd.append("file", file);
    const token = getToken();
    const res = await fetch(`${API_BASE}/admin/workflow-import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "خطا در import");
    }
    const data = await res.json();
    if (resultEl) {
      const sheetLines = Object.entries(data.sheets || {}).map(
        ([name, s]) => `${name}: ${s.inserted} جدید، ${s.updated} به‌روز`
      ).join(" · ");
      resultEl.textContent = `${data.message || "انجام شد"}${sheetLines ? ` — ${sheetLines}` : ""}`;
      resultEl.classList.remove("hidden");
    }
    toast(data.message || "Import انجام شد");
    input.value = "";
    if (typeof loadViewData === "function") loadViewData(true);
    if (typeof loadStats === "function") loadStats();
  } catch (e) {
    toast(e.message);
    if (resultEl) {
      resultEl.textContent = e.message;
      resultEl.classList.remove("hidden");
    }
  } finally {
    hideLoading();
  }
}

window.loadSystemPaths = loadSystemPaths;
window.saveSystemPaths = saveSystemPaths;
window.applyShareDefaults = applyShareDefaults;
window.runSystemImport = runSystemImport;
window.runSystemExport = runSystemExport;
window.saveImportSchedule = saveImportSchedule;
window.setThisMachineAsImportRunner = setThisMachineAsImportRunner;
window.runExcelToDatabase = runExcelToDatabase;
window.openChangePasswordModal = openChangePasswordModal;
window.closeChangePasswordModal = closeChangePasswordModal;
window.submitChangePassword = submitChangePassword;
window.downloadWorkflowTemplate = downloadWorkflowTemplate;
window.downloadWorkflowGuide = downloadWorkflowGuide;
window.runWorkflowImport = runWorkflowImport;