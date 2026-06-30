/** کارشناسان فعال از سرور — با اضافه/حذف کاربر به‌روز می‌شود */
const expertCache = { active: [], legacy: [], items: [], loaded: false };

async function loadPurchaseExperts(force = false) {
  if (expertCache.loaded && !force) return expertCache;
  try {
    const res = await api("/experts");
    expertCache.active = res.active || res.items || [];
    expertCache.legacy = res.legacy || [];
    expertCache.items = res.items || expertCache.active;
    expertCache.loaded = true;
  } catch {
    expertCache.active = [];
    expertCache.legacy = [];
    expertCache.items = [];
  }
  populateExpertSelects();
  return expertCache;
}

function defaultExpertName(fallback = "") {
  const fb = String(fallback || "").trim();
  if (fb && expertCache.active.includes(fb)) return fb;
  return expertCache.active[0] || fb || "";
}

function expertOptionsHtml(selected = "", extraNames = []) {
  const selectedName = String(selected || "").trim();
  const extras = (extraNames || []).map((n) => String(n || "").trim()).filter(Boolean);
  const activeSet = new Set(expertCache.active);
  const names = [...expertCache.active];
  for (const n of [...extras, selectedName]) {
    if (n && !names.includes(n)) names.push(n);
  }
  if (!names.length) return '<option value="">— کارشناسی تعریف نشده —</option>';
  return names.map((name) => {
    const inactive = !activeSet.has(name);
    const label = inactive ? `${name} (غیرفعال)` : name;
    const sel = name === selectedName ? " selected" : "";
    return `<option value="${name.replace(/"/g, "&quot;")}"${sel}${inactive ? ' class="text-slate-400"' : ""}>${label}</option>`;
  }).join("");
}

function populateExpertSelects() {
  const expertOpts = `<option value="">همه کارشناسان</option>${expertCache.active.map((n) =>
    `<option value="${n.replace(/"/g, "&quot;")}">${n}</option>`).join("")}`;
  const filter = document.getElementById("filterExpert");
  if (filter) {
    const cur = filter.value;
    filter.innerHTML = expertOpts;
    if (cur && [...filter.options].some((o) => o.value === cur)) filter.value = cur;
  }
  const dashFilter = document.getElementById("dashFilterExpert");
  if (dashFilter) {
    const cur = dashFilter.value;
    dashFilter.innerHTML = expertOpts;
    if (cur && [...dashFilter.options].some((o) => o.value === cur)) dashFilter.value = cur;
  }
  const editExpert = document.getElementById("editExpert");
  if (editExpert) {
    const cur = editExpert.value;
    editExpert.innerHTML = expertCache.active.map((n) =>
      `<option value="${n.replace(/"/g, "&quot;")}">${n}</option>`).join("") || "<option>—</option>";
    if (cur && [...editExpert.options].some((o) => o.value === cur)) editExpert.value = cur;
  }
  const fuExpert = document.getElementById("fuExpert");
  if (fuExpert && expertCache.active.length) {
    fuExpert.setAttribute("list", "expertNameList");
    let dl = document.getElementById("expertNameList");
    if (!dl) {
      dl = document.createElement("datalist");
      dl.id = "expertNameList";
      document.body.appendChild(dl);
    }
    dl.innerHTML = expertCache.active.map((n) => `<option value="${n.replace(/"/g, "&quot;")}">`).join("");
  }
}

window.loadPurchaseExperts = loadPurchaseExperts;
window.expertOptionsHtml = expertOptionsHtml;
window.defaultExpertName = defaultExpertName;
window.populateExpertSelects = populateExpertSelects;