let editingUsername = null;

async function loadWarehouseOptions() {
  try {
    const res = await api("/warehouses");
    const items = res.items || [];
    const dl = document.getElementById("warehouseList");
    if (dl) {
      dl.innerHTML = items.map((w) => `<option value="${String(w).replace(/"/g, "&quot;")}">`).join("");
    }
    const adv = document.getElementById("advWarehouse");
    if (adv && adv.tagName === "SELECT") {
      const cur = adv.value;
      adv.innerHTML = `<option value="">همه انبارها</option>${items.map((w) =>
        `<option value="${String(w).replace(/"/g, "&quot;")}">${w}</option>`
      ).join("")}`;
      if (cur && items.includes(cur)) adv.value = cur;
    }
  } catch { /* ignore */ }
}

function toggleUserWarehouseField() {
  const role = document.getElementById("fuRole").value;
  const isWh = role === "warehouse";
  document.getElementById("fuWarehouseWrap")?.classList.toggle("hidden", !isWh);
  document.getElementById("fuExpertWrap")?.classList.toggle("hidden", isWh);
}

async function loadUsers() {
  const users = await api("/users");
  const body = document.getElementById("usersTableBody");
  body.innerHTML = users.map((u) => `
    <tr class="${u.active ? "" : "opacity-60"}">
      <td class="font-medium">${u.name}</td>
      <td><code class="text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">${u.username}</code></td>
      <td>${roleBadge(u.role)}</td>
      <td>${u.role === "warehouse" ? (u.warehouse || "—") : (u.expert || "—")}</td>
      <td>${u.active ? '<span class="badge badge-green">فعال</span>' : '<span class="badge badge-slate">غیرفعال</span>'}</td>
      <td class="space-x-reverse space-x-2 whitespace-nowrap">
        <button class="btn btn-ghost !py-1 !px-3 text-xs" onclick="openUserForm('${u.username}')">ویرایش</button>
        ${u.active
          ? `<button class="btn btn-danger !py-1 !px-3 text-xs" onclick="deactivateUser('${u.username}')">غیرفعال</button>`
          : `<button class="btn btn-ghost !py-1 !px-3 text-xs" onclick="reactivateUser('${u.username}')">فعال‌سازی</button>`}
      </td>
    </tr>
  `).join("") || '<tr><td colspan="6" class="text-center py-8 text-slate-400">کاربری یافت نشد</td></tr>';
}

function roleBadge(role) {
  const map = {
    admin: '<span class="badge badge-purple">مدیر سیستم</span>',
    manager: '<span class="badge badge-blue">مدیر</span>',
    expert: '<span class="badge badge-green">کارشناس</span>',
    warehouse: '<span class="badge badge-amber">انبار</span>',
  };
  return map[role] || role;
}

function openUserForm(username = null) {
  editingUsername = username;
  document.getElementById("userFormTitle").textContent = username ? "ویرایش کاربر" : "کاربر جدید";
  document.getElementById("fuUsername").disabled = false;
  document.getElementById("fuUsername").value = username || "";
  document.getElementById("fuPassword").value = "";
  document.getElementById("fuPassword").placeholder = username ? "خالی = بدون تغییر" : "حداقل ۶ کاراکتر";
  document.getElementById("fuName").value = "";
  document.getElementById("fuRole").value = "expert";
  document.getElementById("fuExpert").value = "";
  document.getElementById("fuWarehouse").value = "";
  document.getElementById("fuActive").checked = true;
  document.getElementById("fuMetaWrap")?.classList.toggle("hidden", !username);
  document.getElementById("userFormError").textContent = "";
  toggleUserWarehouseField();

  if (username) {
    api("/users").then((users) => {
      const u = users.find((x) => x.username === username);
      if (!u) return;
      document.getElementById("fuUsername").value = u.username;
      document.getElementById("fuName").value = u.name;
      document.getElementById("fuRole").value = u.role;
      document.getElementById("fuExpert").value = u.expert || "";
      document.getElementById("fuWarehouse").value = u.warehouse || "";
      document.getElementById("fuActive").checked = u.active;
      document.getElementById("fuUserId").textContent = u.id || "—";
      document.getElementById("fuCreatedAt").textContent = u.created_at ? String(u.created_at).slice(0, 16).replace("T", " ") : "—";
      document.getElementById("fuUpdatedAt").textContent = u.updated_at ? String(u.updated_at).slice(0, 16).replace("T", " ") : "—";
      toggleUserWarehouseField();
    });
  }

  document.getElementById("userFormModal").classList.remove("hidden");
}

function closeUserForm() {
  document.getElementById("userFormModal").classList.add("hidden");
  editingUsername = null;
}

async function saveUser() {
  const role = document.getElementById("fuRole").value;
  const usernameInput = document.getElementById("fuUsername").value.trim().toLowerCase();
  const payload = {
    username: usernameInput,
    password: document.getElementById("fuPassword").value,
    name: document.getElementById("fuName").value.trim(),
    role,
    expert: role === "warehouse" ? null : (document.getElementById("fuExpert").value.trim() || null),
    warehouse: role === "warehouse" ? (document.getElementById("fuWarehouse").value.trim() || null) : null,
    active: document.getElementById("fuActive").checked,
  };

  if (role === "warehouse" && !payload.warehouse) {
    document.getElementById("userFormError").textContent = "انبار مرتبط برای نقش انبار الزامی است";
    return;
  }

  try {
    if (editingUsername) {
      const update = { ...payload };
      if (usernameInput !== editingUsername) update.new_username = usernameInput;
      delete update.username;
      if (!update.password) delete update.password;
      await api(`/users/${editingUsername}`, { method: "PUT", body: JSON.stringify(update) });
      toast("کاربر بروزرسانی شد");
    } else {
      await api("/users", { method: "POST", body: JSON.stringify(payload) });
      toast("کاربر ایجاد شد");
    }
    closeUserForm();
    loadUsers();
    if (typeof loadPurchaseExperts === "function") loadPurchaseExperts(true);
  } catch (e) {
    document.getElementById("userFormError").textContent = e.message;
  }
}

async function deactivateUser(username) {
  if (!confirm(`کاربر «${username}» غیرفعال شود؟\nداده‌های استعلام و گردش کار او حفظ می‌شود.`)) return;
  try {
    await api(`/users/${username}`, { method: "DELETE" });
    toast("کاربر غیرفعال شد");
    if (typeof loadPurchaseExperts === "function") loadPurchaseExperts(true);
    loadUsers();
  } catch (e) {
    alert(e.message);
  }
}

async function reactivateUser(username) {
  try {
    await api(`/users/${username}`, { method: "PUT", body: JSON.stringify({ active: true }) });
    toast("کاربر فعال شد");
    loadUsers();
    if (typeof loadPurchaseExperts === "function") loadPurchaseExperts(true);
  } catch (e) {
    alert(e.message);
  }
}

window.loadWarehouseOptions = loadWarehouseOptions;
window.toggleUserWarehouseField = toggleUserWarehouseField;
window.openUserForm = openUserForm;
window.closeUserForm = closeUserForm;
window.saveUser = saveUser;
window.deactivateUser = deactivateUser;
window.reactivateUser = reactivateUser;