function showLogin() {
  document.getElementById("loginPage").classList.remove("hidden");
  document.getElementById("appPage").classList.add("hidden");
  if (typeof stopRefresh === "function") stopRefresh();
}

function showApp() {
  document.getElementById("loginPage").classList.add("hidden");
  document.getElementById("appPage").classList.remove("hidden");
}

function updateUserUI(user) {
  const roleLabel = {
    admin: "مدیر سیستم",
    manager: "مدیر",
    expert: "کارشناس",
    warehouse: user.warehouse ? `انبار — ${user.warehouse}` : "انبار",
  };
  document.getElementById("userLabel").textContent = user.name;
  document.getElementById("userRole").textContent = roleLabel[user.role] || user.role;
  document.getElementById("userAvatar").textContent = user.name.charAt(0);

  const adminSection = document.getElementById("adminSection");
  if (adminSection) {
    adminSection.classList.toggle("hidden", user.role !== "admin");
  }

  const isManager = user.role === "admin" || user.role === "manager";
  const isExpert = user.role === "expert";
  const isWarehouse = user.role === "warehouse";

  const roleSelectors = [
    ".nav-link",
    ".filter-chip",
    "#filterBar",
    "#statsRow",
    "#statsMeta",
    "nav p",
  ];
  const seen = new Set();
  roleSelectors.forEach((sel) => {
    document.querySelectorAll(sel).forEach((el) => {
      if (seen.has(el)) return;
      seen.add(el);
      const hide =
        (el.classList.contains("manager-only") && !isManager)
        || (el.classList.contains("expert-only") && !isExpert)
        || (el.classList.contains("warehouse-only") && !isWarehouse)
        || (el.classList.contains("not-warehouse") && isWarehouse)
        || (el.classList.contains("not-expert") && isExpert)
        || (el.classList.contains("manager-inquiry-chip") && isExpert)
        || (el.classList.contains("expert-inquiry-chip") && !isExpert);
      el.classList.toggle("hidden", hide);
    });
  });
  hideEmptyNavSections();
}

function hideEmptyNavSections() {
  const nav = document.querySelector("nav");
  if (!nav) return;
  nav.querySelectorAll(".nav-section-label").forEach((header) => {
    let el = header.nextElementSibling;
    let hasVisible = false;
    while (el && !el.classList.contains("nav-section-label") && el.id !== "adminSection") {
      const isNavItem = el.classList.contains("nav-link") || el.id === "filterBar";
      if (isNavItem && !el.classList.contains("hidden")) {
        hasVisible = true;
        break;
      }
      el = el.nextElementSibling;
    }
    header.classList.toggle("hidden", !hasVisible);
  });
}

async function login() {
  const username = document.getElementById("username").value.trim().toLowerCase();
  const password = document.getElementById("password").value;
  const errEl = document.getElementById("loginError");
  const btn = document.getElementById("loginBtn");

  errEl.textContent = "";
  if (!username || !password) {
    errEl.textContent = "نام کاربری و رمز عبور را وارد کنید";
    return;
  }

  if (!isServerMode()) {
    errEl.textContent = "لطفاً از طریق سرور وارد شوید: http://127.0.0.1:8000";
    return;
  }

  btn.disabled = true;
  btn.textContent = "در حال ورود...";

  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    setToken(data.access_token);
    setStoredUser(data.user);
    window.state.user = data.user;
    updateUserUI(data.user);
    showApp();
    if (typeof startApp === "function") startApp();
  } catch (e) {
    errEl.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "ورود به سامانه";
  }
}

function logout() {
  setToken(null);
  setStoredUser(null);
  window.state.user = null;
  document.getElementById("password").value = "";
  showLogin();
}

async function tryAutoLogin() {
  const token = getToken();
  const user = getStoredUser();
  if (!token || !user) return showLogin();

  try {
    const me = await api("/auth/me");
    window.state.user = me;
    setStoredUser(me);
    updateUserUI(me);
    showApp();
    if (typeof startApp === "function") startApp();
  } catch {
    showLogin();
  }
}

async function loadSetupStatus() {
  const el = document.getElementById("setupWarning");
  if (!el || !isServerMode()) return;
  try {
    const setup = await api("/system/setup");
    const msgs = setup.messages || [];
    if (!setup.ready && msgs.length) {
      el.classList.remove("hidden");
      el.innerHTML = msgs.map((m) => `<p class="mb-1">• ${m}</p>`).join("");
    } else {
      el.classList.add("hidden");
    }
  } catch {
    /* server not ready */
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (!isServerMode()) {
    document.getElementById("serverWarning").classList.remove("hidden");
  } else {
    loadSetupStatus();
  }
  document.getElementById("password").addEventListener("keydown", (e) => {
    if (e.key === "Enter") login();
  });
  tryAutoLogin();
});