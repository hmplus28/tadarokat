const ORDER_STAGE_SEQUENCE = [
  "دستور خرید",
  "سفارش",
  "ثبت پرداخت",
  "تبدیل وضعیت پرداخت",
  "تحویل",
];

const STAGE_REQUIRED_FIELDS = {
  "سفارش": ["شماره سفارش", "تاریخ سفارش"],
  "ثبت پرداخت": ["شماره پرداخت", "تاریخ ثبت پرداخت"],
  "تبدیل وضعیت پرداخت": ["تاریخ واریز"],
  "تحویل": ["شماره مجوز ورود", "تاریخ تحویل"],
};

const STAGE_VIEW_FIELDS = {
  "دستور خرید": ["شماره دستور", "تاریخ دستور", "عنوان کالا", "نام پیمانکار", "کارشناس"],
  "سفارش": ["شماره سفارش", "تاریخ سفارش"],
  "ثبت پرداخت": ["شماره پرداخت", "تاریخ ثبت پرداخت"],
  "تبدیل وضعیت پرداخت": ["تاریخ واریز"],
  "تحویل": ["شماره مجوز ورود", "تاریخ تحویل"],
};

const LEGACY_STAGE_MAP = { "رسید انبار": "تحویل", "بسته شده": "تحویل" };

const DATE_FIELDS = new Set([
  "تاریخ دستور", "تاریخ سفارش", "تاریخ ثبت پرداخت", "تاریخ واریز", "تاریخ تحویل",
]);

let orderEditId = null;
let orderStageState = { row: null, nextStage: null, complete: false, editStage: null, readonly: false };
let deliveryEditId = null;

function normalizeOrderStage(stage) {
  const s = String(stage || "دستور خرید").trim();
  return LEGACY_STAGE_MAP[s] || (ORDER_STAGE_SEQUENCE.includes(s) ? s : "دستور خرید");
}

function stageIndex(stage) {
  return ORDER_STAGE_SEQUENCE.indexOf(normalizeOrderStage(stage));
}

function nextStageToComplete(current) {
  const idx = stageIndex(current);
  if (idx < 0 || idx >= ORDER_STAGE_SEQUENCE.length - 1) return null;
  return ORDER_STAGE_SEQUENCE[idx + 1];
}

function isWorkflowComplete(stage) {
  return normalizeOrderStage(stage) === "تحویل";
}

function migrateOrderRow(row) {
  const r = { ...row };
  r["مرحله فعلی"] = normalizeOrderStage(r["مرحله فعلی"]);
  if (!r["شماره مجوز ورود"] && r["شماره تحویل"]) {
    r["شماره مجوز ورود"] = r["شماره تحویل"];
  }
  return r;
}

function canManageOrders() {
  return typeof isExpert === "function" && isExpert();
}

function canIssueOrder() {
  return typeof isManager === "function" && isManager();
}

function wfEsc(val) {
  return String(val ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function stageIsEditable(stageName) {
  return stageName !== "دستور خرید" && !!STAGE_REQUIRED_FIELDS[stageName];
}

function isStageDone(orderStage, checkStage) {
  return stageIndex(normalizeOrderStage(orderStage)) >= stageIndex(checkStage);
}

function renderStageFieldInputs(stageName, row, idPrefix = "orderStageField") {
  const fields = STAGE_REQUIRED_FIELDS[stageName] || [];
  return fields.map((f, i) => {
    const isDate = DATE_FIELDS.has(f);
    const cls = isDate ? "input mt-1 jalali-date" : "input mt-1";
    const extra = isDate ? " data-jdp" : "";
    const val = row[f] != null ? wfEsc(row[f]) : "";
    const inputId = idPrefix === "orderStageField" ? `orderStageField_${i}` : `${idPrefix}_${stageName}_${i}`;
    return `<div class="${fields.length === 1 ? "col-span-2" : ""}">
      <label class="text-xs text-slate-500">${f} *</label>
      <input id="${inputId}" class="${cls}"${extra} data-field="${wfEsc(f)}" value="${val}" placeholder="${wfEsc(f)}">
    </div>`;
  }).join("");
}

function renderReadonlyStageBlock(title, fields, row, stageName) {
  const editable = !orderStageState.readonly && canManageOrders() && stageIsEditable(stageName) && isStageDone(row["مرحله فعلی"], stageName);
  const isEditing = orderStageState.editStage === stageName;

  if (isEditing) {
    return `<div class="p-4 rounded-xl border-2 border-amber-300 bg-amber-50/50">
      <div class="flex justify-between items-center mb-3">
        <p class="text-sm font-bold text-amber-900">ویرایش: ${title}</p>
        <button type="button" class="text-xs text-slate-600 hover:underline" onclick="cancelEditOrderStage()">انصراف</button>
      </div>
      <div class="grid grid-cols-2 gap-3">${renderStageFieldInputs(stageName, row, "orderEditField")}</div>
      <p id="orderStageError" class="text-red-500 text-sm mt-2"></p>
    </div>`;
  }

  const items = fields.map((f) => {
    const v = row[f];
    if (v == null || String(v).trim() === "" || String(v).toLowerCase() === "nan") return "";
    return `<div class="text-xs"><span class="text-slate-500">${f}:</span> <strong>${wfEsc(v)}</strong></div>`;
  }).filter(Boolean).join("");
  if (!items && stageName === "دستور خرید") return "";

  const editBtn = editable
    ? `<button type="button" class="text-xs text-indigo-600 font-semibold hover:underline" onclick="startEditOrderStage('${stageName}')">ویرایش</button>`
    : "";

  return `<div class="p-3 rounded-xl bg-slate-50 border border-slate-200">
    <div class="flex justify-between items-center mb-2">
      <p class="text-xs font-bold text-slate-700">${title} ✓</p>
      ${editBtn}
    </div>
    <div class="grid sm:grid-cols-2 gap-2">${items || '<p class="text-xs text-slate-400">—</p>'}</div>
  </div>`;
}

function renderOrderStageForm(row, nextStage) {
  return `<div class="p-4 rounded-xl border-2 border-indigo-200 bg-indigo-50/40">
    <p class="text-sm font-bold text-indigo-900 mb-3">مرحله بعد: ${nextStage}</p>
    <div class="grid grid-cols-2 gap-3">${renderStageFieldInputs(nextStage, row)}</div>
    <div class="mt-3">
      <label class="text-xs text-slate-500">توضیح (اختیاری)</label>
      <textarea id="orderStageNotes" class="input mt-1 text-sm" rows="2" placeholder="یادداشت این مرحله"></textarea>
    </div>
    <p id="orderStageError" class="text-red-500 text-sm mt-2"></p>
  </div>`;
}

function initOrderStagePickers() {
  setTimeout(() => {
    if (window.jalaliDatepicker) {
      try { jalaliDatepicker.startWatch({ time: false, separatorChars: { date: "/" }, zIndex: 9999 }); } catch { /* */ }
    }
  }, 50);
}

function startEditOrderStage(stageName) {
  if (!canManageOrders() || !orderStageState.row) return;
  orderStageState.editStage = stageName;
  renderOrderStageModalContent(orderStageState.row);
  initOrderStagePickers();
}

function cancelEditOrderStage() {
  orderStageState.editStage = null;
  if (orderStageState.row) renderOrderStageModalContent(orderStageState.row);
}

function renderStagesOnlyTimeline(stages, meta = {}) {
  return (stages || []).map((st, i) => {
    const done = st.status === "done";
    const current = st.status === "current";
    const dotCls = done ? "bg-emerald-500 text-white" : current ? "bg-indigo-500 text-white ring-4 ring-indigo-100" : "bg-slate-200 text-slate-500";
    const cardCls = done ? "border-emerald-200 bg-emerald-50/40" : current ? "border-indigo-300 bg-indigo-50/50" : "border-slate-200 bg-slate-50";
    const details = Object.entries(st.details || {}).filter(([, v]) => v != null && String(v).trim())
      .map(([k, v]) => `<span class="text-[10px] text-slate-600"><span class="text-slate-400">${wfEsc(k)}:</span> ${wfEsc(v)}</span>`).join(" · ");
    return `<div class="flex gap-3 items-start">
      <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${dotCls}">${i + 1}</div>
      <div class="flex-1 p-3 rounded-xl border ${cardCls}">
        <p class="text-sm font-bold text-slate-800">${wfEsc(st.stage)}</p>
        ${details ? `<p class="mt-1">${details}</p>` : (current ? '<p class="text-xs text-indigo-600 mt-1">در حال انجام</p>' : done ? "" : '<p class="text-xs text-slate-400 mt-1">در انتظار</p>')}
      </div>
    </div>`;
  }).join("");
}

function renderOrderStageModalContent(row) {
  const r = migrateOrderRow(row);
  const current = r["مرحله فعلی"];
  const next = nextStageToComplete(current);
  const complete = isWorkflowComplete(current);
  const editing = orderStageState.editStage;
  orderStageState = { ...orderStageState, row: r, nextStage: next, complete };

  const body = $("orderStageBody");
  if (!body) return;

  if (orderStageState.stagesOnly && orderStageState.stageTimeline) {
    $("orderStageTitle").textContent = "مراحل خرید ثبت‌شده";
    $("orderStageProgress").textContent = metaLine(orderStageState.stageMeta);
    body.innerHTML = `<div class="space-y-2">${renderStagesOnlyTimeline(orderStageState.stageTimeline)}</div>`;
    $("orderStageSubmitBtn")?.classList.add("hidden");
    return;
  }

  const completedStages = ORDER_STAGE_SEQUENCE.slice(0, stageIndex(current) + 1);
  const historyHtml = completedStages
    .map((st) => renderReadonlyStageBlock(st, STAGE_VIEW_FIELDS[st] || [], r, st))
    .join("");

  $("orderStageTitle").textContent = orderStageState.readonly
    ? "مراحل خرید (فقط مشاهده)"
    : editing
      ? `ویرایش مرحله «${editing}»`
      : complete ? "گردش دستور (خاتمه یافته)" : "ثبت مرحله بعدی";
  $("orderStageProgress").textContent = complete
    ? "فرآیند خاتمه یافته — با دکمه ویرایش می‌توانید مراحل ثبت‌شده را اصلاح کنید"
    : `آخرین مرحله: ${current} · مرحله بعد: ${next}`;

  const workflowNote = orderStageState.workflowNote
    ? `<div class="p-3 mb-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900">${orderStageState.workflowNote}</div>`
    : "";

  body.innerHTML = orderStageState.readonly
    ? `${workflowNote}<div class="space-y-2 mb-2">${historyHtml || renderReadonlyStageBlock("دستور خرید", STAGE_VIEW_FIELDS["دستور خرید"], r, "دستور خرید")}</div>
       ${complete ? `<div class="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800">فرآیند تکمیل شده</div>` : ""}`
    : `
    ${historyHtml || renderReadonlyStageBlock("دستور خرید", STAGE_VIEW_FIELDS["دستور خرید"], r, "دستور خرید")}
    ${!editing && !complete && next ? renderOrderStageForm(r, next) : ""}
    ${complete && !editing ? `<div class="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800">خاتمه — رکورد در بخش <strong>تحویل‌ها</strong> ثبت شده است.</div>` : ""}`;

  const submitBtn = $("orderStageSubmitBtn");
  if (submitBtn) {
    const showSubmit = !orderStageState.readonly && (editing || (!complete && next));
    submitBtn.classList.toggle("hidden", !showSubmit);
    if (editing) {
      submitBtn.textContent = `ذخیره ویرایش «${editing}»`;
    } else if (next === "تحویل") {
      submitBtn.textContent = "خاتمه";
    } else {
      submitBtn.textContent = `ثبت «${next}» و ادامه`;
    }
  }
}

function openIssueOrderModal(inquiryNumber, preinvoiceId, contractorName) {
  if (!canIssueOrder()) return;
  $("issueOrderInquiry").value = inquiryNumber || "";
  $("issueOrderPreinvoiceId").value = preinvoiceId || "";
  $("issueOrderContractor").textContent = contractorName || "—";
  $("issueOrderNumber").value = "";
  $("issueOrderDate").value = "";
  $("issueOrderNotes").value = "";
  $("issueOrderError").textContent = "";
  $("issueOrderModal").classList.remove("hidden");
  setTimeout(() => {
    if (window.jalaliDatepicker) {
      try { jalaliDatepicker.startWatch({ time: false, separatorChars: { date: "/" }, zIndex: 9999 }); } catch { /* */ }
    }
  }, 50);
}

function closeIssueOrderModal() {
  $("issueOrderModal")?.classList.add("hidden");
}

async function submitIssueOrder() {
  const orderNumber = $("issueOrderNumber").value.trim();
  const inquiryNumber = $("issueOrderInquiry").value.trim();
  const preinvoiceId = $("issueOrderPreinvoiceId").value.trim();
  const errEl = $("issueOrderError");
  if (!orderNumber) {
    errEl.textContent = "شماره دستور الزامی است";
    return;
  }
  showLoading("در حال صدور دستور...");
  try {
    await api("/orders", {
      method: "POST",
      body: JSON.stringify({
        "شماره دستور": orderNumber,
        "شماره استعلام": inquiryNumber,
        preinvoice_id: preinvoiceId,
        "تاریخ دستور": $("issueOrderDate").value.trim() || undefined,
        "توضیحات": $("issueOrderNotes").value.trim(),
      }),
    });
    closeIssueOrderModal();
    toast(`دستور ${orderNumber} صادر شد و به کارتابل کارشناس ارسال شد`);
    if (inquiryNumber && typeof openInquiryReview === "function") openInquiryReview(inquiryNumber);
    if (typeof loadViewData === "function") loadViewData();
  } catch (e) {
    errEl.textContent = e.message;
  } finally {
    hideLoading();
  }
}

function metaLine(meta) {
  if (!meta) return "";
  const parts = [];
  if (meta.inquiry_number) parts.push(`استعلام ${meta.inquiry_number}`);
  if (meta.purchase_number) parts.push(`خرید ${meta.purchase_number}`);
  if (meta["عنوان کالا"]) parts.push(meta["عنوان کالا"]);
  return parts.join(" · ") || "—";
}

async function openWarehousePurchaseStages(inquiryNumber) {
  if (!inquiryNumber) return;
  showLoading("در حال بارگذاری مراحل...");
  try {
    const data = await api(`/warehouse/purchases/${encodeURIComponent(inquiryNumber)}/stages`);
    $("orderStageNumber").textContent = data["شماره دستور"] || "—";
    $("orderStageInquiry").textContent = data.inquiry_number || inquiryNumber;
    $("orderStageWarehouse").textContent = data.warehouse || window.state?.user?.warehouse || "—";
    orderEditId = null;
    orderStageState = {
      row: null,
      nextStage: null,
      complete: false,
      editStage: null,
      readonly: true,
      stagesOnly: true,
      stageTimeline: data.stages || [],
      stageMeta: data,
    };
    renderOrderStageModalContent({});
    $("orderStageModal").classList.remove("hidden");
  } catch (e) {
    toast(e.message);
  } finally {
    hideLoading();
  }
}

async function openOrderStageModal(orderId, options = {}) {
  const readonly = !!options.readonly || (typeof isReadOnly === "function" && isReadOnly());
  if (!readonly && !canManageOrders()) return;
  const row = options.row || window.state.data.find((r) => String(r.id) === String(orderId));
  if (!row) return;
  if (readonly && typeof isWarehouse === "function" && isWarehouse()) {
    const inq = row["شماره استعلام"];
    if (inq) {
      await openWarehousePurchaseStages(inq);
      return;
    }
  }
  orderEditId = readonly ? null : orderId;
  $("orderStageNumber").textContent = row["شماره دستور"] || "—";
  $("orderStageInquiry").textContent = row["شماره استعلام"] || "—";
  $("orderStageWarehouse").textContent = row["انبار"] || "—";
  orderStageState = {
    row: null, nextStage: null, complete: false, editStage: null, readonly, stagesOnly: false,
    workflowNote: options.workflowNote || "", workflowSource: options.workflowSource || "",
  };
  renderOrderStageModalContent(row);
  $("orderStageModal").classList.remove("hidden");
  if (!readonly) initOrderStagePickers();
}

async function openDeliveryWorkflow(deliveryRow) {
  const row = typeof deliveryRow === "string"
    ? (window.state.data || []).find((r) => String(r.id) === String(deliveryRow))
    : deliveryRow;
  const deliveryId = row?.id || (typeof deliveryRow === "string" ? deliveryRow : null);
  const orderNum = row?.["شماره دستور"];
  if (!deliveryId && !orderNum) {
    toast("شناسه تحویل یا شماره دستور یافت نشد");
    return;
  }
  showLoading("در حال بارگذاری مراحل...");
  try {
    let res;
    if (deliveryId) {
      res = await api(`/deliveries/${encodeURIComponent(deliveryId)}/workflow`);
    } else {
      res = await api(`/orders/by-number/${encodeURIComponent(orderNum)}/workflow`);
    }
    if (!res?.order) throw new Error("دستور یافت نشد");
    if (res.note) toast(res.note);
    const inq = res.order["شماره استعلام"];
    if (typeof isReadOnly === "function" && isReadOnly() && inq) {
      await openWarehousePurchaseStages(inq);
      return;
    }
    openOrderStageModal(null, { row: res.order, readonly: true, workflowNote: res.note, workflowSource: res.source });
  } catch (e) {
    toast(e.message || "خطا در بارگذاری مراحل");
  } finally {
    hideLoading();
  }
}

function closeOrderStageModal() {
  orderEditId = null;
  orderStageState = {
    row: null, nextStage: null, complete: false, editStage: null, readonly: false, stagesOnly: false, stageTimeline: null, stageMeta: null,
  };
  $("orderStageModal")?.classList.add("hidden");
}

function collectStageFields(stageName, idPrefix) {
  const fields = STAGE_REQUIRED_FIELDS[stageName] || [];
  const payload = {};
  for (let i = 0; i < fields.length; i++) {
    const input = $(`${idPrefix}_${stageName}_${i}`) || $(`orderStageField_${i}`);
    const key = input?.dataset?.field || fields[i];
    const val = input?.value?.trim() || "";
    if (!val) return { error: `«${key}» الزامی است` };
    payload[key] = val;
  }
  return { payload };
}

async function submitOrderStage() {
  if (!orderEditId) return;
  const errEl = $("orderStageError");
  if (errEl) errEl.textContent = "";

  const editStage = orderStageState.editStage;
  const nextStage = orderStageState.nextStage;

  if (!editStage && (orderStageState.complete || !nextStage)) return;

  const targetStage = editStage || nextStage;
  const prefix = editStage ? "orderEditField" : "orderStageField";
  const collected = collectStageFields(targetStage, prefix);
  if (collected.error) {
    if (errEl) errEl.textContent = collected.error;
    return;
  }

  const payload = { ...collected.payload };
  if (!editStage) payload.توضیحات = $("orderStageNotes")?.value?.trim() || "";
  if (editStage) payload.edit_stage = editStage;

  const confirmMsg = editStage
    ? `تغییرات مرحله «${editStage}» ذخیره شود؟`
    : nextStage === "تحویل"
      ? "خاتمه فرآیند و ثبت در بخش تحویل‌ها؟"
      : `مرحله «${nextStage}» ثبت شود؟`;
  if (!confirm(confirmMsg)) return;

  showLoading(editStage ? "در حال ذخیره ویرایش..." : nextStage === "تحویل" ? "در حال خاتمه..." : "در حال ثبت مرحله...");
  try {
    const res = await api(`/orders/${orderEditId}`, { method: "PATCH", body: JSON.stringify(payload) });
    orderStageState.editStage = null;
    if (editStage) {
      toast(`مرحله «${editStage}» ویرایش شد`);
    } else if (nextStage === "تحویل") {
      toast("خاتمه — در بخش تحویل‌ها ثبت شد");
    } else {
      toast(`مرحله «${nextStage}» ثبت شد`);
    }
    if (res.order) {
      orderStageState.row = migrateOrderRow(res.order);
      renderOrderStageModalContent(res.order);
      initOrderStagePickers();
    }
    if (typeof loadViewData === "function") loadViewData();
    if (!editStage && res.workflow?.complete) {
      closeOrderStageModal();
      if (typeof setView === "function") setView("deliveries");
    }
  } catch (e) {
    if (errEl) errEl.textContent = e.message;
  } finally {
    hideLoading();
  }
}

function openDeliveryForm(deliveryId = null) {
  if (typeof isReadOnly === "function" && isReadOnly()) return;
  deliveryEditId = deliveryId;
  $("deliveryFormTitle").textContent = deliveryId ? "ویرایش تحویل" : "ثبت تحویل جدید";
  if (deliveryId) {
    const row = window.state.data.find((r) => String(r.id) === String(deliveryId));
    if (!row) return;
    $("deliveryNumber").value = row["شماره تحویل"] || "";
    $("deliveryNumber").readOnly = true;
    $("deliveryOrderNumber").value = row["شماره دستور"] || "";
    $("deliveryPurchaseNumber").value = row["شماره خرید"] || "";
    $("deliveryProductTitle").value = row["عنوان کالا"] || "";
    $("deliveryWarehouse").value = row["انبار"] || "";
    $("deliveryQuantity").value = row["مقدار"] || "";
    $("deliveryUnit").value = row["واحد"] || "";
    $("deliveryDate").value = row["تاریخ تحویل"] || "";
    $("deliveryReceiver").value = row["تحویل گیرنده"] || "";
    $("deliveryStatus").value = row["وضعیت"] || "ثبت شده";
    $("deliveryNotes").value = row["توضیحات"] || "";
  } else {
    $("deliveryNumber").value = "";
    $("deliveryNumber").readOnly = false;
    $("deliveryOrderNumber").value = "";
    $("deliveryPurchaseNumber").value = "";
    $("deliveryProductTitle").value = "";
    $("deliveryWarehouse").value = "";
    $("deliveryQuantity").value = "";
    $("deliveryUnit").value = "";
    $("deliveryDate").value = "";
    $("deliveryReceiver").value = "";
    $("deliveryStatus").value = "ثبت شده";
    $("deliveryNotes").value = "";
  }
  $("deliveryFormError").textContent = "";
  $("deliveryFormModal").classList.remove("hidden");
  setTimeout(() => {
    if (window.jalaliDatepicker) {
      try { jalaliDatepicker.startWatch({ time: false, separatorChars: { date: "/" }, zIndex: 9999 }); } catch { /* */ }
    }
  }, 50);
}

function closeDeliveryForm() {
  deliveryEditId = null;
  $("deliveryFormModal")?.classList.add("hidden");
}

async function saveDelivery() {
  const payload = {
    "شماره تحویل": $("deliveryNumber").value.trim(),
    "شماره دستور": $("deliveryOrderNumber").value.trim(),
    "شماره خرید": $("deliveryPurchaseNumber").value.trim(),
    "عنوان کالا": $("deliveryProductTitle").value.trim(),
    "انبار": $("deliveryWarehouse").value.trim(),
    "مقدار": $("deliveryQuantity").value.trim(),
    "واحد": $("deliveryUnit").value.trim(),
    "تاریخ تحویل": $("deliveryDate").value.trim(),
    "تحویل گیرنده": $("deliveryReceiver").value.trim(),
    "وضعیت": $("deliveryStatus").value,
    "توضیحات": $("deliveryNotes").value.trim(),
  };
  showLoading("در حال ذخیره...");
  try {
    if (deliveryEditId) {
      const { "شماره تحویل": _n, ...updates } = payload;
      await api(`/deliveries/${deliveryEditId}`, { method: "PATCH", body: JSON.stringify(updates) });
      toast("تحویل بروزرسانی شد");
    } else {
      if (!payload["شماره تحویل"]) throw new Error("شماره تحویل الزامی است");
      await api("/deliveries", { method: "POST", body: JSON.stringify(payload) });
      toast("تحویل ثبت شد");
    }
    closeDeliveryForm();
    if (typeof loadViewData === "function") loadViewData();
  } catch (e) {
    $("deliveryFormError").textContent = e.message;
  } finally {
    hideLoading();
  }
}

function renderOrdersTable(rows) {
  const head = $("tableHead");
  const body = $("tableBody");
  const readOnly = typeof isReadOnly === "function" && isReadOnly();
  head.innerHTML = `<tr>
    <th>شماره دستور</th><th>استعلام</th><th>خرید</th><th>ردیف</th><th>کالا</th><th>انبار</th>
    <th>کارشناس</th><th>پیمانکار</th><th>مرحله</th><th>تاریخ دستور</th><th>عملیات</th>
  </tr>`;
  body.innerHTML = rows.map((row, idx) => {
    const r = migrateOrderRow(row);
    const adminCtx = typeof isAdmin === "function" && isAdmin()
      ? ` oncontextmenu="openAdminContext(event,${idx})" ondblclick="openDetail(${idx})" class="cursor-pointer hover:bg-slate-50"`
      : "";
    const stage = r["مرحله فعلی"] || "—";
    const complete = isWorkflowComplete(stage);
    const stageCls = complete ? "badge-green" : "badge-blue";
    const actions = readOnly
      ? `<button class="text-indigo-600 text-xs font-semibold hover:underline" onclick="openOrderStageModal('${row.id}', { readonly: true })">مشاهده</button>`
      : canManageOrders()
        ? complete
          ? `<button class="text-indigo-600 text-xs hover:underline" onclick="openOrderStageModal('${row.id}')">مشاهده مراحل</button>`
          : `<button class="text-indigo-600 text-xs font-semibold hover:underline" onclick="openOrderStageModal('${row.id}')">ثبت مرحله بعد</button>`
        : `<button class="text-indigo-600 text-xs hover:underline" onclick="openDetailById('${row.id}')">مشاهده</button>`;
    return `<tr${adminCtx}>
      <td class="font-medium">${r["شماره دستور"] || "—"}</td>
      <td>${r["شماره استعلام"] || "—"}</td>
      <td>${r["شماره خرید"] || "—"}</td>
      <td>${r["ردیف"] ?? "—"}</td>
      <td title="${r["عنوان کالا"] || ""}">${truncate(r["عنوان کالا"], 30)}</td>
      <td>${r["انبار"] || "—"}</td>
      <td>${r["کارشناس"] || "—"}</td>
      <td>${r["نام پیمانکار"] || "—"}</td>
      <td><span class="badge ${stageCls}">${stage}</span></td>
      <td>${r["تاریخ دستور"] || "—"}</td>
      <td>${actions}</td>
    </tr>`;
  }).join("") || `<tr><td colspan="11" class="text-center py-12 text-slate-500">
    <p class="font-medium mb-1">هنوز دستوری ثبت نشده</p>
    <p class="text-xs">دستور خرید فقط از پنل مدیر (بررسی استعلام → صدور دستور) ساخته می‌شود — از اکسل خوانده نمی‌شود.</p>
  </td></tr>`;
}

function renderDeliveriesTable(rows) {
  const head = $("tableHead");
  const body = $("tableBody");
  const readOnly = typeof isReadOnly === "function" && isReadOnly();
  const toolbar = $("deliveriesToolbar");
  if (toolbar) toolbar.classList.toggle("hidden", readOnly || window.state.view !== "deliveries");

  head.innerHTML = `<tr>
    <th>شماره تحویل</th><th>دستور</th><th>خرید</th><th>کالا</th><th>انبار</th>
    <th>مقدار</th><th>تاریخ</th><th>گیرنده</th><th>وضعیت</th><th>عملیات</th>
  </tr>`;
  body.innerHTML = rows.map((row, idx) => {
    const qty = row["مقدار"] != null ? `${row["مقدار"]}${row["واحد"] ? ` ${row["واحد"]}` : ""}` : "—";
    const adminCtx = typeof isAdmin === "function" && isAdmin()
      ? ` oncontextmenu="openAdminContext(event,${idx})" ondblclick="openDetail(${idx})" class="cursor-pointer hover:bg-slate-50"`
      : "";
    const workflowBtn = row["شماره دستور"]
      ? `<button class="text-indigo-600 text-xs font-semibold hover:underline" onclick="openDeliveryWorkflow('${row.id}')">${readOnly ? "مراحل" : "روند"}</button>`
      : "";
    const editBtn = readOnly
      ? ""
      : `<button class="text-slate-600 text-xs hover:underline" onclick="openDeliveryForm('${row.id}')">ویرایش</button>`;
    const actions = [workflowBtn, editBtn].filter(Boolean).join(" · ") || "—";
    return `<tr${adminCtx}>
      <td class="font-medium">${row["شماره تحویل"] || "—"}</td>
      <td>${row["شماره دستور"] || "—"}</td>
      <td>${row["شماره خرید"] || "—"}</td>
      <td title="${row["عنوان کالا"] || ""}">${truncate(row["عنوان کالا"], 30)}</td>
      <td>${row["انبار"] || "—"}</td>
      <td>${qty}</td>
      <td>${row["تاریخ تحویل"] || "—"}</td>
      <td>${row["تحویل گیرنده"] || "—"}</td>
      <td>${statusBadge(row["وضعیت"])}</td>
      <td>${actions}</td>
    </tr>`;
  }).join("") || '<tr><td colspan="10" class="text-center py-12 text-slate-400">تحویلی یافت نشد</td></tr>';
}

function openDetailById(id) {
  const idx = window.state.data.findIndex((r) => String(r.id) === String(id));
  if (idx >= 0) openDetail(idx);
}

window.openIssueOrderModal = openIssueOrderModal;
window.closeIssueOrderModal = closeIssueOrderModal;
window.submitIssueOrder = submitIssueOrder;
window.openOrderStageModal = openOrderStageModal;
window.openDeliveryWorkflow = openDeliveryWorkflow;
window.closeOrderStageModal = closeOrderStageModal;
window.submitOrderStage = submitOrderStage;
window.openDeliveryForm = openDeliveryForm;
window.closeDeliveryForm = closeDeliveryForm;
window.saveDelivery = saveDelivery;
window.renderOrdersTable = renderOrdersTable;
window.renderDeliveriesTable = renderDeliveriesTable;
window.openDetailById = openDetailById;
window.openWarehousePurchaseStages = openWarehousePurchaseStages;
window.startEditOrderStage = startEditOrderStage;
window.cancelEditOrderStage = cancelEditOrderStage;