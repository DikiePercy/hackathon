let siteCurrentUser = null;

function tr(key, fallback) {
  return window.AppI18n?.t?.(key) || fallback;
}

function tf(key, fallback, vars = {}) {
  let text = tr(key, fallback);
  Object.entries(vars).forEach(([name, value]) => {
    text = text.replaceAll(`{${name}}`, String(value ?? ""));
  });
  return text;
}

function resolveAuthApiBase() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  if (fromQuery) {
    return fromQuery.replace(/\/$/, "");
  }
  return "";
}

const SITE_AUTH_API_BASE = resolveAuthApiBase();

function authApiUrl(path) {
  return SITE_AUTH_API_BASE ? `${SITE_AUTH_API_BASE}${path}` : path;
}

async function authFetch(path, options = {}) {
  return fetch(authApiUrl(path), {
    credentials: "include",
    ...options
  });
}

function emitAuthChange() {
  window.dispatchEvent(new CustomEvent("site-auth-changed", {
    detail: { user: siteCurrentUser }
  }));
}

function setGlobalAuthStatus(text) {
  const statusEl = document.getElementById("globalAuthStatus");
  if (statusEl) {
    statusEl.textContent = text;
  }
}

function openGlobalAuthModal() {
  const modal = document.getElementById("globalAuthModal");
  if (!modal) return;
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeGlobalAuthModal() {
  const modal = document.getElementById("globalAuthModal");
  if (!modal) return;
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

function updateGlobalAuthControls() {
  const loginBtn = document.getElementById("globalLoginOpenBtn");
  const logoutBtn = document.getElementById("globalLogoutBtn");
  if (!loginBtn || !logoutBtn) return;

  if (siteCurrentUser) {
    loginBtn.hidden = true;
    logoutBtn.hidden = false;
  } else {
    loginBtn.hidden = false;
    logoutBtn.hidden = true;
  }
}

async function refreshSiteSession() {
  const response = await authFetch("/me");
  if (!response.ok) {
    siteCurrentUser = null;
    setGlobalAuthStatus(tr("auth_not_authorized", "Not authorized"));
    normalizeHeaderNav();
    updateGlobalAuthControls();
    emitAuthChange();
    return null;
  }

  siteCurrentUser = await response.json();
  setGlobalAuthStatus(tf("auth_logged_in_as", "Logged in: {username} ({role})", {
    username: siteCurrentUser.username,
    role: siteCurrentUser.role,
  }));
  normalizeHeaderNav();
  updateGlobalAuthControls();
  emitAuthChange();
  return siteCurrentUser;
}

async function registerSiteUser() {
  const username = (document.getElementById("globalAuthUser")?.value || "").trim();
  const password = (document.getElementById("globalAuthPass")?.value || "").trim();
  if (!username || !password) {
    setGlobalAuthStatus(tr("auth_need_credentials", "Enter username and password"));
    return;
  }

  const response = await authFetch("/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    setGlobalAuthStatus(`Error: ${payload.detail || response.status}`);
    return;
  }

  setGlobalAuthStatus(tr("auth_register_success", "Registration successful. Please sign in."));
}

async function loginSiteUser() {
  const username = (document.getElementById("globalAuthUser")?.value || "").trim();
  const password = (document.getElementById("globalAuthPass")?.value || "").trim();
  if (!username || !password) {
    setGlobalAuthStatus(tr("auth_need_credentials", "Enter username and password"));
    return;
  }

  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);

  const response = await authFetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString()
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    setGlobalAuthStatus(`Error: ${payload.detail || response.status}`);
    return;
  }

  await refreshSiteSession();
  closeGlobalAuthModal();
}

async function logoutSiteUser() {
  await authFetch("/logout", { method: "POST" });
  siteCurrentUser = null;
  setGlobalAuthStatus(tr("status_logged_out", "You have signed out"));
  normalizeHeaderNav();
  updateGlobalAuthControls();
  emitAuthChange();
}

function normalizeHeaderNav() {
  const nav = document.querySelector(".header-nav");
  if (!nav) return;

  const links = [
    { href: "index.html", label: tr("nav_main", "Home") },
    { href: "list.html", label: tr("nav_db", "Database") },
    { href: "about.html", label: tr("nav_about", "About") },
    { href: "contacts.html", label: tr("nav_contacts", "Contacts") },
    { href: "chat.html", label: tr("nav_chat", "AI Chat") },
    { href: "suggestions.html", label: tr("nav_suggestions", "Submit Entry") },
    { href: "admin.html", label: tr("nav_admin", "Admin"), adminOnly: true }
  ];

  const page = window.location.pathname.split("/").pop() || "index.html";
  nav.innerHTML = links
    .filter((item) => !item.adminOnly || siteCurrentUser?.role === "admin")
    .map(({ href, label }) => {
      const active = href === page ? " class=\"nav-active\"" : "";
      return `<a href=\"${href}\"${active}>${label}</a>`;
    })
    .join("");

  nav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      closeMobileMenu();
    });
  });
}

function ensureHeaderBurger() {
  const headerInner = document.querySelector(".header-inner");
  const siteHeader = document.querySelector(".site-header");
  if (!headerInner || !siteHeader) return;

  if (headerInner.querySelector("#headerBurgerBtn")) return;

  const button = document.createElement("button");
  button.id = "headerBurgerBtn";
  button.className = "header-burger";
  button.type = "button";
  button.setAttribute("aria-label", "Open menu");
  button.setAttribute("aria-expanded", "false");
  button.innerHTML = "&#9776;";

  button.addEventListener("click", () => {
    const isOpen = siteHeader.classList.toggle("menu-open");
    button.setAttribute("aria-expanded", isOpen ? "true" : "false");
    button.innerHTML = isOpen ? "&times;" : "&#9776;";
  });

  headerInner.appendChild(button);
}

function ensureHeaderMenuOverlay() {
  if (document.querySelector(".header-menu-overlay")) return;
  const overlay = document.createElement("div");
  overlay.className = "header-menu-overlay";
  overlay.setAttribute("aria-hidden", "true");
  overlay.addEventListener("click", () => {
    closeMobileMenu();
  });
  document.body.appendChild(overlay);
}

function closeMobileMenu() {
  const siteHeader = document.querySelector(".site-header");
  const burger = document.getElementById("headerBurgerBtn");
  if (siteHeader) {
    siteHeader.classList.remove("menu-open");
  }
  if (burger) {
    burger.setAttribute("aria-expanded", "false");
    burger.innerHTML = "&#9776;";
  }
}

function handleHeaderResize() {
  if (window.innerWidth > 700) {
    closeMobileMenu();
  }
}

function ensureHeaderSearchBar() {
  const headerInner = document.querySelector(".header-inner");
  if (!headerInner || headerInner.querySelector(".search-bar")) return;

  const search = document.createElement("div");
  search.className = "search-bar";
  search.innerHTML = `
    <input type="text" placeholder="${tr("search_placeholder", "Search by name, surname, year...")}" id="searchInput">
    <button type="button" id="searchBtn">${tr("search_btn", "Search")}</button>
  `;

  const nav = headerInner.querySelector(".header-nav");
  if (nav) {
    headerInner.insertBefore(search, nav);
  } else {
    headerInner.appendChild(search);
  }
}

function ensureHeaderAuthControls() {
  const headerInner = document.querySelector(".header-inner");
  if (!headerInner || document.getElementById("globalLoginOpenBtn")) return;

  const controls = document.createElement("div");
  controls.className = "global-auth-controls";
  controls.innerHTML = `
    <button id="globalLoginOpenBtn" type="button">${tr("auth_login_btn", "Sign in")}</button>
    <button id="globalLogoutBtn" type="button" hidden>${tr("btn_logout", "Logout")}</button>
  `;
  headerInner.appendChild(controls);
}

function ensureGlobalAuthModal() {
  if (document.getElementById("globalAuthModal")) return;

  const modal = document.createElement("div");
  modal.id = "globalAuthModal";
  modal.className = "global-auth-modal";
  modal.setAttribute("aria-hidden", "true");
  modal.innerHTML = `
    <div class="global-auth-dialog" role="dialog" aria-modal="true" aria-labelledby="globalAuthTitle">
      <div class="global-auth-header">
        <h3 id="globalAuthTitle">${tr("auth_title", "Sign in")}</h3>
        <button id="globalAuthCloseBtn" type="button" class="global-auth-close" aria-label="Закрыть">x</button>
      </div>
      <div class="global-auth-fields">
        <input id="globalAuthUser" type="text" placeholder="${tr("auth_username_placeholder", "Username")}" autocomplete="username">
        <input id="globalAuthPass" type="password" placeholder="${tr("auth_password_placeholder", "Password")}" autocomplete="current-password">
      </div>
      <div class="global-auth-actions">
        <button id="globalAuthRegisterBtn" type="button">${tr("btn_register", "Register")}</button>
        <button id="globalAuthLoginBtn" type="button">${tr("btn_login", "Login")}</button>
      </div>
      <p id="globalAuthStatus">${tr("auth_not_authorized", "Not authorized")}</p>
    </div>
  `;

  document.body.appendChild(modal);
}

function setupGlobalAuthEvents() {
  document.getElementById("globalLoginOpenBtn")?.addEventListener("click", openGlobalAuthModal);
  document.getElementById("globalLogoutBtn")?.addEventListener("click", logoutSiteUser);
  document.getElementById("globalAuthCloseBtn")?.addEventListener("click", closeGlobalAuthModal);
  document.getElementById("globalAuthRegisterBtn")?.addEventListener("click", registerSiteUser);
  document.getElementById("globalAuthLoginBtn")?.addEventListener("click", loginSiteUser);

  document.getElementById("globalAuthModal")?.addEventListener("click", (event) => {
    if (event.target.id === "globalAuthModal") {
      closeGlobalAuthModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeGlobalAuthModal();
      closeMobileMenu();
    }
  });
}

function setupGlobalSearch() {
  const isListPage =
    window.location.pathname.endsWith("/list.html") ||
    window.location.pathname.endsWith("list.html");
  if (isListPage) return;

  const input = document.getElementById("searchInput");
  const btn = document.getElementById("searchBtn");
  if (!input || !btn) return;

  const runSearch = () => {
    const q = (input.value || "").trim();
    if (!q) return;

    const params = new URLSearchParams(window.location.search);
    const api = params.get("api");
    const target = new URL("list.html", window.location.href);
    target.searchParams.set("q", q);
    if (api) {
      target.searchParams.set("api", api);
    }
    window.location.href = target.toString();
  };

  const existingFlag = "data-global-search-bound";
  if (!btn.hasAttribute(existingFlag)) {
    btn.setAttribute(existingFlag, "1");
    btn.addEventListener("click", runSearch);
  }

  if (!input.hasAttribute(existingFlag)) {
    input.setAttribute(existingFlag, "1");
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        runSearch();
      }
    });
  }
}

window.SiteAuth = {
  getCurrentUser: () => siteCurrentUser,
  refreshSession: refreshSiteSession,
  openModal: openGlobalAuthModal,
  logout: logoutSiteUser
};

document.addEventListener("DOMContentLoaded", async () => {
  normalizeHeaderNav();
  ensureHeaderBurger();
  ensureHeaderMenuOverlay();
  ensureHeaderSearchBar();
  ensureHeaderAuthControls();
  ensureGlobalAuthModal();
  setupGlobalAuthEvents();
  setupGlobalSearch();
  handleHeaderResize();
  window.addEventListener("resize", handleHeaderResize);
  await refreshSiteSession();

  window.addEventListener("site-language-changed", () => {
    normalizeHeaderNav();
    ensureHeaderBurger();
    ensureHeaderMenuOverlay();
    ensureHeaderSearchBar();
    ensureHeaderAuthControls();
    if (!siteCurrentUser) {
      setGlobalAuthStatus(tr("auth_not_authorized", "Not authorized"));
    } else {
      setGlobalAuthStatus(tf("auth_logged_in_as", "Logged in: {username} ({role})", {
        username: siteCurrentUser.username,
        role: siteCurrentUser.role,
      }));
    }
  });
});
