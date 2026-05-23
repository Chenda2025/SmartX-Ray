/**
 * api.js — shared API client + auth state manager.
 * Loaded on every page via base.html.
 */

const API_BASE = "/api";

// ── Token helpers ──────────────────────────────────────────────────────────
const Token = {
  get access()  { return localStorage.getItem("access_token"); },
  get refresh() { return localStorage.getItem("refresh_token"); },
  save(a, r)    { localStorage.setItem("access_token", a); if (r) localStorage.setItem("refresh_token", r); },
  clear()       { localStorage.removeItem("access_token"); localStorage.removeItem("refresh_token"); localStorage.removeItem("user"); },
};

// ── User state ─────────────────────────────────────────────────────────────
const User = {
  get()       { try { return JSON.parse(localStorage.getItem("user")); } catch { return null; } },
  save(u)     { localStorage.setItem("user", JSON.stringify(u)); },
  clear()     { localStorage.removeItem("user"); },
  get isPro() { return User.get()?.tier === "pro"; },
};

// ── Core fetch wrapper ─────────────────────────────────────────────────────
async function apiFetch(path, options = {}, retry = true) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (Token.access) headers["Authorization"] = `Bearer ${Token.access}`;

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (options.body instanceof FormData) delete headers["Content-Type"];

  const res = await fetch(API_BASE + path, { ...options, headers });

  // Auto-refresh on 401
  if (res.status === 401 && retry && Token.refresh) {
    const refreshed = await fetch(API_BASE + "/auth/refresh", {
      method: "POST",
      headers: { "Authorization": `Bearer ${Token.refresh}` },
    });
    if (refreshed.ok) {
      const data = await refreshed.json();
      Token.save(data.access_token, null);
      return apiFetch(path, options, false);
    } else {
      Auth.logout();
      return res;
    }
  }

  return res;
}

// Convenience wrappers
const api = {
  get:    (path)         => apiFetch(path, { method: "GET" }),
  post:   (path, body)   => apiFetch(path, { method: "POST",   body: JSON.stringify(body) }),
  patch:  (path, body)   => apiFetch(path, { method: "PATCH",  body: JSON.stringify(body) }),
  delete: (path)         => apiFetch(path, { method: "DELETE" }),
  upload: (path, form)   => apiFetch(path, { method: "POST",   body: form }),
};

// ── Auth helper ────────────────────────────────────────────────────────────
const Auth = {
  isLoggedIn() { return !!Token.access; },

  async login(email, password) {
    const res  = await api.post("/auth/login", { email, password });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Login failed.");
    Token.save(data.access_token, data.refresh_token);
    User.save(data.user);
    return data;
  },

  async register(email, password, full_name) {
    const res  = await api.post("/auth/register", { email, password, full_name });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Registration failed.");
    Token.save(data.access_token, data.refresh_token);
    User.save(data.user);
    return data;
  },

  async me() {
    const res  = await api.get("/auth/me");
    const data = await res.json();
    if (res.ok) User.save(data);
    return data;
  },

  logout() {
    Token.clear();
    User.clear();
    window.location.href = "/login";
  },

  requireLogin() {
    if (!Auth.isLoggedIn()) { window.location.href = "/login"; return false; }
    return true;
  },

  initNav() {
    const user = User.get();
    if (user) {
      document.getElementById("navAuth")?.classList.add("d-none");
      const navUser = document.getElementById("navUser");
      if (navUser) {
        navUser.classList.remove("d-none");
        navUser.classList.add("d-flex");
      }
      const badge = document.getElementById("navTierBadge");
      if (badge) {
        badge.textContent = user.tier === "pro" ? "PRO" : "FREE";
        badge.className   = `badge ${user.tier === "pro" ? "badge-pro" : "badge-free"}`;
      }
      const name = document.getElementById("navUserName");
      if (name) name.textContent = user.full_name || user.email;
    }
  },
};

// ── Toast notifications ────────────────────────────────────────────────────
function showToast(message, type = "success") {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const id   = `toast_${Date.now()}`;
  const icon = type === "success" ? "check-circle" : type === "danger" ? "circle-exclamation" : "info-circle";
  container.insertAdjacentHTML("beforeend", `
    <div id="${id}" class="toast align-items-center text-bg-${type} border-0" role="alert" aria-live="assertive">
      <div class="d-flex">
        <div class="toast-body"><i class="fa-solid fa-${icon} me-2"></i>${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`);
  const el = document.getElementById(id);
  new bootstrap.Toast(el, { delay: 4000 }).show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}

// ── Loading overlay ────────────────────────────────────────────────────────
function showLoading(msg = "Processing…") {
  let ov = document.getElementById("loadingOverlay");
  if (!ov) {
    document.body.insertAdjacentHTML("beforeend", `
      <div id="loadingOverlay">
        <div class="text-center text-white">
          <div class="spinner-border mb-3" style="width:3rem;height:3rem;" role="status"></div>
          <div id="loadingMsg" class="fs-6">${msg}</div>
        </div>
      </div>`);
  } else {
    document.getElementById("loadingMsg").textContent = msg;
    ov.style.display = "flex";
  }
}
function hideLoading() {
  const ov = document.getElementById("loadingOverlay");
  if (ov) ov.style.display = "none";
}
