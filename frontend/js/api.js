const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000/api" : "/api";

function getToken() {
  return sessionStorage.getItem("token");
}

function setToken(token) {
  if (token) sessionStorage.setItem("token", token);
  else sessionStorage.removeItem("token");
}

function getStoredUser() {
  try {
    return JSON.parse(sessionStorage.getItem("user") || "null");
  } catch {
    return null;
  }
}

function setStoredUser(user) {
  if (user) sessionStorage.setItem("user", JSON.stringify(user));
  else sessionStorage.removeItem("user");
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    setToken(null);
    setStoredUser(null);
    if (typeof showLogin === "function") showLogin();
    throw new Error("نشست شما منقضی شده — لطفاً دوباره وارد شوید");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail;
    const msg = Array.isArray(detail) ? detail.map((d) => d.msg).join("، ") : (detail || "خطا در ارتباط با سرور");
    throw new Error(msg);
  }

  if (res.status === 204) return null;
  return res.json();
}

function isServerMode() {
  return window.location.protocol !== "file:";
}