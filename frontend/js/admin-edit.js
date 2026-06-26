/** ویرایش تک‌فیلدی سوپر‌یوزر — آیکون مداد کنار فیلدها */

function $el(id) {
  return document.getElementById(id);
}

const FIELD_EDIT_SKIP = new Set([
  "شماره", "شماره خرید", "purchase_lines", "line_count", "pre_invoices", "lines",
  "approval_summary", "has_orders", "order_count", "fully_locked", "locked",
  "partially_approved", "has_manager_decision", "manager_status", "manager_reviewer",
  "manager_reviewed_at", "pending_order_lines", "pending_row_decisions", "total_rows",
  "lines_with_orders", "preinvoice_count", "pending_review", "approved_count",
  "rejected_count", "order_id", "order_stage", "id", "preinvoice_id",
  "has_local_inquiry", "local_inquiry_number", "inquiry_approved", "وضعیت فعلی خرید",
  "updated_at", "updated_by", "created_at", "created_by", "overrides_json", "_source",
  "has_order", "line_status",
]);

let detailEditContext = null;
let fieldEditState = null;

function setDetailEditContext(ctx) {
  detailEditContext = ctx;
}

function buildDetailEditContext(row) {
  if (!row || typeof isAdmin !== "function" || !isAdmin()) return null;
  const cfg = window.ADMIN_ENTITY_VIEWS?.[window.state?.view];
  if (cfg?.idKey && row[cfg.idKey]) {
    return { entityType: cfg.type, entityId: String(row[cfg.idKey]), label: cfg.label };
  }
  if (row["شماره استعلام"]) {
    return { entityType: "inquiry", entityId: String(row["شماره استعلام"]), label: "استعلام" };
  }
  if (row.id && row["شماره دستور"]) {
    return { entityType: "order", entityId: String(row.id), label: "دستور خرید" };
  }
  if (row.id && row["شماره تحویل"]) {
    return { entityType: "delivery", entityId: String(row.id), label: "تحویل" };
  }
  if (row.id && row["نام پیمانکار"] && row["شماره پیش فاکتور"]) {
    return { entityType: "pre_invoice", entityId: String(row.id), label: "پیش‌فاکتور" };
  }
  if (row.id && row["عنوان کالا"] && row.preinvoice_id) {
    return { entityType: "pre_invoice_line", entityId: String(row.id), label: "ردیف پیش‌فاکتور" };
  }
  if (row["شماره"]) {
    return { entityType: "purchase", entityId: String(row["شماره"]), label: "درخواست خرید" };
  }
  return null;
}

function escFieldText(v) {
  return String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escFieldAttr(v) {
  return String(v ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fieldEditBtnHtml(fieldKey, ctx) {
  return `<button type="button" class="field-edit-btn shrink-0" title="ویرایش"
    data-field-key="${escFieldAttr(fieldKey)}"
    data-entity-type="${escFieldAttr(ctx.entityType)}"
    data-entity-id="${escFieldAttr(ctx.entityId)}"
    data-entity-label="${escFieldAttr(ctx.label)}">✏️</button>`;
}

function adminEntityEditBtnHtml(entityType, entityId, label, extraClass = "") {
  if (!entityType || entityId == null || entityId === "") return "";
  const cls = ["admin-entity-edit-btn", extraClass].filter(Boolean).join(" ");
  return `<button type="button" class="${cls}"
    data-entity-type="${escFieldAttr(entityType)}"
    data-entity-id="${escFieldAttr(entityId)}"
    data-entity-label="${escFieldAttr(label)}">ویرایش</button>`;
}

function readFieldEditBtn(btn) {
  if (!btn) return null;
  const ds = btn.dataset || {};
  return {
    fieldKey: ds.fieldKey || btn.getAttribute("data-field-key") || "",
    entityType: ds.entityType || btn.getAttribute("data-entity-type") || "",
    entityId: ds.entityId || btn.getAttribute("data-entity-id") || "",
    entityLabel: ds.entityLabel || btn.getAttribute("data-entity-label") || "",
  };
}

function handleFieldEditClick(e, btn) {
  e?.stopPropagation?.();
  e?.preventDefault?.();
  const { fieldKey, entityType, entityId, entityLabel } = readFieldEditBtn(btn);
  openFieldEditPopup(e, fieldKey, entityType, entityId, entityLabel);
}

function renderEditableFieldRow(key, value, ctxOverride) {
  const display = value == null || String(value).trim() === "" ? "—" : String(value);
  const ctx = ctxOverride || detailEditContext;
  const canEdit = typeof isAdmin === "function" && isAdmin() && ctx
    && !FIELD_EDIT_SKIP.has(key) && !key.startsWith("_");
  const pencil = canEdit ? fieldEditBtnHtml(key, ctx) : "";
  return `<div class="detail-field-row grid grid-cols-[1fr_auto_auto] gap-2 items-start py-2.5 border-b border-slate-100">
    <span class="text-slate-500 text-sm">${escFieldText(key)}</span>
    <span class="text-sm break-words text-left">${escFieldText(display)}</span>
    ${pencil}
  </div>`;
}

function renderEditableInfoBox(label, value, ctxOverride) {
  const ctx = ctxOverride || detailEditContext;
  const canEdit = typeof isAdmin === "function" && isAdmin() && ctx
    && !FIELD_EDIT_SKIP.has(label) && !label.startsWith("_");
  const pencil = canEdit
    ? fieldEditBtnHtml(label, ctx).replace("shrink-0", "!text-[10px] !p-0.5 shrink-0")
    : "";
  return `<div class="p-3 bg-slate-50 rounded-xl relative">
    <span class="text-xs text-slate-500 block">${escFieldText(label)}</span>
    <div class="flex justify-between items-start gap-1 mt-0.5">
      <strong class="text-sm break-words">${escFieldText(value ?? "—")}</strong>
      ${pencil}
    </div>
  </div>`;
}

function openFieldEditPopup(e, fieldKey, entityType, entityId, entityLabel) {
  e?.stopPropagation?.();
  e?.preventDefault?.();
  if (!fieldKey || !entityType || !entityId) {
    if (typeof toast === "function") toast("ویرایش این فیلد ممکن نیست — شناسه رکورد یافت نشد");
    return;
  }
  fieldEditState = { fieldKey, entityType, entityId, entityLabel };
  const row = window.state?.selectedRow || window.savedInquiryState?.data || {};
  const current = row[fieldKey];
  const titleEl = $el("fieldEditTitle");
  const subEl = $el("fieldEditSubtitle");
  const modalEl = $el("fieldEditModal");
  const wrap = $el("fieldEditInputWrap");
  if (!titleEl || !modalEl || !wrap) {
    if (typeof toast === "function") toast("خطا: مودال ویرایش بارگذاری نشده — صفحه را رفرش کنید");
    return;
  }
  titleEl.textContent = `ویرایش: ${fieldKey}`;
  if (subEl) subEl.textContent = `${entityLabel || entityType} · ${entityId}`;
  const isLong = fieldKey === "توضیحات" || fieldKey === "شرح" || fieldKey === "مشخصه فنی"
    || String(current ?? "").length > 80;
  wrap.innerHTML = isLong
    ? '<textarea id="fieldEditValue" class="input min-h-[5rem] resize-y w-full" rows="4"></textarea>'
    : '<input id="fieldEditValue" class="input w-full" type="text">';
  const el = $el("fieldEditValue");
  if (el) el.value = current == null ? "" : String(current);
  $el("fieldEditError")?.classList.add("hidden");
  modalEl.classList.remove("hidden");
  document.body.classList.add("field-edit-open");
  el?.focus();
}

function closeFieldEdit() {
  $el("fieldEditModal")?.classList.add("hidden");
  document.body.classList.remove("field-edit-open");
  fieldEditState = null;
  const wrap = $el("fieldEditInputWrap");
  if (wrap) wrap.innerHTML = '<input id="fieldEditValue" class="input w-full" type="text">';
}

async function saveFieldEdit() {
  if (!fieldEditState) return;
  const val = $el("fieldEditValue")?.value ?? "";
  const { fieldKey, entityType, entityId } = fieldEditState;
  const errEl = $el("fieldEditError");
  showLoading("در حال ذخیره...");
  try {
    const payload = { [fieldKey]: val };
    if (entityType === "purchase") {
      await api(`/requests/${encodeURIComponent(entityId)}`, { method: "PATCH", body: JSON.stringify(payload) });
    } else {
      await api(`/admin/entities/${entityType}/${encodeURIComponent(entityId)}`, {
        method: "PATCH", body: JSON.stringify(payload),
      });
    }
    closeFieldEdit();
    toast("فیلد ذخیره شد");
    if (typeof reloadCurrentDetail === "function") await reloadCurrentDetail();
    if (typeof loadViewData === "function") loadViewData();
    if (entityType === "purchase" && typeof loadStats === "function") loadStats();
  } catch (e) {
    if (errEl) {
      errEl.textContent = e.message;
      errEl.classList.remove("hidden");
    }
  } finally {
    hideLoading();
  }
}

async function reloadCurrentDetail() {
  const ctx = detailEditContext || fieldEditState;
  if (!ctx) return;
  try {
    let full;
    if (ctx.entityType === "purchase") {
      full = await api(`/requests/detail/${encodeURIComponent(ctx.entityId)}`);
    } else if (ctx.entityType === "inquiry") {
      full = await api(`/inquiries/detail/${encodeURIComponent(ctx.entityId)}`);
    } else {
      full = await api(`/admin/entities/${ctx.entityType}/${encodeURIComponent(ctx.entityId)}`);
    }
    window.state.selectedRow = full;
    if (!$el("expertDetailModal")?.classList.contains("hidden") && typeof renderExpertInquiryDetail === "function") {
      if (typeof window.savedInquiryState !== "undefined") window.savedInquiryState.data = full;
      renderExpertInquiryDetail(full);
    } else if (!$el("reviewModal")?.classList.contains("hidden") && typeof openInquiryReview === "function") {
      await openInquiryReview(ctx.entityId, window.reviewState?.step || "compare");
    } else if (!$el("detailModal")?.classList.contains("hidden") && typeof renderDetailModal === "function") {
      renderDetailModal(full);
    }
  } catch { /* ignore */ }
}

window.setDetailEditContext = setDetailEditContext;
window.buildDetailEditContext = buildDetailEditContext;
window.renderEditableFieldRow = renderEditableFieldRow;
window.renderEditableInfoBox = renderEditableInfoBox;
window.handleFieldEditClick = handleFieldEditClick;
window.openFieldEditPopup = openFieldEditPopup;
window.closeFieldEdit = closeFieldEdit;
window.saveFieldEdit = saveFieldEdit;
window.reloadCurrentDetail = reloadCurrentDetail;

document.addEventListener("click", (e) => {
  const fieldBtn = e.target.closest?.(".field-edit-btn[data-field-key]");
  if (fieldBtn) {
    handleFieldEditClick(e, fieldBtn);
    return;
  }
  const adminBtn = e.target.closest?.(".admin-entity-edit-btn[data-entity-type][data-entity-id]");
  if (!adminBtn) return;
  e.stopPropagation();
  e.preventDefault();
  const { entityType, entityId, entityLabel } = readFieldEditBtn(adminBtn);
  if (typeof openAdminEntityEdit === "function") {
    openAdminEntityEdit(entityType, entityId, null, entityLabel || "");
  }
});

window.escFieldAttr = escFieldAttr;
window.escFieldText = escFieldText;
window.adminEntityEditBtnHtml = adminEntityEditBtnHtml;