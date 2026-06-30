const issueState = { preInvoices: [], purchaseData: null, headerConfirmed: false, _activePurchase: "" };
const ISSUE_DRAFT_PREFIX = "tadarokat_issue_draft_";
const ISSUE_HEADER_IDS = [
  "issueInquiryNumber", "issuePurchaseNumber", "issuePurchaseType", "issueDeadline",
  "issueUnit", "issueUrgency", "issueWarehouse", "issueRequester",
  "issueMaterialRequestNumber", "issueMaterialRequestDate", "issueReceiptDate",
  "issueReason", "issueRisk",
];
let issueDraftTimer = null;
let issueDraftBound = false;

function issueDraftStorageKey(purchaseNumber) {
  const user = window.state?.user?.username || "anon";
  const pn = String(purchaseNumber || issueState._activePurchase || $("issuePurchaseNumber")?.value?.trim() || "").trim();
  return `${ISSUE_DRAFT_PREFIX}${user}_${pn}`;
}

function collectIssueHeaderFields() {
  const out = {};
  ISSUE_HEADER_IDS.forEach((id) => {
    const el = $(id);
    out[id] = el?.value ?? "";
  });
  return out;
}

function applyIssueHeaderFields(header = {}) {
  ISSUE_HEADER_IDS.forEach((id) => {
    const el = $(id);
    if (el && header[id] != null) el.value = header[id];
  });
}

function scheduleIssueDraftSave() {
  clearTimeout(issueDraftTimer);
  issueDraftTimer = setTimeout(saveIssueDraft, 450);
}

function saveIssueDraft() {
  const pn = $("issuePurchaseNumber")?.value?.trim();
  if (!pn || !$("issueModal") || $("issueModal").classList.contains("hidden")) return;
  try {
    const draft = {
      purchase_number: pn,
      saved_at: Date.now(),
      headerConfirmed: issueState.headerConfirmed,
      header: collectIssueHeaderFields(),
      preInvoices: issueState.preInvoices,
    };
    localStorage.setItem(issueDraftStorageKey(pn), JSON.stringify(draft));
  } catch { /* quota */ }
}

function loadIssueDraft(purchaseNumber) {
  try {
    const raw = localStorage.getItem(issueDraftStorageKey(purchaseNumber));
    if (!raw) return null;
    const draft = JSON.parse(raw);
    if (!draft?.purchase_number) return null;
    return draft;
  } catch {
    return null;
  }
}

function clearIssueDraft(purchaseNumber) {
  try {
    localStorage.removeItem(issueDraftStorageKey(purchaseNumber));
  } catch { /* */ }
}

function normalizePreInvoiceCard(card) {
  if (!card) return card;
  if (card.vat_enabled === undefined || card.vat_enabled === null) {
    const t = String(card.invoice_type || "").trim();
    card.vat_enabled = t === "رسمی" || !!card["اعمال مالیات ده درصد"];
  }
  card.invoice_type = card.vat_enabled ? "رسمی" : "کد ملی";
  return card;
}

function restoreIssueFromDraft(draft) {
  if (!draft) return;
  applyIssueHeaderFields(draft.header || {});
  issueState.preInvoices = (Array.isArray(draft.preInvoices) ? draft.preInvoices : []).map(normalizePreInvoiceCard);
  issueState.headerConfirmed = !!draft.headerConfirmed;
  issueState._activePurchase = draft.purchase_number || "";
  showIssueStep(issueState.headerConfirmed ? 2 : 1);
  renderPreInvoiceCards();
}

function resetIssueFormFromRow(row) {
  issueState.preInvoices = [];
  issueState.headerConfirmed = false;
  issueState._activePurchase = String(row["شماره"] ?? "");
  $("issueError")?.classList.add("hidden");
  $("issuePurchaseNumber").value = row["شماره"] ?? "";
  $("issuePurchaseType").value = row["نوع خرید"] || "استعلامی";
  $("issueDeadline").value = row["مهلت استعلام"] ?? "";
  $("issueUnit").value = row["واحد/رمز تامین"] || "تدارکات داخلی";
  $("issueUrgency").value = row["رمز فوریت"] || "";
  $("issueWarehouse").value = "";
  $("issueRequester").value = row["درخواست کننده"] || "";
  $("issueMaterialRequestNumber").value = row["شماره مبنا"] || "";
  $("issueMaterialRequestDate").value = row["تاریخ درخواست کالا"] || "";
  $("issueReceiptDate").value = "";
  $("issueReason").value = "";
  $("issueRisk").value = "";
  $("preInvoiceCards").innerHTML = "";
  showIssueStep(1);
}

function bindIssueDraftAutosave() {
  if (issueDraftBound) return;
  issueDraftBound = true;
  ISSUE_HEADER_IDS.forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.addEventListener("input", scheduleIssueDraftSave);
    el.addEventListener("change", scheduleIssueDraftSave);
  });
}

function defaultLineFromPurchase(p, rowNum = 1, lineRow = null) {
  const src = lineRow || p || {};
  return {
    row_number: rowNum,
    product_title: src["عنوان قلم خریدنی"] || src["عنوان کالا"] || p["عنوان کالا"] || "",
    unit: src["واحد سنجش قلم خریدنی"] || src["واحد"] || p["واحد"] || p["واحد سنجش قلم خریدنی"] || "",
    unit_price: 0,
    quantity: src["مقدار"] ?? p["مقدار"] ?? 1,
    notes: src["توضیحات"] || p["توضیحات"] || "",
  };
}

function defaultLinesFromPurchase(p) {
  const plines = p?.purchase_lines || p?.["purchase_lines"] || [];
  if (plines.length > 1) {
    return plines.map((row, idx) => defaultLineFromPurchase(p, row.ردیف ?? idx + 1, row));
  }
  return [defaultLineFromPurchase(p, 1)];
}

function initJalaliPickers() {
  if (!window.jalaliDatepicker) return;
  try {
    jalaliDatepicker.startWatch({ time: false, separatorChars: { date: "/" }, zIndex: 9999 });
  } catch { /* already started */ }
}

function loadCityList() {
  api("/cities/search?q=").then((res) => {
    const dl = $("cityList");
    if (dl) dl.innerHTML = (res.items || []).map((c) => `<option value="${c}">`).join("");
  }).catch(() => {});
}

function fillIssueHeaderFromPurchase(p) {
  if (!p) return;
  $("issuePurchaseType").value = p["نوع خرید"] || $("issuePurchaseType").value;
  $("issueDeadline").value = p["مهلت استعلام"] || $("issueDeadline").value;
  $("issueUnit").value = p["واحد/رمز تامین"] || $("issueUnit").value || "تدارکات داخلی";
  const urgency = p["رمز فوریت"] || "";
  const urgSel = $("issueUrgency");
  if (urgency && ![...urgSel.options].some((o) => o.value === urgency)) {
    urgSel.add(new Option(urgency, urgency));
  }
  urgSel.value = urgency || "";
  $("issueRequester").value = p["درخواست کننده"] || $("issueRequester").value;
  $("issueMaterialRequestNumber").value = p["شماره مبنا"] || $("issueMaterialRequestNumber").value;
  $("issueMaterialRequestDate").value = p["تاریخ درخواست کالا"] || $("issueMaterialRequestDate").value;
  $("issueReceiptDate").value = p["تاریخ دریافت"] || $("issueReceiptDate").value;
}

function validateIssueHeader() {
  const checks = [
    ["issuePurchaseNumber", "شماره خرید"],
    ["issuePurchaseType", "نوع خرید"],
    ["issueDeadline", "مهلت استعلام"],
    ["issueUnit", "واحد تامین"],
    ["issueUrgency", "رمز فوریت"],
    ["issueWarehouse", "انبار"],
    ["issueRequester", "درخواست‌دهنده"],
    ["issueMaterialRequestNumber", "شماره درخواست کالا"],
    ["issueMaterialRequestDate", "تاریخ درخواست کالا"],
    ["issueReceiptDate", "تاریخ دریافت"],
  ];
  for (const [id, label] of checks) {
    const el = $(id);
    if (!el?.value?.trim()) return `${label} الزامی است`;
  }
  return null;
}

function showIssueStep(step) {
  issueState.headerConfirmed = step === 2;
  $("issueHeaderSection")?.classList.toggle("hidden", step === 2);
  $("issuePreinvoiceSection")?.classList.toggle("hidden", step !== 2);
  $("issuePrintBtn")?.classList.toggle("hidden", step !== 2);
  $("issueExportBtn")?.classList.toggle("hidden", step !== 2);
}

function confirmIssueHeader() {
  const err = validateIssueHeader();
  const errEl = $("issueError");
  if (err) {
    errEl.textContent = err;
    errEl.classList.remove("hidden");
    return;
  }
  errEl?.classList.add("hidden");
  showIssueStep(2);
  if (!issueState.preInvoices.length) addPreInvoiceCard();
  scheduleIssueDraftSave();
}

function editIssueHeader() {
  showIssueStep(1);
  scheduleIssueDraftSave();
}

async function openIssue(idx) {
  const row = window.state.data[idx];
  if (!row) return;
  window.state.selectedRow = row;
  issueState.purchaseData = null;
  const purchaseNum = String(row["شماره"] ?? "");
  const draft = loadIssueDraft(purchaseNum);

  if (draft) {
    restoreIssueFromDraft(draft);
  } else {
    resetIssueFormFromRow(row);
  }

  try {
    const lookup = await api(`/inquiries/lookup/${purchaseNum}`);
    issueState.purchaseData = lookup;
    if (!draft) fillIssueHeaderFromPurchase(lookup);
    if (draft?.header?.issueInquiryNumber) {
      $("issueInquiryNumber").value = draft.header.issueInquiryNumber;
    } else {
      const next = await api("/inquiries/next-number");
      $("issueInquiryNumber").value = next.next_number;
    }
  } catch (e) {
    $("issueError").textContent = e.message;
    $("issueError").classList.remove("hidden");
  }

  $("issueModal").classList.remove("hidden");
  bindIssueDraftAutosave();
  loadCityList();
  setTimeout(initJalaliPickers, 50);
  if (draft?.preInvoices?.length) {
    if (typeof toast === "function") toast("پیش‌نویس ذخیره‌شده بازیابی شد — می‌توانید ادامه دهید");
  }
  scheduleIssueDraftSave();
}

function closeIssue(skipSave = false) {
  if (!skipSave) saveIssueDraft();
  $("issueModal").classList.add("hidden");
}

async function lookupPurchaseForIssue() {
  const num = $("issuePurchaseNumber").value.trim();
  if (!num) return;
  showLoading("در حال دریافت اطلاعات خرید...");
  try {
    issueState.purchaseData = await api(`/inquiries/lookup/${num}`);
    fillIssueHeaderFromPurchase(issueState.purchaseData);
    toast("اطلاعات خرید بارگذاری شد");
    if (issueState.headerConfirmed) {
      if (!issueState.preInvoices.length) addPreInvoiceCard();
      else refreshPreInvoiceLines();
    }
  } catch (e) { alert(e.message); }
  finally { hideLoading(); }
}

function addPreInvoiceCard() {
  if (!issueState.headerConfirmed) {
    const err = validateIssueHeader();
    if (err) {
      $("issueError").textContent = err;
      $("issueError").classList.remove("hidden");
      return;
    }
  }
  const id = Date.now() + Math.random();
  const p = issueState.purchaseData || {};
  const today = new Date().toLocaleDateString("fa-IR");
  const card = {
    id,
    contractor: "",
    preinvoice_number: `PF-${Math.floor(Math.random() * 9000 + 1000)}`,
    date: today,
    invoice_type: "کد ملی",
    vat_enabled: false,
    discount: 0,
    delivery_time: "",
    description: "",
    notes: "",
    contractor_city: "",
    selected: false,
    lines: defaultLinesFromPurchase(p),
  };
  issueState.preInvoices.push(card);
  renderPreInvoiceCards();
  scheduleIssueDraftSave();
}

function removePreInvoiceCard(id) {
  issueState.preInvoices = issueState.preInvoices.filter((c) => c.id !== id);
  renderPreInvoiceCards();
  scheduleIssueDraftSave();
}

function refreshPreInvoiceLines() {
  const p = issueState.purchaseData;
  if (!p) return;
  const plines = p.purchase_lines || p["purchase_lines"] || [];
  issueState.preInvoices.forEach((card) => {
    card.lines.forEach((line, idx) => {
      const src = plines[idx] || p;
      if (!line.product_title) {
        line.product_title = src["عنوان قلم خریدنی"] || src["عنوان کالا"] || p["عنوان کالا"] || "";
      }
      if (!line.unit) line.unit = src["واحد سنجش قلم خریدنی"] || src["واحد"] || p["واحد"] || "";
      if (!line.quantity) line.quantity = src["مقدار"] ?? p["مقدار"] ?? 1;
      if (!line.notes) line.notes = src["توضیحات"] || p["توضیحات"] || "";
      line.row_number = src.ردیف ?? idx + 1;
    });
  });
  renderPreInvoiceCards();
}

function addLineToCard(cardId) {
  const card = issueState.preInvoices.find((c) => c.id === cardId);
  if (!card) return;
  const p = issueState.purchaseData || {};
  const nextRow = card.lines.length + 1;
  const plines = p.purchase_lines || p["purchase_lines"] || [];
  const lineRow = plines[nextRow - 1] || null;
  card.lines.push(defaultLineFromPurchase(p, lineRow?.ردیف ?? nextRow, lineRow));
  renderPreInvoiceCards();
  scheduleIssueDraftSave();
}

function removeLine(cardId, lineIdx) {
  const card = issueState.preInvoices.find((c) => c.id === cardId);
  if (!card || card.lines.length <= 1) return;
  card.lines.splice(lineIdx, 1);
  card.lines.forEach((line, idx) => { line.row_number = idx + 1; });
  renderPreInvoiceCards();
  scheduleIssueDraftSave();
}

function calcLineTotal(line) {
  return (parseFloat(line.unit_price) || 0) * (parseFloat(line.quantity) || 0);
}

function calcCardSubtotal(card) {
  return card.lines.reduce((s, l) => s + calcLineTotal(l), 0);
}

function cardInvoiceType(card) {
  const t = String(card?.invoice_type || "").trim();
  if (t === "رسمی" || t === "کد ملی") return t;
  return card?.vat_enabled ? "رسمی" : "کد ملی";
}

function calcCardVat(card) {
  if (cardInvoiceType(card) !== "رسمی") return 0;
  const sub = calcCardSubtotal(card);
  return Math.round(sub * 0.1);
}

function calcCardGrand(card) {
  const sub = calcCardSubtotal(card);
  const vat = calcCardVat(card);
  const discount = parseFloat(card.discount) || 0;
  return Math.max(0, sub + vat - discount);
}

function setCardVatEnabled(ci, enabled) {
  const card = issueState.preInvoices[ci];
  if (!card) return;
  card.vat_enabled = !!enabled;
  card.invoice_type = card.vat_enabled ? "رسمی" : "کد ملی";
  updatePreInvoiceCardSummary(ci);
  scheduleIssueDraftSave();
}

function onPreInvoiceLineInput(ci, li, field, value) {
  const card = issueState.preInvoices[ci];
  if (!card?.lines?.[li]) return;
  card.lines[li][field] = value;
  const totalEl = document.getElementById(`pi-line-total-${ci}-${li}`);
  if (totalEl) {
    totalEl.textContent = calcLineTotal(card.lines[li]).toLocaleString("fa-IR");
  }
  updatePreInvoiceCardSummary(ci);
  scheduleIssueDraftSave();
}

function onPreInvoiceDiscountInput(ci, value) {
  const card = issueState.preInvoices[ci];
  if (!card) return;
  card.discount = value;
  updatePreInvoiceCardSummary(ci);
  scheduleIssueDraftSave();
}

function updatePreInvoiceCardSummary(ci) {
  const card = issueState.preInvoices[ci];
  if (!card) return;
  const sub = calcCardSubtotal(card);
  const vat = calcCardVat(card);
  const grand = calcCardGrand(card);
  const discount = parseFloat(card.discount) || 0;
  const type = cardInvoiceType(card);
  const summaryEl = document.getElementById(`pi-card-summary-${ci}`);
  if (summaryEl) {
    summaryEl.innerHTML = `جمع اقلام: ${sub.toLocaleString("fa-IR")}`
      + (type === "رسمی" ? ` · مالیات: ${vat.toLocaleString("fa-IR")}` : "")
      + ` · تخفیف: ${discount.toLocaleString("fa-IR")}`
      + ` · <strong class="text-indigo-700">جمع کل: ${grand.toLocaleString("fa-IR")}</strong> ریال`;
  }
  const vatEl = document.getElementById(`pi-card-vat-${ci}`);
  if (vatEl) {
    vatEl.innerHTML = `نوع فاکتور: <strong>${type === "رسمی" ? "رسمی (با مالیات ۱۰٪)" : "کد ملی (بدون مالیات)"}</strong>`
      + ` · مالیات: <strong class="text-indigo-600">${type === "رسمی" ? `${vat.toLocaleString("fa-IR")} ریال` : "—"}</strong>`;
  }
}

function getPreInvoicePrintStyles() {
  return `
    @page { size: A4; margin: 14mm; }
    * { box-sizing: border-box; }
    body { font-family: Tahoma, 'Segoe UI', sans-serif; color: #1e293b; margin: 0; padding: 0; background: #fff; }
    .doc { max-width: 800px; margin: 0 auto; border: 2px solid #312e81; border-radius: 4px; overflow: hidden; }
    .doc-header { background: linear-gradient(135deg, #312e81 0%, #4338ca 100%); color: #fff; padding: 16px 20px; text-align: center; }
    .doc-title { font-size: 18px; font-weight: 800; letter-spacing: 0.02em; }
    .doc-sub { font-size: 11px; opacity: 0.9; margin-top: 4px; }
    .doc-body { padding: 16px 20px 20px; }
    .section-title { font-size: 11px; font-weight: 700; color: #4338ca; margin: 12px 0 6px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }
    .meta-table { width: 100%; border-collapse: collapse; font-size: 10px; margin-bottom: 10px; }
    .meta-table td, .meta-table th { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: center; }
    .meta-table td:nth-child(odd) { background: #f8fafc; font-weight: 600; color: #475569; width: 14%; }
    .contractor-table th { background: #eef2ff; color: #3730a3; font-weight: 700; }
    .contractor-table td { font-weight: 600; }
    table.items { width: 100%; border-collapse: collapse; font-size: 10px; margin-top: 4px; }
    table.items th { background: #eef2ff; color: #3730a3; border: 1px solid #c7d2fe; padding: 8px 6px; font-weight: 700; }
    table.items td { border: 1px solid #e2e8f0; padding: 7px 6px; vertical-align: top; }
    table.items tbody tr:nth-child(even) { background: #fafafa; }
    .doc-footer { margin-top: 14px; border-top: 2px solid #e2e8f0; padding-top: 12px; }
    .footer-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; font-size: 11px; margin-bottom: 12px; }
    .footer-block { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 10px; }
    .footer-block.full { grid-column: 1 / -1; }
    .footer-block .lbl { color: #64748b; font-size: 10px; display: block; margin-bottom: 2px; }
    .footer-block .val { font-weight: 600; }
    .totals-wrap { display: flex; justify-content: flex-end; margin-top: 8px; }
    .totals-table { width: 100%; max-width: 340px; font-size: 11px; border-collapse: collapse; border: 1px solid #c7d2fe; }
    .totals-table td { border: 1px solid #e2e8f0; padding: 7px 12px; }
    .totals-table td:first-child { background: #f8fafc; color: #475569; width: 45%; }
    .totals-table td:last-child { text-align: left; direction: ltr; font-weight: 700; }
    .totals-vat td { color: #64748b !important; font-size: 10px; font-weight: 400 !important; }
    .totals-grand td { background: #eef2ff !important; color: #312e81; font-size: 13px !important; }
    .doc-footnote { margin-top: 12px; font-size: 9px; color: #94a3b8; text-align: center; border-top: 1px dashed #e2e8f0; padding-top: 8px; }
  `;
}

function buildCardFooterMetaPrintHtml(card) {
  const type = cardInvoiceType(card);
  return `<div class="footer-meta">
    <div class="footer-block"><span class="lbl">نوع فاکتور</span><span class="val">${escHtml(type)}</span></div>
    <div class="footer-block"><span class="lbl">شهر پیمانکار</span><span class="val">${escHtml(card.contractor_city || "—")}</span></div>
    <div class="footer-block"><span class="lbl">تخفیف</span><span class="val">${fmtNum(card.discount || 0)} ریال</span></div>
    <div class="footer-block"><span class="lbl">زمان تحویل</span><span class="val">${escHtml(card.delivery_time || "—")}</span></div>
    ${card.description ? `<div class="footer-block full"><span class="lbl">شرح</span><span class="val">${escHtml(card.description)}</span></div>` : ""}
    ${card.notes ? `<div class="footer-block full"><span class="lbl">توضیحات</span><span class="val">${escHtml(card.notes)}</span></div>` : ""}
  </div>`;
}

function buildCardTotalsPrintHtml(card) {
  const sub = calcCardSubtotal(card);
  const vat = calcCardVat(card);
  const discount = parseFloat(card.discount) || 0;
  const grand = calcCardGrand(card);
  const type = cardInvoiceType(card);
  const vatRow = type === "رسمی"
    ? `<tr><td>مالیات (۱۰٪)</td><td>${fmtNum(vat)} ریال</td></tr>`
    : `<tr class="totals-vat"><td>مالیات</td><td>— (فاکتور کد ملی)</td></tr>`;
  return `<div class="totals-wrap"><table class="totals-table">
    <tr><td>جمع اقلام</td><td>${fmtNum(sub)} ریال</td></tr>
    ${vatRow}
    <tr><td>تخفیف</td><td>${fmtNum(discount)} ریال</td></tr>
    <tr class="totals-grand"><td><strong>جمع کل نهایی</strong></td><td><strong>${fmtNum(grand)} ریال</strong></td></tr>
  </table></div>`;
}

function escAttr(val) {
  return String(val ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escHtml(val) {
  return escAttr(val);
}

function getIssueHeaderSnapshot() {
  return {
    inquiry_number: $("issueInquiryNumber")?.value?.trim() || "—",
    purchase_number: $("issuePurchaseNumber")?.value?.trim() || "—",
    purchase_type: $("issuePurchaseType")?.value || "—",
    deadline: $("issueDeadline")?.value?.trim() || "—",
    unit: $("issueUnit")?.value?.trim() || "—",
    urgency: $("issueUrgency")?.value || "—",
    warehouse: $("issueWarehouse")?.value?.trim() || "—",
    requester: $("issueRequester")?.value?.trim() || "—",
    material_request_number: $("issueMaterialRequestNumber")?.value?.trim() || "—",
    material_request_date: $("issueMaterialRequestDate")?.value?.trim() || "—",
    receipt_date: $("issueReceiptDate")?.value?.trim() || "—",
    reason: $("issueReason")?.value?.trim() || "",
    risk: $("issueRisk")?.value?.trim() || "",
    expert: window.state?.user?.expert || window.state?.user?.name || window.state?.user?.username || "—",
    printed_at: new Date().toLocaleString("fa-IR"),
  };
}

function issuePreInvoicesAsCompareData() {
  return issueState.preInvoices.map((card, idx) => ({
    id: card.id,
    "نام پیمانکار": (card.contractor || "").trim() || `پیمانکار ${idx + 1}`,
    "شماره پیش فاکتور": card.preinvoice_number || "",
    "شهر پیمانکار": card.contractor_city || "",
    "زمان تحویل": card.delivery_time || "",
    "تاریخ پیش فاکتور": card.date || "",
    "نوع فاکتور": cardInvoiceType(card),
    "شرح": card.description || "",
    "توضیحات": card.notes || "",
    "تخفیف": parseFloat(card.discount) || 0,
    "جمع اقلام": calcCardSubtotal(card),
    "مالیات بر ارزش افزوده": calcCardVat(card),
    "جمع کل": calcCardGrand(card),
    lines: (card.lines || []).map((l, li) => ({
      ردیف: l.row_number || li + 1,
      "عنوان کالا": l.product_title || "—",
      "واحد": l.unit || "",
      "فی": parseFloat(l.unit_price) || 0,
      "تعداد": parseFloat(l.quantity) || 0,
      "جمع کل": calcLineTotal(l),
      "توضیحات": l.notes || "",
    })),
  }));
}

function buildIssueCompareMatrix() {
  const pres = issuePreInvoicesAsCompareData();
  return { ...buildCompareMatrix({ pre_invoices: pres }), pres };
}

const savedInquiryState = { data: null };
window.savedInquiryState = savedInquiryState;

function getInquiryHeaderFromData(data) {
  return {
    inquiry_number: data["شماره استعلام"] || "—",
    purchase_number: data["شماره درخواست خرید"] || "—",
    purchase_type: data["نوع خرید"] || "—",
    deadline: data["مهلت استعلام"] || "—",
    warehouse: data["انبار"] || "—",
    requester: data["درخواست دهنده"] || "—",
    expert: data["کارشناس خرید"] || data["صادر کننده سند"] || "—",
    urgency: data["رمز فوریت"] || "—",
    material_request_number: data["شماره درخواست کالا"] || "—",
    material_request_date: data["تاریخ درخواست کالا"] || "—",
    printed_at: new Date().toLocaleString("fa-IR"),
  };
}

function validateIssueCompareExport() {
  const headerErr = validateIssueHeader();
  if (headerErr) return headerErr;
  if (!issueState.headerConfirmed) return "ابتدا اطلاعات استعلام را تایید کنید";
  if (!issueState.preInvoices.length) return "حداقل یک پیش‌فاکتور برای مقایسه لازم است";
  return null;
}

function validateInquiryCompareExport(sourceData) {
  if (sourceData) {
    if (!(sourceData.pre_invoices || []).length) return "پیش‌فاکتوری برای چاپ یافت نشد";
    return null;
  }
  return validateIssueCompareExport();
}

function getCompareMatrixFromSource(sourceData) {
  if (sourceData) {
    const pres = sourceData.pre_invoices || [];
    return { ...buildCompareMatrix({ pre_invoices: pres }), pres };
  }
  return buildIssueCompareMatrix();
}

function buildComparePrintHtml(sourceData) {
  const issued = !!sourceData;
  const header = issued ? getInquiryHeaderFromData(sourceData) : getIssueHeaderSnapshot();
  const { rows, contractors, pres } = getCompareMatrixFromSource(sourceData);
  const totalRows = rows.length;
  const coverage = contractorCoverage(pres, totalRows);

  const contractorRows = pres.map((pi) => {
    const name = pi["نام پیمانکار"] || "—";
    const cov = coverage[name] || { quoted: 0, total: totalRows, partial: false };
    const covText = cov.partial
      ? `${cov.quoted} از ${cov.total} ردیف`
      : cov.quoted === 0 ? "بدون قیمت" : "پوشش کامل";
    return `<tr>
      <td>${escHtml(name)}</td>
      <td>${escHtml(pi["شماره پیش فاکتور"] || "—")}</td>
      <td>${escHtml(pi["شهر پیمانکار"] || "—")}</td>
      <td>${escHtml(pi["تاریخ پیش فاکتور"] || "—")}</td>
      <td>${escHtml(pi["زمان تحویل"] || "—")}</td>
      <td>${escHtml(pi["نوع فاکتور"] || "—")}</td>
      <td>${escHtml(pi["شرح"] || "—")}</td>
      <td>${escHtml(pi["توضیحات"] || "—")}</td>
      <td>${escHtml(covText)}</td>
    </tr>`;
  }).join("");

  const contractorGroupHeaders = contractors.map((c) =>
    `<th colspan="3" class="ic-contractor-head">${escHtml(c)}</th>`
  ).join("");
  const contractorSubHeaders = contractors.map(() =>
    "<th>فی (ریال)</th><th>تعداد</th><th>جمع (ریال)</th>"
  ).join("");

  const lineRows = rows.map((lr) => {
    const cells = contractors.map((c) => {
      const o = lr.offers[c];
      if (!o || !o.price) {
        return `<td class="ic-miss">—</td><td class="ic-miss">—</td><td class="ic-miss">ندارد</td>`;
      }
      return `<td>${fmtNum(o.price)}</td><td>${escHtml(o.qty ?? "—")}</td><td>${fmtNum(o.total)}</td>`;
    }).join("");
    return `<tr>
      <td class="ic-row-num">${lr.row ?? "—"}</td>
      <td class="ic-product">${escHtml(lr.title)}</td>
      <td class="ic-unit">${escHtml(lr.unit || "—")}</td>
      ${cells}
    </tr>`;
  }).join("");

  const totalsRows = [
    { label: "جمع اقلام", key: "جمع اقلام" },
    { label: "مالیات (۱۰٪)", key: "مالیات بر ارزش افزوده", empty: "—" },
    { label: "تخفیف", key: "تخفیف" },
    { label: "جمع کل نهایی", key: "جمع کل", grand: true },
  ];
  const totalsBody = totalsRows.map((tr) => {
    const cells = contractors.map((c) => {
      const pi = pres.find((p) => p["نام پیمانکار"] === c);
      if (!pi) return `<td>—</td>`;
      if (tr.key === "مالیات بر ارزش افزوده" && pi["نوع فاکتور"] !== "رسمی") {
        return `<td>${tr.empty || "—"}</td>`;
      }
      const val = Number(pi[tr.key] || 0);
      return `<td class="${tr.grand ? "ic-grand-val" : ""}">${fmtNum(val)}</td>`;
    }).join("");
    return `<tr class="${tr.grand ? "ic-grand-row" : ""}"><td class="ic-total-label">${tr.label}</td>${cells}</tr>`;
  }).join("");

  const metaRows = [
    ["شماره استعلام", header.inquiry_number, "شماره خرید", header.purchase_number],
    ["نوع خرید", header.purchase_type, "مهلت استعلام", header.deadline],
    ["انبار", header.warehouse, "درخواست‌دهنده", header.requester],
    ["کارشناس", header.expert, "رمز فوریت", header.urgency],
    ["شماره درخواست کالا", header.material_request_number, "تاریخ درخواست", header.material_request_date],
  ];

  const colSpan = 3 + contractors.length;

  return `<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8">
  <title>مقایسه استعلام ${escHtml(header.inquiry_number)}</title>
  <style>
    @page { size: A4 landscape; margin: 12mm; }
    * { box-sizing: border-box; }
    body { font-family: Tahoma, 'Segoe UI', sans-serif; color: #1e293b; margin: 0; padding: 16px; background: #fff; }
    .doc-wrap { border: 2px solid #312e81; border-radius: 4px; overflow: hidden; }
    .doc-head { background: linear-gradient(135deg, #312e81 0%, #4338ca 100%); color: #fff; padding: 14px 18px; text-align: center; }
    .doc-head h1 { font-size: 17px; margin: 0 0 4px; }
    .doc-head p { font-size: 10px; margin: 0; opacity: 0.9; }
    .doc-body { padding: 14px 16px 16px; }
    .ic-section-title { font-size: 11px; font-weight: 700; color: #4338ca; margin: 12px 0 6px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }
    .ic-meta { width: 100%; border-collapse: collapse; font-size: 10px; margin-bottom: 10px; }
    .ic-meta td { border: 1px solid #e2e8f0; padding: 5px 8px; }
    .ic-meta td:nth-child(odd) { background: #f8fafc; font-weight: 600; width: 14%; color: #475569; }
    table.ic-contractors { width: 100%; border-collapse: collapse; font-size: 9px; margin-bottom: 12px; }
    table.ic-contractors th { background: #eef2ff; color: #3730a3; border: 1px solid #c7d2fe; padding: 6px 5px; text-align: center; }
    table.ic-contractors td { border: 1px solid #e2e8f0; padding: 5px; text-align: center; vertical-align: top; }
    table.ic-matrix { width: 100%; border-collapse: collapse; font-size: 9px; }
    table.ic-matrix th { background: #eef2ff; color: #3730a3; border: 1px solid #c7d2fe; padding: 6px 4px; text-align: center; }
    table.ic-matrix td { border: 1px solid #e2e8f0; padding: 5px 4px; text-align: center; vertical-align: middle; }
    .ic-contractor-head { background: #4338ca !important; color: #fff !important; font-size: 10px; }
    .ic-row-num { font-weight: 700; background: #f8fafc; width: 32px; }
    .ic-product { text-align: right !important; min-width: 120px; }
    .ic-unit { min-width: 48px; }
    .ic-miss { color: #b45309; font-weight: 600; background: #fffbeb; }
    table.ic-totals { width: 100%; max-width: 520px; margin-top: 12px; margin-right: auto; border-collapse: collapse; font-size: 10px; border: 2px solid #c7d2fe; }
    table.ic-totals th { background: #eef2ff; color: #3730a3; border: 1px solid #c7d2fe; padding: 7px 8px; text-align: center; }
    table.ic-totals td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: center; }
    .ic-total-label { background: #f8fafc; font-weight: 700; text-align: right !important; color: #475569; width: 110px; }
    .ic-grand-row td { background: #eef2ff; font-weight: 800; color: #312e81; }
    .ic-grand-val { font-size: 11px; }
    .ic-foot { margin-top: 10px; font-size: 9px; color: #94a3b8; text-align: center; border-top: 1px dashed #e2e8f0; padding-top: 8px; }
    .ic-note { font-size: 10px; color: #92400e; background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 8px; margin-bottom: 10px; }
  </style>
</head>
<body>
  <div class="doc-wrap">
    <div class="doc-head">
      <h1>مقایسه پیش‌فاکتور استعلام</h1>
      <p>خرید ${escHtml(header.purchase_number)} · چاپ ${escHtml(header.printed_at)} · ${issued ? "استعلام ثبت‌شده" : "پیش از ثبت نهایی"}</p>
    </div>
    <div class="doc-body">
      <div class="ic-section-title">اطلاعات استعلام</div>
      <table class="ic-meta">${metaRows.map((r) => `<tr>${r.map((c) => `<td>${escHtml(c)}</td>`).join("")}</tr>`).join("")}</table>
      ${Object.values(coverage).some((c) => c.partial) ? '<div class="ic-note">برخی پیمانکاران همه ردیف‌ها را قیمت‌گذاری نکرده‌اند — «ندارد» یعنی برای آن کالا پیشنهادی ثبت نشده.</div>' : ""}
      <div class="ic-section-title">مشخصات پیمانکاران</div>
      <table class="ic-contractors">
        <thead><tr>
          <th>نام پیمانکار</th><th>شماره پیش‌فاکتور</th><th>شهر</th><th>تاریخ</th>
          <th>زمان تحویل</th><th>نوع فاکتور</th><th>شرح</th><th>توضیحات</th><th>پوشش ردیف</th>
        </tr></thead>
        <tbody>${contractorRows || `<tr><td colspan="9">پیش‌فاکتوری ثبت نشده</td></tr>`}</tbody>
      </table>
      <div class="ic-section-title">اقلام استعلام</div>
      <table class="ic-matrix">
        <thead>
          <tr><th rowspan="2">ردیف</th><th rowspan="2">عنوان کالا</th><th rowspan="2">واحد</th>${contractorGroupHeaders}</tr>
          <tr>${contractorSubHeaders}</tr>
        </thead>
        <tbody>${lineRows || `<tr><td colspan="${colSpan}">ردیفی نیست</td></tr>`}</tbody>
      </table>
      <div class="ic-section-title">جمع‌بندی مالی</div>
      <table class="ic-totals">
        <thead><tr><th>شرح</th>${contractors.map((c) => `<th>${escHtml(c)}</th>`).join("")}</tr></thead>
        <tbody>${totalsBody}</tbody>
      </table>
      <p class="ic-foot">سامانه تدارکات — سند مقایسه پیش‌فاکتور</p>
    </div>
  </div>
</body>
</html>`;
}

function printHtmlDocument(html, title = "چاپ") {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const iframe = document.createElement("iframe");
  iframe.setAttribute("title", title);
  iframe.style.cssText = "position:fixed;left:-9999px;top:0;width:0;height:0;border:0";
  document.body.appendChild(iframe);

  const cleanup = () => {
    URL.revokeObjectURL(url);
    iframe.remove();
  };

  const doPrint = () => {
    try {
      iframe.contentWindow.focus();
      iframe.contentWindow.print();
    } catch {
      const w = window.open(url, "_blank");
      if (w) {
        w.addEventListener("load", () => {
          w.focus();
          w.print();
        });
      } else {
        alert("چاپ ممکن نشد — popup یا چاپگر را بررسی کنید");
      }
    }
    setTimeout(cleanup, 2000);
  };

  iframe.onload = () => setTimeout(doPrint, 150);
  iframe.onerror = cleanup;
  iframe.src = url;
}

function savedPreInvoiceToCard(pi) {
  const vatEnabled = pi["نوع فاکتور"] === "رسمی" || pi["اعمال مالیات ده درصد"];
  return {
    contractor: pi["نام پیمانکار"] || "",
    preinvoice_number: pi["شماره پیش فاکتور"] || "",
    contractor_city: pi["شهر پیمانکار"] || "",
    date: pi["تاریخ پیش فاکتور"] || "",
    delivery_time: pi["زمان تحویل"] || "",
    description: pi["شرح"] || "",
    notes: pi["توضیحات"] || "",
    discount: pi["تخفیف"] || 0,
    invoice_type: pi["نوع فاکتور"] || (vatEnabled ? "رسمی" : "کد ملی"),
    vat_enabled: !!vatEnabled,
    lines: (pi.lines || []).map((line, li) => ({
      row_number: line.ردیف || li + 1,
      product_title: line["عنوان کالا"] || "—",
      unit: line["واحد"] || "",
      unit_price: line["فی"] || 0,
      quantity: line["تعداد"] || 0,
      notes: line["توضیحات"] || "",
    })),
  };
}

function buildPreInvoiceCardPrintHtml(cardOrIndex, sourceData) {
  let card;
  if (typeof cardOrIndex === "number") {
    card = issueState.preInvoices[cardOrIndex];
  } else if (cardOrIndex && typeof cardOrIndex === "object") {
    card = savedPreInvoiceToCard(cardOrIndex);
  } else {
    return "";
  }
  if (!card) return "";
  const header = sourceData ? getInquiryHeaderFromData(sourceData) : getIssueHeaderSnapshot();
  const type = cardInvoiceType(card);
  const lines = (card.lines || []).map((line, li) => `
    <tr>
      <td>${line.row_number || li + 1}</td>
      <td>${escHtml(line.product_title || "—")}</td>
      <td>${escHtml(line.unit || "—")}</td>
      <td>${fmtNum(line.unit_price)}</td>
      <td>${escHtml(line.quantity)}</td>
      <td>${fmtNum(calcLineTotal(line))}</td>
      <td>${escHtml(line.notes || "")}</td>
    </tr>`).join("");

  const inquiryMeta = [
    ["شماره استعلام", header.inquiry_number, "شماره خرید", header.purchase_number],
    ["انبار", header.warehouse, "کارشناس", header.expert],
    ["نوع خرید", header.purchase_type, "مهلت استعلام", header.deadline],
  ];

  return `<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8">
  <title>پیش‌فاکتور ${escHtml(card.preinvoice_number)}</title>
  <style>${getPreInvoicePrintStyles()}</style></head><body>
  <div class="doc">
    <div class="doc-header">
      <div class="doc-title">پیش‌فاکتور / استعلام قیمت</div>
      <div class="doc-sub">سامانه تدارکات · چاپ ${escHtml(header.printed_at)}</div>
    </div>
    <div class="doc-body">
      <div class="section-title">اطلاعات استعلام</div>
      <table class="meta-table">${inquiryMeta.map((r) => `<tr>${r.map((c) => `<td>${escHtml(c)}</td>`).join("")}</tr>`).join("")}</table>
      <div class="section-title">مشخصات پیمانکار</div>
      <table class="meta-table contractor-table">
        <thead><tr>
          <th>نام پیمانکار</th><th>شماره پیش‌فاکتور</th><th>شهر</th><th>تاریخ</th>
          <th>زمان تحویل</th><th>نوع فاکتور</th><th>شرح</th><th>توضیحات</th>
        </tr></thead>
        <tbody><tr>
          <td>${escHtml(card.contractor || "—")}</td>
          <td>${escHtml(card.preinvoice_number || "—")}</td>
          <td>${escHtml(card.contractor_city || "—")}</td>
          <td>${escHtml(card.date || "—")}</td>
          <td>${escHtml(card.delivery_time || "—")}</td>
          <td>${escHtml(type)}</td>
          <td>${escHtml(card.description || "—")}</td>
          <td>${escHtml(card.notes || "—")}</td>
        </tr></tbody>
      </table>
      <div class="section-title">اقلام</div>
      <table class="items"><thead><tr>
        <th>ردیف</th><th>شرح کالا</th><th>واحد</th><th>فی (ریال)</th><th>تعداد</th><th>جمع (ریال)</th><th>توضیح</th>
      </tr></thead><tbody>${lines}</tbody></table>
      <div class="doc-footer">
        ${buildCardTotalsPrintHtml(card)}
      </div>
      <p class="doc-footnote">این سند پیش از ثبت نهایی استعلام صادر شده است.</p>
    </div>
  </div>
  </body></html>`;
}

function printInquiryPreInvoice(sourceData, cardIndex) {
  const data = sourceData || null;
  if (!data) {
    if (!issueState.headerConfirmed) {
      $("issueError").textContent = "ابتدا اطلاعات استعلام را تایید کنید";
      $("issueError").classList.remove("hidden");
      return;
    }
    const html = buildPreInvoiceCardPrintHtml(cardIndex);
    if (!html) return;
    $("issueError")?.classList.add("hidden");
    printHtmlDocument(html, "پیش‌فاکتور");
    return;
  }
  const pi = (data.pre_invoices || [])[cardIndex];
  if (!pi) return;
  const html = buildPreInvoiceCardPrintHtml(pi, data);
  if (!html) return;
  printHtmlDocument(html, "پیش‌فاکتور");
}

function printPreInvoiceCard(cardIndex) {
  printInquiryPreInvoice(null, cardIndex);
}

function printInquiryCompare(sourceData) {
  const data = sourceData || null;
  const err = validateInquiryCompareExport(data);
  if (err) {
    if (!data) {
      $("issueError").textContent = err;
      $("issueError").classList.remove("hidden");
    } else {
      alert(err);
    }
    return;
  }
  if (!data) $("issueError")?.classList.add("hidden");
  printHtmlDocument(buildComparePrintHtml(data), "مقایسه پیش‌فاکتور");
}

function printIssueCompare() {
  printInquiryCompare(null);
}

function printInquiryCompareFromDetail() {
  printInquiryCompare(savedInquiryState.data);
}

function printInquiryCompareFromReview() {
  printInquiryCompare(reviewState.data);
}

function printInquiryPreInvoiceFromDetail(cardIndex) {
  printInquiryPreInvoice(savedInquiryState.data, cardIndex);
}

function exportInquiryCompareExcel(sourceData) {
  const data = sourceData || null;
  const err = validateInquiryCompareExport(data);
  if (err) {
    if (!data) {
      $("issueError").textContent = err;
      $("issueError").classList.remove("hidden");
    } else {
      alert(err);
    }
    return;
  }
  if (!window.XLSX) {
    alert("کتابخانه اکسل بارگذاری نشده — صفحه را رفرش کنید");
    return;
  }
  if (!data) $("issueError")?.classList.add("hidden");

  const issued = !!data;
  const header = issued ? getInquiryHeaderFromData(data) : getIssueHeaderSnapshot();
  const { rows, contractors, pres } = getCompareMatrixFromSource(data);
  const aoa = [];

  aoa.push([issued ? "مقایسه پیش‌فاکتور استعلام (ثبت‌شده)" : "مقایسه پیش‌فاکتور استعلام (پیش از ثبت)"]);
  aoa.push(["شماره استعلام", header.inquiry_number, "شماره خرید", header.purchase_number]);
  aoa.push(["نوع خرید", header.purchase_type, "مهلت", header.deadline]);
  aoa.push(["انبار", header.warehouse, "درخواست‌دهنده", header.requester]);
  aoa.push(["کارشناس", header.expert, "تاریخ چاپ", header.printed_at]);
  aoa.push([]);

  const contractorHeader = ["ردیف", "عنوان کالا", "واحد"];
  contractors.forEach((c) => {
    contractorHeader.push(`${c} — فی (ریال)`, `${c} — تعداد`, `${c} — جمع (ریال)`);
  });
  aoa.push(contractorHeader);

  rows.forEach((lr) => {
    const row = [lr.row ?? "", lr.title, lr.unit || ""];
    contractors.forEach((c) => {
      const o = lr.offers[c];
      if (!o || !o.price) {
        row.push("ندارد", "", "");
      } else {
        row.push(o.price, o.qty ?? "", o.total ?? "");
      }
    });
    aoa.push(row);
  });

  aoa.push([]);
  const subtotalRow = ["", "جمع اقلام", ""];
  const vatRow = ["", "مالیات (۱۰٪)", ""];
  const discountRow = ["", "تخفیف", ""];
  const grandRow = ["", "جمع کل نهایی", ""];
  contractors.forEach((c) => {
    const pi = pres.find((p) => p["نام پیمانکار"] === c);
    if (!pi) {
      subtotalRow.push("", "", "");
      vatRow.push("", "", "");
      discountRow.push("", "", "");
      grandRow.push("", "", "");
      return;
    }
    subtotalRow.push(pi["جمع اقلام"] ?? "", "", "");
    vatRow.push(pi["نوع فاکتور"] === "رسمی" ? (pi["مالیات بر ارزش افزوده"] ?? "") : "—", "", "");
    discountRow.push(pi["تخفیف"] ?? "", "", "");
    grandRow.push(pi["جمع کل"] ?? "", "", "");
  });
  aoa.push(subtotalRow, vatRow, discountRow, grandRow);

  pres.forEach((pi) => {
    aoa.push([]);
    aoa.push([`پیمانکار: ${pi["نام پیمانکار"]}`]);
    aoa.push(["شماره پیش‌فاکتور", pi["شماره پیش فاکتور"], "شهر پیمانکار", pi["شهر پیمانکار"]]);
    aoa.push(["تاریخ پیش‌فاکتور", pi["تاریخ پیش فاکتور"], "زمان تحویل", pi["زمان تحویل"]]);
    aoa.push(["نوع فاکتور", pi["نوع فاکتور"], "شرح", pi["شرح"]]);
    aoa.push(["توضیحات", pi["توضیحات"], "تخفیف (ریال)", pi["تخفیف"]]);
    aoa.push(["جمع اقلام", pi["جمع اقلام"], "مالیات", pi["مالیات بر ارزش افزوده"]]);
    aoa.push(["جمع کل", pi["جمع کل"]]);
    aoa.push(["ردیف", "کالا", "واحد", "فی", "تعداد", "جمع", "توضیح ردیف"]);
    (pi.lines || []).forEach((line) => {
      aoa.push([
        line.ردیف, line["عنوان کالا"], line["واحد"],
        line["فی"], line["تعداد"], line["جمع کل"], line["توضیحات"] || "",
      ]);
    });
  });

  const ws = XLSX.utils.aoa_to_sheet(aoa);
  ws["!cols"] = [{ wch: 8 }, { wch: 28 }, { wch: 10 }, ...contractors.flatMap(() => [{ wch: 14 }, { wch: 8 }, { wch: 14 }])];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "مقایسه");
  const fname = `inquiry-${header.inquiry_number || header.purchase_number}-compare.xlsx`;
  XLSX.writeFile(wb, fname);
  if (typeof toast === "function") toast("فایل اکسل دانلود شد");
}

function exportIssueCompareExcel() {
  exportInquiryCompareExcel(null);
}

function exportInquiryCompareExcelFromDetail() {
  exportInquiryCompareExcel(savedInquiryState.data);
}

function exportInquiryCompareExcelFromReview() {
  exportInquiryCompareExcel(reviewState.data);
}

function renderPreInvoiceCards() {
  const box = $("preInvoiceCards");
  if (!box) return;

  box.innerHTML = issueState.preInvoices.map((card, ci) => {
    const sub = calcCardSubtotal(card);
    const vat = calcCardVat(card);
    const grand = calcCardGrand(card);
    const linesHtml = card.lines.map((line, li) => `
      <tr>
        <td class="text-center text-xs font-medium text-slate-500">${line.row_number || li + 1}</td>
        <td class="issue-line-title">
          <div class="flex gap-1 items-start">
            <input class="input !py-1.5 !text-xs flex-1 min-w-[200px]" value="${escAttr(line.product_title)}"
              onchange="issueState.preInvoices[${ci}].lines[${li}].product_title=this.value;scheduleIssueDraftSave()" placeholder="عنوان کالا">
            <button type="button" class="btn btn-ghost !px-2 !py-1 !text-[10px] shrink-0" title="مقایسه با آخرین خرید"
              onclick="openLastPurchaseCompare(${ci},${li})">↔</button>
          </div>
        </td>
        <td><input class="input !py-1 !text-xs !w-20" list="unitList" value="${escAttr(line.unit)}"
          onchange="issueState.preInvoices[${ci}].lines[${li}].unit=this.value;scheduleIssueDraftSave()" placeholder="واحد"></td>
        <td><input type="number" class="input !py-1 !text-xs !w-28" value="${line.unit_price}" oninput="onPreInvoiceLineInput(${ci},${li},'unit_price',this.value)"></td>
        <td><input type="number" step="any" class="input !py-1 !text-xs !w-20" value="${line.quantity}" oninput="onPreInvoiceLineInput(${ci},${li},'quantity',this.value)"></td>
        <td id="pi-line-total-${ci}-${li}" class="text-xs font-medium whitespace-nowrap">${calcLineTotal(line).toLocaleString("fa-IR")}</td>
        <td class="issue-line-notes"><textarea class="input !py-1.5 !text-xs min-h-[2.5rem] resize-y" rows="2"
          onchange="issueState.preInvoices[${ci}].lines[${li}].notes=this.value;scheduleIssueDraftSave()" placeholder="توضیحات">${escAttr(line.notes)}</textarea></td>
        <td><button type="button" class="text-red-500 text-xs" onclick="removeLine(${card.id},${li})">✕</button></td>
      </tr>`).join("");

    return `
    <div class="border border-slate-200 rounded-xl p-4 mb-3 bg-slate-50">
      <div class="flex justify-between items-center mb-3">
        <h4 class="font-bold text-sm text-indigo-800">پیش‌فاکتور پیمانکار ${ci + 1}</h4>
        <div class="flex gap-2">
          <button type="button" class="btn btn-ghost !py-1 !px-2 !text-[10px]" onclick="printPreInvoiceCard(${ci})" title="چاپ این پیش‌فاکتور">🖨 چاپ</button>
          <button type="button" class="text-red-500 text-xs" onclick="removePreInvoiceCard(${card.id})">حذف</button>
        </div>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-2 mb-2">
        <div class="relative md:col-span-2">
          <label class="text-[10px] text-slate-500">پیمانکار *</label>
          <input class="input !py-1.5 !text-xs mt-0.5" list="contractorList" value="${escAttr(card.contractor)}"
            oninput="issueState.preInvoices[${ci}].contractor=this.value;searchContractors(this.value);scheduleIssueDraftSave()"
            placeholder="جستجو یا تایپ...">
        </div>
        <div>
          <label class="text-[10px] text-slate-500">شماره پیش‌فاکتور *</label>
          <input class="input !py-1.5 !text-xs mt-0.5" value="${escAttr(card.preinvoice_number)}"
            onchange="issueState.preInvoices[${ci}].preinvoice_number=this.value;scheduleIssueDraftSave()">
        </div>
        <div>
          <label class="text-[10px] text-slate-500">شهر پیمانکار</label>
          <input class="input !py-1.5 !text-xs mt-0.5" list="cityList" value="${escAttr(card.contractor_city)}"
            onchange="issueState.preInvoices[${ci}].contractor_city=this.value;scheduleIssueDraftSave()" placeholder="انتخاب یا تایپ...">
        </div>
        <div>
          <label class="text-[10px] text-slate-500">تاریخ پیش‌فاکتور</label>
          <input class="input !py-1.5 !text-xs mt-0.5" value="${escAttr(card.date)}"
            onchange="issueState.preInvoices[${ci}].date=this.value;scheduleIssueDraftSave()">
        </div>
        <div>
          <label class="text-[10px] text-slate-500">زمان تحویل</label>
          <input class="input !py-1.5 !text-xs mt-0.5" value="${escAttr(card.delivery_time)}"
            onchange="issueState.preInvoices[${ci}].delivery_time=this.value;scheduleIssueDraftSave()" placeholder="مثلاً ۷ روز">
        </div>
      </div>
      <label class="flex items-center gap-2 text-xs mb-2">
        <input type="checkbox" ${card.selected ? "checked" : ""} onchange="issueState.preInvoices[${ci}].selected=this.checked;scheduleIssueDraftSave()">
        انتخاب این پیمانکار برای مقایسه
      </label>
      <div class="overflow-x-auto issue-table">
        <table class="data-table !text-xs">
          <thead><tr>
            <th>ردیف</th><th>عنوان کالا</th><th>واحد</th><th>فی (ریال)</th><th>تعداد</th><th>جمع (ریال)</th><th>توضیحات</th><th></th>
          </tr></thead>
          <tbody>${linesHtml}</tbody>
        </table>
      </div>
      <button type="button" class="text-indigo-600 text-xs mt-2 hover:underline" onclick="addLineToCard(${card.id})">+ ردیف کالا</button>
      <p class="text-[10px] text-slate-500 mt-1">پیمانکار می‌تواند فقط برخی ردیف‌ها را قیمت‌گذاری کند — ردیف‌های بدون قیمت در مقایسه «ندارد» نمایش داده می‌شوند.</p>
      <div class="mt-3 pt-3 border-t border-slate-200 grid grid-cols-2 md:grid-cols-4 gap-2 items-end">
        <div>
          <label class="text-[10px] text-slate-500">تخفیف (ریال)</label>
          <input type="number" class="input !py-1.5 !text-xs mt-0.5" value="${card.discount}"
            oninput="onPreInvoiceDiscountInput(${ci},this.value)" placeholder="۰">
        </div>
        <div>
          <label class="text-[10px] text-slate-500">شرح</label>
          <input class="input !py-1.5 !text-xs mt-0.5" value="${escAttr(card.description)}"
            oninput="issueState.preInvoices[${ci}].description=this.value;scheduleIssueDraftSave()" placeholder="شرح پیش‌فاکتور">
        </div>
        <div>
          <label class="text-[10px] text-slate-500">توضیحات</label>
          <input class="input !py-1.5 !text-xs mt-0.5" value="${escAttr(card.notes)}"
            oninput="issueState.preInvoices[${ci}].notes=this.value;scheduleIssueDraftSave()" placeholder="توضیحات تکمیلی">
        </div>
        <label class="flex items-center gap-2 text-xs cursor-pointer select-none pb-2">
          <input type="checkbox" class="rounded border-slate-300" ${card.vat_enabled ? "checked" : ""}
            onchange="setCardVatEnabled(${ci}, this.checked)">
          <span>اعمال مالیات ده درصد</span>
        </label>
      </div>
      <p id="pi-card-vat-${ci}" class="text-[10px] text-slate-500 mt-1">نوع فاکتور: <strong>${cardInvoiceType(card) === "رسمی" ? "رسمی (با مالیات ۱۰٪)" : "کد ملی (بدون مالیات)"}</strong>
        · مالیات: <strong class="text-indigo-600">${cardInvoiceType(card) === "رسمی" ? `${vat.toLocaleString("fa-IR")} ریال` : "—"}</strong></p>
      <p id="pi-card-summary-${ci}" class="text-xs text-right mt-2 pt-2 border-t border-slate-100 text-slate-600">
        جمع اقلام: ${sub.toLocaleString("fa-IR")}
        ${cardInvoiceType(card) === "رسمی" ? ` · مالیات: ${vat.toLocaleString("fa-IR")}` : ""}
        · تخفیف: ${(parseFloat(card.discount) || 0).toLocaleString("fa-IR")}
        · <strong class="text-indigo-700">جمع کل: ${grand.toLocaleString("fa-IR")}</strong> ریال
      </p>
    </div>`;
  }).join("");
  scheduleIssueDraftSave();
}

let contractorTimer = null;
async function searchContractors(q) {
  clearTimeout(contractorTimer);
  contractorTimer = setTimeout(async () => {
    try {
      const res = await api(`/contractors/search?q=${encodeURIComponent(q)}`);
      const dl = $("contractorList");
      if (dl) dl.innerHTML = (res.items || []).map((n) => `<option value="${n}">`).join("");
    } catch { /* ignore */ }
  }, 300);
}

async function submitIssue() {
  const errEl = $("issueError");
  errEl?.classList.add("hidden");

  const headerErr = validateIssueHeader();
  if (headerErr) {
    errEl.textContent = headerErr;
    errEl.classList.remove("hidden");
    showIssueStep(1);
    return;
  }

  if (!issueState.headerConfirmed) {
    errEl.textContent = "ابتدا اطلاعات استعلام را تایید کنید";
    errEl.classList.remove("hidden");
    showIssueStep(1);
    return;
  }

  if (!issueState.preInvoices.length) {
    errEl.textContent = "حداقل یک پیش‌فاکتور اضافه کنید";
    errEl.classList.remove("hidden");
    return;
  }

  const payload = {
    purchase_number: $("issuePurchaseNumber").value.trim(),
    inquiry_number: $("issueInquiryNumber").value.trim(),
    "نوع خرید": $("issuePurchaseType").value,
    "مهلت استعلام": $("issueDeadline").value,
    "واحد/رمز تامین": $("issueUnit").value,
    "رمز فوریت": $("issueUrgency").value,
    "علت خرید": $("issueReason").value,
    "انبار": $("issueWarehouse").value.trim(),
    "درخواست دهنده": $("issueRequester").value.trim(),
    "ریسک عدم خرید": $("issueRisk").value,
    "شماره درخواست کالا": $("issueMaterialRequestNumber").value.trim(),
    "تاریخ درخواست کالا": $("issueMaterialRequestDate").value.trim(),
    "تاریخ دریافت": $("issueReceiptDate").value.trim(),
    pre_invoices: issueState.preInvoices.map((card) => ({
      "نام پیمانکار": card.contractor,
      "شهر پیمانکار": card.contractor_city,
      "شماره پیش فاکتور": card.preinvoice_number,
      "تاریخ پیش فاکتور": card.date,
      "نوع فاکتور": cardInvoiceType(card),
      "شرح": card.description || "",
      "اعمال مالیات ده درصد": cardInvoiceType(card) === "رسمی",
      "مالیات بر ارزش افزوده": calcCardVat(card),
      "تخفیف": parseFloat(card.discount) || 0,
      "زمان تحویل": card.delivery_time,
      "توضیحات": card.notes,
      "جمع کل": calcCardGrand(card),
      "انتخاب شده": card.selected,
      lines: card.lines.map((l, idx) => ({
        "ردیف": l.row_number || idx + 1,
        "عنوان کالا": l.product_title,
        "واحد": l.unit,
        "فی": parseFloat(l.unit_price) || 0,
        "تعداد": parseFloat(l.quantity) || 0,
        "جمع کل": calcLineTotal(l),
        "توضیحات": l.notes,
      })),
    })),
  };

  showLoading("در حال صدور استعلام...");
  try {
    const result = await api("/inquiries/issue", { method: "POST", body: JSON.stringify(payload) });
    clearIssueDraft($("issuePurchaseNumber").value.trim());
    issueState.preInvoices = [];
    issueState.headerConfirmed = false;
    closeIssue(true);
    toast(`استعلام ${result.inquiry["شماره استعلام"]} با ${result.pre_invoices.length} پیش‌فاکتور ذخیره شد`);
    if (typeof loadViewData === "function") loadViewData();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove("hidden");
  } finally {
    hideLoading();
  }
}

function renderLineRow(l) {
  const row = l["ردیف"] ?? l["شماره خرید"] ?? "—";
  const unit = l["واحد"] ? ` ${l["واحد"]}` : "";
  return `<tr>
    <td class="text-xs">${row}</td>
    <td class="text-xs">${l["عنوان کالا"] || "—"}</td>
    <td class="text-xs">${l["واحد"] || "—"}</td>
    <td class="text-xs">${Number(l["فی"] || 0).toLocaleString("fa-IR")}</td>
    <td class="text-xs">${l["تعداد"] ?? "—"}${unit && l["تعداد"] ? "" : ""}</td>
    <td class="text-xs font-medium">${Number(l["جمع کل"] || 0).toLocaleString("fa-IR")}</td>
    <td class="text-xs">${l["توضیحات"] || "—"}</td>
  </tr>`;
}

async function openLastPurchaseCompare(ci, li) {
  const line = issueState.preInvoices[ci]?.lines[li];
  if (!line) return;
  const title = line.product_title?.trim();
  if (!title) return alert("ابتدا عنوان کالا را وارد کنید");
  const code = issueState.purchaseData?.["کد قلم خریدنی"] || "";
  const exclude = $("issuePurchaseNumber")?.value?.trim() || "";
  showLoading("در حال جستجوی آخرین خرید...");
  let data = { found: false, item: null };
  try {
    data = await api(`/inquiries/last-purchase?code=${encodeURIComponent(code)}&title=${encodeURIComponent(title)}&exclude=${encodeURIComponent(exclude)}`);
  } catch {
    data = { found: false, item: null };
  } finally {
    hideLoading();
  }
  renderLastPurchaseCompare(line, data);
  $("lastPurchaseModal").classList.remove("hidden");
}

function renderLastPurchaseCompare(currentLine, data) {
  $("lastPurchaseTitle").textContent = `مقایسه — ${currentLine.product_title || "کالا"}`;
  const curPrice = parseFloat(currentLine.unit_price) || 0;
  const curQty = parseFloat(currentLine.quantity) || 0;
  const last = data.item;
  if (!data.found || !last) {
    $("lastPurchaseBody").innerHTML = `<p class="text-center text-slate-400 py-10">سابقه خرید قبلی برای این کالا یافت نشد</p>`;
    return;
  }
  const lastPrice = Number(last["فی"] || 0);
  const diff = curPrice - lastPrice;
  const diffPct = lastPrice ? ((diff / lastPrice) * 100).toFixed(1) : "—";
  const diffCls = diff > 0 ? "text-red-600" : diff < 0 ? "text-green-600" : "text-slate-600";
  const sourceMap = { erp: "گزارش ERP", local: "استعلام‌های محلی", history: "سابقه ثبت‌شده" };
  const sourceLabel = sourceMap[data.source] || "—";
  $("lastPurchaseBody").innerHTML = `
    <p class="text-xs text-slate-500 mb-4">منبع: ${sourceLabel}</p>
    <div class="grid md:grid-cols-2 gap-4">
      <div class="border rounded-xl p-4 bg-indigo-50 border-indigo-200">
        <h4 class="font-bold text-sm text-indigo-900 mb-3">پیش‌فاکتور جاری</h4>
        <div class="text-sm space-y-2">
          <p><span class="text-slate-500">عنوان:</span> ${currentLine.product_title || "—"}</p>
          <p><span class="text-slate-500">فی:</span> <strong>${curPrice.toLocaleString("fa-IR")}</strong> ریال</p>
          <p><span class="text-slate-500">تعداد:</span> ${curQty.toLocaleString("fa-IR")}${currentLine.unit ? ` ${currentLine.unit}` : ""}</p>
          <p><span class="text-slate-500">جمع:</span> ${(curPrice * curQty).toLocaleString("fa-IR")} ریال</p>
        </div>
      </div>
      <div class="border rounded-xl p-4 bg-slate-50">
        <h4 class="font-bold text-sm text-slate-800 mb-3">آخرین خرید</h4>
        <div class="text-sm space-y-2">
          <p><span class="text-slate-500">عنوان:</span> ${last["عنوان کالا"] || "—"}</p>
          <p><span class="text-slate-500">فی:</span> <strong>${lastPrice.toLocaleString("fa-IR")}</strong> ریال</p>
          <p><span class="text-slate-500">تعداد:</span> ${Number(last["تعداد"] || 0).toLocaleString("fa-IR") || "—"}${last["واحد"] ? ` ${last["واحد"]}` : ""}</p>
          <p><span class="text-slate-500">تاریخ:</span> ${last["تاریخ خرید"] || "—"}</p>
          <p><span class="text-slate-500">تامین‌کننده:</span> ${last["تامین کننده"] || "—"}</p>
          <p><span class="text-slate-500">شماره خرید:</span> ${last["شماره خرید"] || last["شماره سفارش"] || last["شماره استعلام"] || "—"}</p>
        </div>
      </div>
    </div>
    <div class="mt-4 p-4 rounded-xl bg-amber-50 border border-amber-200 text-sm">
      <p>اختلاف فی: <strong class="${diffCls}">${diff > 0 ? "+" : ""}${diff.toLocaleString("fa-IR")} ریال (${diffPct}٪)</strong></p>
    </div>`;
}

function closeLastPurchaseCompare() {
  $("lastPurchaseModal")?.classList.add("hidden");
}

async function openExpertInquiryDetail(inquiryNumber) {
  showLoading("در حال بارگذاری جزئیات...");
  try {
    const data = await api(`/inquiries/detail/${inquiryNumber}`);
    savedInquiryState.data = data;
    renderExpertInquiryDetail(data);
    $("expertDetailModal").classList.remove("hidden");
  } catch (e) { alert(e.message); }
  finally { hideLoading(); }
}

const reviewState = { data: null, rows: [], step: "compare" };
window.reviewState = reviewState;

async function openInquiryReview(inquiryNumber, step = "compare") {
  if (typeof isManager === "function" && !isManager()) return;
  showLoading("در حال بارگذاری...");
  try {
    await loadPurchaseExperts();
    const data = await api(`/inquiries/compare/${inquiryNumber}`);
    reviewState.data = data;
    reviewState.rows = buildCompareLineRows(data);
    $("reviewModal").classList.remove("hidden");
    setReviewStep(step);
  } catch (e) { alert(e.message); }
  finally { hideLoading(); }
}

async function openCompare(inquiryNumber) { return openInquiryReview(inquiryNumber, "compare"); }
async function openApprove(inquiryNumber) { return openInquiryReview(inquiryNumber, "approve"); }

function setReviewStep(step) {
  reviewState.step = step;
  const data = reviewState.data;
  if (!data) return;
  $("reviewTabCompare")?.classList.toggle("review-step-active", step === "compare");
  $("reviewTabApprove")?.classList.toggle("review-step-active", step === "approve");
  $("reviewTitle").textContent = `بررسی استعلام ${data["شماره استعلام"]}`;
  $("reviewSubtitle").textContent = `خرید ${data["شماره درخواست خرید"]} · ${data["کارشناس خرید"] || data["صادر کننده سند"] || "—"} · ${data["انبار"] || "—"}`;
  if (step === "compare") renderReviewCompare(data);
  else renderReviewApprove(data);
}

function closeReview() {
  $("reviewModal")?.classList.add("hidden");
  $("reviewFooter")?.classList.add("hidden");
}

function fmtNum(n) {
  return Number(n || 0).toLocaleString("fa-IR");
}

function buildCompareMatrix(data) {
  const pres = data.pre_invoices || [];
  const contractors = [...new Set(pres.map((p) => (p["نام پیمانکار"] || "").trim()).filter(Boolean))];
  const map = new Map();
  pres.forEach((pi) => {
    (pi.lines || []).forEach((line) => {
      const key = String(line.ردیف ?? line.id);
      if (!map.has(key)) {
        map.set(key, { row: line.ردیف, title: line["عنوان کالا"] || "—", unit: line["واحد"] || "", offers: {} });
      }
      map.get(key).offers[pi["نام پیمانکار"]] = {
        price: Number(line["فی"] || 0),
        qty: line["تعداد"],
        total: Number(line["جمع کل"] || 0),
        preinvoiceId: pi.id,
      };
    });
  });
  const rows = [...map.values()].sort((a, b) => String(a.row).localeCompare(String(b.row), "fa"));
  rows.forEach((lr) => {
    const prices = contractors.map((c) => lr.offers[c]?.price).filter((p) => p > 0);
    lr.minPrice = prices.length ? Math.min(...prices) : null;
    lr.maxPrice = prices.length ? Math.max(...prices) : null;
  });
  return { rows, contractors, pres };
}

function buildCompareLineRows(data) {
  const pres = data.pre_invoices || [];
  const map = new Map();
  pres.forEach((pi) => {
    (pi.lines || []).forEach((line) => {
      const key = String(line.ردیف ?? line.id);
      if (!map.has(key)) {
        map.set(key, {
          key,
          row: line.ردیف,
          title: line["عنوان کالا"] || "—",
          unit: line["واحد"] || "",
          offers: [],
          selectedOfferIdx: 0,
          expert: defaultExpertName(data["کارشناس خرید"]),
          orderNumber: "",
          includeInBatch: false,
        });
      }
      map.get(key).offers.push({
        preinvoiceId: pi.id,
        lineId: line.id,
        contractor: pi["نام پیمانکار"],
        price: line["فی"],
        qty: line["تعداد"],
        total: line["جمع کل"],
        unit: line["واحد"],
        selected: line["منتخب مدیر"],
        expert: line["کارشناس ارجاع"],
        orderNumber: line["شماره دستور"],
        hasOrder: !!line.has_order,
        lineStatus: line.line_status,
      });
    });
  });
  const rows = [...map.values()].sort((a, b) => String(a.row).localeCompare(String(b.row), "fa"));
  rows.forEach((lr) => {
    const sel = lr.offers.findIndex((o) => o.selected);
    if (sel >= 0) lr.selectedOfferIdx = sel;
    const chosen = lr.offers[lr.selectedOfferIdx];
    if (chosen?.expert) lr.expert = chosen.expert;
    if (chosen?.orderNumber) lr.orderNumber = chosen.orderNumber;
    lr.hasOrder = lr.offers.some((o) => o.hasOrder);
    lr.awaitingOrder = !lr.hasOrder && lr.offers.some((o) => o.selected);
    lr.lineStatus = lr.offers.find((o) => o.hasOrder)?.lineStatus
      || (lr.awaitingOrder ? "در انتظار دستور" : chosen?.lineStatus)
      || (lr.hasOrder ? "دستور صادر" : "—");
  });
  return rows;
}

function reviewRowByKey(key) {
  return reviewState.rows.find((r) => r.key === key);
}

function contractorCoverage(pres, totalRows) {
  const map = {};
  pres.forEach((pi) => {
    const name = pi["نام پیمانکار"] || "—";
    const quoted = (pi.lines || []).length;
    map[name] = { quoted, total: totalRows, partial: quoted > 0 && quoted < totalRows };
  });
  return map;
}

function renderReviewCompare(data) {
  $("reviewFooter")?.classList.add("hidden");
  const { rows, contractors, pres } = buildCompareMatrix(data);
  const totalRows = rows.length;
  const coverage = contractorCoverage(pres, totalRows);
  const grandTotals = pres.map((p) => Number(p["جمع کل"] || 0)).filter((v) => v > 0);
  const minGrand = grandTotals.length ? Math.min(...grandTotals) : null;
  const comparable = pres.filter((pi) => {
    const cov = coverage[pi["نام پیمانکار"]];
    return cov && cov.quoted === totalRows;
  });
  const minComparable = comparable.map((p) => Number(p["جمع کل"] || 0)).filter((v) => v > 0);
  const minComparableGrand = minComparable.length ? Math.min(...minComparable) : null;

  const isAdminUser = typeof isAdmin === "function" && isAdmin();
  const winnerCards = pres.map((pi, ci) => {
    const name = pi["نام پیمانکار"] || "—";
    const cov = coverage[name] || { quoted: 0, total: totalRows, partial: false };
    const total = Number(pi["جمع کل"] || 0);
    const fullCoverage = cov.quoted === totalRows;
    const isBest = fullCoverage && minComparableGrand != null && total === minComparableGrand && minComparable.length > 1;
    const covBadge = cov.partial
      ? `<span class="badge badge-amber text-[10px]">${cov.quoted} از ${cov.total} ردیف</span>`
      : cov.quoted === 0
        ? `<span class="badge badge-slate text-[10px]">بدون قیمت</span>`
        : `<span class="badge badge-green text-[10px]">پوشش کامل</span>`;
    return `<div class="flex items-center justify-between p-3 rounded-lg border ${isBest ? "border-emerald-400 bg-emerald-50" : cov.partial ? "border-amber-200 bg-amber-50/40" : "border-slate-200 bg-white"}">
      <div>
        <p class="font-bold text-sm">${name}${isBest ? ' <span class="text-emerald-600 text-xs">★ ارزان‌ترین (پوشش کامل)</span>' : ""}</p>
        <p class="text-xs text-slate-500">تحویل: ${pi["زمان تحویل"] || "—"} · ${covBadge}</p>
        ${cov.partial ? `<p class="text-[10px] text-amber-700 mt-1">فقط ${cov.quoted} ردیف قیمت داده — برای مقایسه کل، پوشش کامل لازم است</p>` : ""}
        <div class="flex gap-2 mt-2">
          <button type="button" class="btn btn-ghost !py-0.5 !px-2 !text-[10px]" onclick="printInquiryPreInvoice(reviewState.data,${ci})">🖨 چاپ پیش‌فاکتور</button>
          ${isAdminUser && pi.id ? `<button type="button" class="admin-entity-edit-btn text-[10px] text-indigo-600 hover:underline" data-entity-type="pre_invoice" data-entity-id="${escAttr(pi.id)}" data-entity-label="پیش‌فاکتور">ویرایش</button>` : ""}
        </div>
      </div>
      <p class="text-lg font-bold ${isBest ? "text-emerald-700" : "text-slate-800"}">${fmtNum(total)}</p>
    </div>`;
  }).join("");

  const lineRows = rows.map((lr) => {
    const best = contractors.find((c) => lr.offers[c]?.price === lr.minPrice);
    const cells = contractors.map((c) => {
      const o = lr.offers[c];
      if (!o) return `<td class="text-center text-amber-600/80 p-2 text-[10px] font-medium">ندارد</td>`;
      const isMin = lr.minPrice != null && o.price === lr.minPrice && lr.minPrice !== lr.maxPrice;
      return `<td class="text-center p-2 text-xs ${isMin ? "bg-emerald-50 font-bold text-emerald-800" : ""}">${fmtNum(o.price)}</td>`;
    }).join("");
    return `<tr class="border-t">
      <td class="p-2 text-xs font-medium">${lr.row ?? "—"}</td>
      <td class="p-2 text-xs">${truncate(lr.title, 32)}</td>
      ${cells}
      <td class="p-2 text-xs text-emerald-700 font-medium">${best || "—"}</td>
    </tr>`;
  }).join("");

  const colHeaders = contractors.map((c) => `<th class="text-xs">${c}</th>`).join("");

  const partialCount = Object.values(coverage).filter((c) => c.partial).length;
  $("reviewBody").innerHTML = `
    ${partialCount ? `<div class="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-900">${partialCount} پیمانکار همه ردیف‌ها را قیمت‌گذاری نکرده‌اند — سلول «ندارد» یعنی آن پیمانکار برای آن ردیف پیشنهاد نداده.</div>` : ""}
    <p class="text-sm text-slate-600 mb-4">قیمت‌ها را مقایسه کنید. برای انتخاب پیمانکار و صدور دستور به مرحله بعد بروید.</p>
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-2 mb-5">${winnerCards}</div>
    <div class="overflow-x-auto border rounded-xl">
      <table class="data-table !text-xs w-full">
        <thead class="bg-slate-50"><tr><th>ردیف</th><th>کالا</th>${colHeaders}<th>پیشنهاد</th></tr></thead>
        <tbody>${lineRows || '<tr><td colspan="8" class="text-center py-8 text-slate-400">ردیفی نیست</td></tr>'}</tbody>
      </table>
    </div>
    <div class="mt-5 flex justify-end">
      <button type="button" onclick="setReviewStep('approve')" class="btn btn-primary">مرحله بعد: تایید و دستور ←</button>
    </div>`;
}

function renderReviewApprove(data) {
  const pendingRows = reviewState.rows.filter((lr) => !lr.hasOrder);
  const completedRows = reviewState.rows.filter((lr) => lr.hasOrder);
  const allComplete = completedRows.length > 0 && pendingRows.length === 0;
  const isPartial = completedRows.length > 0 && pendingRows.length > 0;

  const completedSection = completedRows.length ? `
    <div class="mb-5">
      <h4 class="font-bold text-sm text-emerald-900 mb-2">ردیف‌های تایید شده / دستور صادر شده (${completedRows.length})</h4>
      <div class="overflow-x-auto border border-emerald-200 rounded-xl bg-emerald-50/30">
        <table class="data-table !text-xs w-full">
          <thead class="bg-emerald-50"><tr>
            <th>ردیف</th><th>کالا</th><th>پیمانکار</th><th>کارشناس</th><th>شماره دستور</th><th>وضعیت</th>
          </tr></thead>
          <tbody>${completedRows.map((lr) => {
            const selected = lr.offers.find((o) => o.hasOrder) || lr.offers[lr.selectedOfferIdx] || lr.offers[0];
            return `<tr class="border-t border-emerald-100">
              <td class="p-2 font-medium">${lr.row ?? "—"}</td>
              <td class="p-2">${truncate(lr.title, 28)}</td>
              <td class="p-2 font-medium">${selected?.contractor || "—"}</td>
              <td class="p-2">${lr.expert || selected?.expert || "—"}</td>
              <td class="p-2 font-bold text-emerald-800">${lr.orderNumber || selected?.orderNumber || "—"}</td>
              <td class="p-2"><span class="badge badge-green">دستور صادر</span></td>
            </tr>`;
          }).join("")}</tbody>
        </table>
      </div>
    </div>` : "";

  const pendingCards = pendingRows.map((lr) => {
    const selected = lr.offers[lr.selectedOfferIdx] || lr.offers[0];
    const status = lr.lineStatus || (lr.awaitingOrder ? "در انتظار دستور" : "در انتظار تصمیم");
    const statusCls = status === "در انتظار دستور" ? "badge-blue" : "badge-slate";
    const rowKey = escAttr(lr.key);

    const offerOpts = lr.offers.map((o, oi) => {
      const isMin = o.price === Math.min(...lr.offers.map((x) => Number(x.price) || 0));
      return `<option value="${oi}" ${lr.selectedOfferIdx === oi ? "selected" : ""}>${o.contractor} — ${fmtNum(o.price)} ریال${isMin ? " ★" : ""}</option>`;
    }).join("");

    return `<div class="border rounded-xl p-4 bg-white shadow-sm ${lr.includeInBatch ? "ring-2 ring-indigo-200" : ""}">
      <div class="flex items-start gap-3 mb-3">
        <label class="flex items-center gap-2 cursor-pointer shrink-0 mt-1">
          <input type="checkbox" class="w-4 h-4" ${lr.includeInBatch ? "checked" : ""}
            onchange="(reviewRowByKey('${rowKey}')||{}).includeInBatch=this.checked">
          <span class="text-xs font-medium text-indigo-700">انتخاب</span>
        </label>
        <div class="flex-1 flex justify-between items-start gap-2">
          <div><span class="text-xs text-slate-500">ردیف ${lr.row}</span><h4 class="font-bold text-sm">${lr.title}</h4></div>
          <span class="badge ${statusCls}">${status}</span>
        </div>
      </div>
      <div class="grid sm:grid-cols-2 gap-3 mr-7">
        <div>
          <label class="text-xs text-slate-500 block mb-1">پیمانکار منتخب</label>
          <select class="input !text-sm" onchange="(reviewRowByKey('${rowKey}')||{}).selectedOfferIdx=+this.value">${offerOpts}</select>
        </div>
        <div>
          <label class="text-xs text-slate-500 block mb-1">کارشناس ارجاع</label>
          <select class="input !text-sm" onchange="(reviewRowByKey('${rowKey}')||{}).expert=this.value">${expertOptionsHtml(lr.expert, [lr.expert, data["کارشناس خرید"]])}</select>
        </div>
      </div>
      <div class="mt-3 mr-7">
        <label class="text-xs text-slate-500 block mb-1">شماره دستور</label>
        <input class="input !text-sm" placeholder="برای صدور دستور پر کنید" value="${escAttr(lr.orderNumber || "")}"
          oninput="(reviewRowByKey('${rowKey}')||{}).orderNumber=this.value">
      </div>
    </div>`;
  }).join("");

  const statusBanner = allComplete
    ? `<div class="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800">همه ${completedRows.length} ردیف دستور صادر شده — این استعلام از لیست انتظار خارج شد.</div>`
    : isPartial
      ? `<div class="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-900">
          <strong>تایید جزئی:</strong> ${completedRows.length} ردیف انجام شده · ${pendingRows.length} ردیف در انتظار
          ${data.pending_order_lines ? ` (${data.pending_order_lines} تاییدشده بدون دستور)` : ""}
        </div>`
      : "";

  $("reviewBody").innerHTML = `
    ${statusBanner}
    ${completedSection}
    ${pendingRows.length ? `
      <h4 class="font-bold text-sm mb-2">ردیف‌های در انتظار (${pendingRows.length})</h4>
      <p class="text-sm text-slate-600 mb-3">ردیف‌هایی که می‌خواهید الان پردازش شوند را تیک بزنید. بدون تیک → در لیست می‌مانند و بعداً می‌توانید برایشان دستور بزنید.</p>
      <div class="space-y-3">${pendingCards}</div>` : (
      !completedRows.length ? '<p class="text-center text-slate-400 py-8">ردیفی نیست</p>' : ""
    )}`;

  const footer = $("reviewFooter");
  if (pendingRows.length && footer) {
    footer.classList.remove("hidden");
    footer.innerHTML = `
      <textarea id="managerLineComment" class="input !text-sm w-full mb-3" rows="2" placeholder="توضیح مدیر (اختیاری)"></textarea>
      <p id="approveLinesError" class="text-red-500 text-sm mb-2"></p>
      <div class="flex flex-wrap gap-3 justify-between items-center">
        <button type="button" onclick="setReviewStep('compare')" class="btn btn-ghost text-sm">← بازگشت به مقایسه</button>
        <div class="flex flex-wrap gap-2">
          <button type="button" onclick="submitManagerLineApproval(false)" class="btn btn-secondary">ذخیره تایید (ردیف‌های تیک‌خورده)</button>
          <button type="button" onclick="submitManagerLineApproval(true)" class="btn btn-primary">صدور دستور (ردیف‌های تیک‌خورده)</button>
        </div>
      </div>`;
  } else if (footer) {
    footer.classList.add("hidden");
  }
}

function renderExpertInquiryDetail(data) {
  const sum = data.approval_summary || {};
  const hasDecision = sum.has_manager_decision;
  $("expertDetailTitle").textContent = `استعلام ${data["شماره استعلام"]} — خرید ${data["شماره درخواست خرید"]}`;

  const inqCtx = { entityType: "inquiry", entityId: String(data["شماره استعلام"]), label: "استعلام" };
  if (typeof setDetailEditContext === "function") setDetailEditContext(inqCtx);
  if (window.state) window.state.selectedRow = data;

  const infoFields = [
    ["وضعیت", data["وضعیت"] || data.manager_status],
    ["تاریخ استعلام", data["تاریخ استعلام"]],
    ["صادر کننده سند", sum.issuer || data["صادر کننده سند"]],
    ["کارشناس خرید", data["کارشناس خرید"]],
    ["انبار", data["انبار"]],
    ["مهلت استعلام", data["مهلت استعلام"]],
    ["نوع خرید", data["نوع خرید"]],
    ["درخواست دهنده", data["درخواست دهنده"]],
    ["رمز فوریت", data["رمز فوریت"]],
  ];
  const box = (label, val) => (typeof renderEditableInfoBox === "function"
    ? renderEditableInfoBox(label, val, inqCtx)
    : `<div class="p-3 bg-slate-50 rounded-xl"><span class="text-xs text-slate-500 block">${label}</span><strong>${val || "—"}</strong></div>`);
  const infoGrid = `<div class="grid sm:grid-cols-2 md:grid-cols-3 gap-3 text-sm mb-5">${infoFields.map(([k, v]) => box(k, v)).join("")}</div>`;

  const approvalBlock = hasDecision ? `
    <div class="mb-5 p-4 border border-emerald-200 bg-emerald-50 rounded-xl">
      <h4 class="font-bold text-emerald-900 mb-3">نتیجه بررسی مدیر</h4>
      <div class="grid sm:grid-cols-2 gap-3 text-sm">
        <p><span class="text-slate-600">تاییدکننده:</span> <strong>${sum.reviewer || "—"}</strong></p>
        <p><span class="text-slate-600">زمان تایید:</span> <strong>${sum.reviewed_at_display || "—"}</strong></p>
        <p class="sm:col-span-2"><span class="text-slate-600">توضیح مدیر:</span> ${sum.comment || "—"}</p>
      </div>
      ${(sum.approved_contractors || []).length ? `<p class="text-xs mt-3 text-emerald-800">پیمانکاران تاییدشده: ${sum.approved_contractors.map((c) => c["نام"]).join("، ")}</p>` : ""}
      ${(sum.rejected_contractors || []).length ? `<p class="text-xs mt-1 text-red-700">رد شده: ${sum.rejected_contractors.map((c) => c["نام"]).join("، ")}</p>` : ""}
    </div>` : `<div class="mb-5 p-4 border border-amber-200 bg-amber-50 rounded-xl text-sm text-amber-900">
      هنوز توسط مدیر بررسی و تایید نشده — در انتظار تصمیم مدیر
    </div>`;

  const lineRows = (sum.approved_lines || []).map((ln) => {
    const st = ln["وضعیت"] || "—";
    const stCls = st === "دستور صادر" ? "badge-green" : st === "در انتظار دستور" ? "badge-blue" : "badge-slate";
    return `<tr class="border-t">
      <td class="text-xs p-2">${ln["ردیف"] ?? "—"}</td>
      <td class="text-xs p-2">${ln["عنوان کالا"] || "—"}</td>
      <td class="text-xs p-2 font-medium">${ln["پیمانکار"] || "—"}</td>
      <td class="text-xs p-2">${fmtNum(ln["فی"])}</td>
      <td class="text-xs p-2">${ln["تعداد"] ?? "—"} ${ln["واحد"] || ""}</td>
      <td class="text-xs p-2">${ln["کارشناس ارجاع"] || "—"}</td>
      <td class="text-xs p-2 font-medium">${ln["شماره دستور"] || "—"}</td>
      <td class="p-2"><span class="badge ${stCls}">${st}</span></td>
    </tr>`;
  }).join("");

  const orderCell = (o, key, val) => {
    if (typeof openFieldEditPopup !== "function" || typeof isAdmin !== "function" || !isAdmin() || !o.id) {
      return `<td class="p-2">${val ?? "—"}</td>`;
    }
    return `<td class="p-2">${escAttr(val ?? "—")} <button type="button" class="field-edit-btn !text-[9px]"
      data-field-key="${escAttr(key)}"
      data-entity-type="order"
      data-entity-id="${escAttr(o.id)}"
      data-entity-label="دستور خرید">✏️</button></td>`;
  };
  const orderRows = (sum.orders || []).map((o) => `<tr class="border-t text-xs">
    ${orderCell(o, "شماره دستور", o["شماره دستور"])}
    ${orderCell(o, "عنوان کالا", o["عنوان کالا"])}
    ${orderCell(o, "نام پیمانکار", o["نام پیمانکار"])}
    ${orderCell(o, "کارشناس", o["کارشناس"])}
    ${orderCell(o, "تاریخ دستور", o["تاریخ دستور"])}
    ${orderCell(o, "مرحله فعلی", o["مرحله فعلی"] || o["وضعیت"])}
  </tr>`).join("");

  const { rows: compareRows, contractors: compareContractors, pres: comparePres } = buildCompareMatrix(data);
  const compareCoverage = contractorCoverage(comparePres, compareRows.length);
  const compareMatrix = compareRows.length ? `
    <div class="mb-5">
      <h4 class="font-bold text-sm mb-2">مقایسه قیمت پیمانکاران</h4>
      ${Object.values(compareCoverage).some((c) => c.partial) ? `<p class="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2 mb-2">برخی پیمانکاران همه ردیف‌ها را قیمت‌گذاری نکرده‌اند — «ندارد» یعنی پیشنهادی برای آن ردیف ثبت نشده.</p>` : ""}
      <div class="overflow-x-auto border rounded-xl">
        <table class="data-table !text-xs w-full">
          <thead class="bg-slate-50"><tr>
            <th>ردیف</th><th>کالا</th>
            ${compareContractors.map((c) => {
              const cov = compareCoverage[c];
              const badge = cov?.partial ? ` <span class="text-amber-600">(${cov.quoted}/${cov.total})</span>` : "";
              return `<th>${c}${badge}</th>`;
            }).join("")}
          </tr></thead>
          <tbody>${compareRows.map((lr) => {
            const cells = compareContractors.map((c) => {
              const o = lr.offers[c];
              if (!o) return `<td class="text-center text-amber-600/80 p-2">ندارد</td>`;
              const isMin = lr.minPrice != null && o.price === lr.minPrice && lr.minPrice !== lr.maxPrice;
              return `<td class="text-center p-2 ${isMin ? "bg-emerald-50 font-bold text-emerald-800" : ""}">${fmtNum(o.price)}</td>`;
            }).join("");
            return `<tr class="border-t"><td class="p-2">${lr.row ?? "—"}</td><td class="p-2">${truncate(lr.title, 28)}</td>${cells}</tr>`;
          }).join("")}</tbody>
        </table>
      </div>
    </div>` : "";

  const isAdminUser = typeof isAdmin === "function" && isAdmin();
  const preCompare = (data.pre_invoices || []).map((pi, ci) => {
    const cov = compareCoverage[pi["نام پیمانکار"]] || {};
    const covNote = cov.partial ? ` · ${cov.quoted} از ${cov.total} ردیف` : cov.quoted === compareRows.length && compareRows.length ? " · پوشش کامل" : "";
    return `
    <div class="border rounded-lg p-3 text-xs ${pi["وضعیت مدیر"] === "تایید شده" ? "border-emerald-300 bg-emerald-50/50" : pi["وضعیت مدیر"] === "رد شده" ? "border-red-200 bg-red-50/50" : ""}">
      <div class="flex justify-between items-start gap-2">
        <div>
          <p class="font-bold">${pi["نام پیمانکار"]}</p>
          <p class="text-slate-500">جمع: ${fmtNum(pi["جمع کل"])} · وضعیت: ${pi["وضعیت مدیر"] || "در انتظار"}${covNote}</p>
        </div>
        <div class="flex flex-col items-end gap-1 shrink-0">
          <button type="button" class="btn btn-ghost !py-0.5 !px-1.5 !text-[10px]" onclick="printInquiryPreInvoiceFromDetail(${ci})">🖨 چاپ</button>
          ${isAdminUser ? `<button type="button" class="admin-entity-edit-btn text-[10px] text-indigo-600 hover:underline" data-entity-type="pre_invoice" data-entity-id="${escAttr(pi.id)}" data-entity-label="پیش‌فاکتور">ویرایش</button>` : ""}
        </div>
      </div>
    </div>`;
  }).join("");

  const adminInquiryBtn = isAdminUser
    ? `<div class="mb-4 flex justify-end"><button type="button" class="admin-entity-edit-btn btn btn-ghost !py-1.5 !text-xs" data-entity-type="inquiry" data-entity-id="${escAttr(data["شماره استعلام"])}" data-entity-label="استعلام">✏️ ویرایش استعلام (مدیر سیستم)</button></div>`
    : "";

  $("expertDetailBody").innerHTML = `
    ${adminInquiryBtn}
    ${infoGrid}
    ${approvalBlock}
    ${hasDecision && lineRows ? `<div class="mb-5">
      <h4 class="font-bold text-sm mb-2">ردیف‌های تاییدشده توسط مدیر</h4>
      <div class="overflow-x-auto border rounded-xl">
        <table class="data-table !text-xs w-full">
          <thead class="bg-slate-50"><tr>
            <th>ردیف</th><th>کالا</th><th>پیمانکار منتخب</th><th>فی</th><th>تعداد</th><th>کارشناس ارجاع</th><th>شماره دستور</th><th>وضعیت</th>
          </tr></thead>
          <tbody>${lineRows}</tbody>
        </table>
      </div>
    </div>` : ""}
    ${orderRows ? `<div class="mb-5">
      <h4 class="font-bold text-sm mb-2">دستورات صادرشده</h4>
      <div class="overflow-x-auto border rounded-xl">
        <table class="data-table !text-xs w-full">
          <thead class="bg-slate-50"><tr>
            <th>شماره دستور</th><th>کالا</th><th>پیمانکار</th><th>کارشناس</th><th>تاریخ دستور</th><th>مرحله</th>
          </tr></thead>
          <tbody>${orderRows}</tbody>
        </table>
      </div>
    </div>` : ""}
    ${compareMatrix}
    <div>
      <h4 class="font-bold text-sm mb-2">پیش‌فاکتورهای ارسالی</h4>
      <div class="grid sm:grid-cols-2 md:grid-cols-3 gap-2">${preCompare}</div>
    </div>`;
}

async function submitManagerLineApproval(issueOrders = true) {
  const data = reviewState.data;
  if (!data) return;
  const errEl = $("approveLinesError");
  if (errEl) errEl.textContent = "";

  const editableRows = reviewState.rows.filter((lr) => !lr.hasOrder && lr.includeInBatch);
  if (!editableRows.length) {
    if (errEl) errEl.textContent = "حداقل یک ردیف در انتظار را تیک بزنید";
    return;
  }
  const lines = editableRows.map((lr) => {
    const offer = lr.offers[lr.selectedOfferIdx];
    const orderNumber = (lr.orderNumber || "").trim();
    const defer = issueOrders ? !orderNumber : true;
    return {
      row: lr.row,
      line_id: offer?.lineId,
      preinvoice_id: offer?.preinvoiceId,
      "کارشناس": lr.expert,
      "شماره دستور": issueOrders && !defer ? orderNumber : "",
      defer_order: defer,
      "عنوان کالا": lr.title,
    };
  });

  for (const ln of lines) {
    if (!ln["کارشناس"]) {
      if (errEl) errEl.textContent = "کارشناس ارجاع برای هر ردیف الزامی است";
      return;
    }
    if (!ln.line_id || !ln.preinvoice_id) {
      if (errEl) errEl.textContent = "انتخاب پیمانکار برای هر ردیف الزامی است";
      return;
    }
  }

  if (issueOrders) {
    const toIssue = lines.filter((ln) => ln["شماره دستور"]);
    if (!toIssue.length) {
      if (errEl) errEl.textContent = "برای ردیف‌های تیک‌خورده شماره دستور وارد کنید";
      return;
    }
    const skipped = lines.length - toIssue.length;
    const msg = skipped
      ? `دستور برای ${toIssue.length} ردیف صادر شود؟ (${skipped} ردیف تیک‌خورده بدون شماره — فقط تایید می‌شوند)`
      : `دستور برای ${toIssue.length} ردیف صادر شود؟`;
    if (!confirm(msg)) return;
  } else if (!confirm(`تایید ${lines.length} ردیف تیک‌خورده (بدون صدور دستور) ذخیره شود؟`)) {
    return;
  }

  showLoading(issueOrders ? "در حال صدور دستورها..." : "در حال ذخیره تایید...");
  try {
    const res = await api(`/inquiries/${data["شماره استعلام"]}/approve-lines`, {
      method: "POST",
      body: JSON.stringify({
        lines,
        issue_orders: issueOrders,
        comment: $("managerLineComment")?.value?.trim() || "",
      }),
    });
    if (issueOrders && res.count > 0) {
      toast(`${res.count} دستور در «دستور خرید» ثبت شد`);
      closeReview();
      if (typeof setView === "function") {
        setView("orders");
      } else if (typeof loadViewData === "function") {
        loadViewData();
      }
    } else if (issueOrders) {
      toast("تایید ذخیره شد — برای ثبت در دستور خرید شماره دستور وارد کنید");
      await openInquiryReview(data["شماره استعلام"], "approve");
      if (typeof loadViewData === "function") loadViewData();
    } else {
      toast(`${res.saved} ردیف تایید شد — برای دستور خرید بعداً شماره وارد و «صدور دستور» بزنید`);
      await openInquiryReview(data["شماره استعلام"], "approve");
      if (typeof loadViewData === "function") loadViewData();
    }
  } catch (e) {
    if (errEl) errEl.textContent = e.message;
  } finally {
    hideLoading();
  }
}

function closeCompare() { closeReview(); }
function closeApprove() { closeReview(); }
function closeExpertDetail() { $("expertDetailModal")?.classList.add("hidden"); }

async function reviewPreinvoice(id, action) {
  const comment = document.getElementById(`comment-${id}`)?.value?.trim() || "";
  if (!confirm(action === "approve" ? "پیمانکار تایید شود؟" : "پیمانکار رد شود؟")) return;
  showLoading("در حال ثبت...");
  try {
    await api(`/inquiries/preinvoice/${id}/${action}`, {
      method: "PATCH",
      body: JSON.stringify({ comment }),
    });
    toast(action === "approve" ? "پیمانکار تایید شد" : "پیمانکار رد شد");
    const inqNum = $("reviewTitle")?.textContent.match(/استعلام (\S+)/)?.[1];
    if (inqNum) openInquiryReview(inqNum, "approve");
    if (typeof loadViewData === "function") loadViewData();
  } catch (e) { alert(e.message); }
  finally { hideLoading(); }
}

window.openIssue = openIssue;
window.openCompare = openCompare;
window.openApprove = openApprove;
window.openInquiryReview = openInquiryReview;
window.setReviewStep = setReviewStep;
window.closeReview = closeReview;
window.openExpertInquiryDetail = openExpertInquiryDetail;
window.openInquiryStatus = openExpertInquiryDetail;
window.submitIssue = submitIssue;
window.closeIssue = closeIssue;
window.closeCompare = closeCompare;
window.closeApprove = closeApprove;
window.closeExpertDetail = closeExpertDetail;
window.addPreInvoiceCard = addPreInvoiceCard;
window.lookupPurchaseForIssue = lookupPurchaseForIssue;
window.confirmIssueHeader = confirmIssueHeader;
window.editIssueHeader = editIssueHeader;
window.openLastPurchaseCompare = openLastPurchaseCompare;
window.closeLastPurchaseCompare = closeLastPurchaseCompare;
window.setCardVatEnabled = setCardVatEnabled;
window.onPreInvoiceLineInput = onPreInvoiceLineInput;
window.onPreInvoiceDiscountInput = onPreInvoiceDiscountInput;
window.submitManagerLineApproval = submitManagerLineApproval;
window.reviewRowByKey = reviewRowByKey;
window.printIssueCompare = printIssueCompare;
window.printPreInvoiceCard = printPreInvoiceCard;
window.printInquiryCompare = printInquiryCompare;
window.printInquiryCompareFromDetail = printInquiryCompareFromDetail;
window.printInquiryCompareFromReview = printInquiryCompareFromReview;
window.printInquiryPreInvoiceFromDetail = printInquiryPreInvoiceFromDetail;
window.printInquiryPreInvoice = printInquiryPreInvoice;
window.exportIssueCompareExcel = exportIssueCompareExcel;
window.exportInquiryCompareExcelFromDetail = exportInquiryCompareExcelFromDetail;
window.exportInquiryCompareExcelFromReview = exportInquiryCompareExcelFromReview;
window.scheduleIssueDraftSave = scheduleIssueDraftSave;

window.addEventListener("beforeunload", () => {
  if (!$("issueModal")?.classList.contains("hidden")) saveIssueDraft();
});

function truncate(t, n = 45) {
  if (!t) return "—";
  const s = String(t);
  return s.length > n ? s.slice(0, n) + "…" : s;
}