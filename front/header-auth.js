let siteCurrentUser = null;

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
    setGlobalAuthStatus("Не авторизован");
    normalizeHeaderNav();
    updateGlobalAuthControls();
    emitAuthChange();
    return null;
  }

  siteCurrentUser = await response.json();
  setGlobalAuthStatus(`Вход выполнен: ${siteCurrentUser.username} (${siteCurrentUser.role})`);
  normalizeHeaderNav();
  updateGlobalAuthControls();
  emitAuthChange();
  return siteCurrentUser;
}

async function registerSiteUser() {
  const username = (document.getElementById("globalAuthUser")?.value || "").trim();
  const password = (document.getElementById("globalAuthPass")?.value || "").trim();
  if (!username || !password) {
    setGlobalAuthStatus("Введите логин и пароль");
    return;
  }

  const response = await authFetch("/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    setGlobalAuthStatus(`Ошибка регистрации: ${payload.detail || response.status}`);
    return;
  }

  setGlobalAuthStatus("Регистрация успешна. Теперь войдите.");
}

async function loginSiteUser() {
  const username = (document.getElementById("globalAuthUser")?.value || "").trim();
  const password = (document.getElementById("globalAuthPass")?.value || "").trim();
  if (!username || !password) {
    setGlobalAuthStatus("Введите логин и пароль");
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
    setGlobalAuthStatus(`Ошибка входа: ${payload.detail || response.status}`);
    return;
  }

  await refreshSiteSession();
  closeGlobalAuthModal();
}

async function logoutSiteUser() {
  await authFetch("/logout", { method: "POST" });
  siteCurrentUser = null;
  setGlobalAuthStatus("Вы вышли");
  normalizeHeaderNav();
  updateGlobalAuthControls();
  emitAuthChange();
}

function normalizeHeaderNav() {
  const nav = document.querySelector(".header-nav");
  if (!nav) return;

  const links = [
    { href: "index.html", label: "Главная" },
    { href: "list.html", label: "База данных" },
    { href: "about.html", label: "О проекте" },
    { href: "contacts.html", label: "Контакты" },
    { href: "chat.html", label: "Чат AI" },
    { href: "suggestions.html", label: "Предложить запись" },
    { href: "admin.html", label: "Админ", adminOnly: true }
  ];

  const page = window.location.pathname.split("/").pop() || "index.html";
  nav.innerHTML = links
    .filter((item) => !item.adminOnly || siteCurrentUser?.role === "admin")
    .map(({ href, label }) => {
      const active = href === page ? " class=\"nav-active\"" : "";
      return `<a href=\"${href}\"${active}>${label}</a>`;
    })
    .join("");
}

function ensureHeaderSearchBar() {
  const headerInner = document.querySelector(".header-inner");
  if (!headerInner || headerInner.querySelector(".search-bar")) return;

  const search = document.createElement("div");
  search.className = "search-bar";
  search.innerHTML = `
    <input type="text" placeholder="Поиск по имени, фамилии, году..." id="searchInput">
    <button type="button" id="searchBtn">Найти</button>
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
    <button id="globalLoginOpenBtn" type="button">Зайти</button>
    <button id="globalLogoutBtn" type="button" hidden>Выйти</button>
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
        <h3 id="globalAuthTitle">Вход в аккаунт</h3>
        <button id="globalAuthCloseBtn" type="button" class="global-auth-close" aria-label="Закрыть">x</button>
      </div>
      <div class="global-auth-fields">
        <input id="globalAuthUser" type="text" placeholder="Логин" autocomplete="username">
        <input id="globalAuthPass" type="password" placeholder="Пароль" autocomplete="current-password">
      </div>
      <div class="global-auth-actions">
        <button id="globalAuthRegisterBtn" type="button">Регистрация</button>
        <button id="globalAuthLoginBtn" type="button">Войти</button>
      </div>
      <p id="globalAuthStatus">Не авторизован</p>
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
  ensureHeaderSearchBar();
  ensureHeaderAuthControls();
  ensureGlobalAuthModal();
  setupGlobalAuthEvents();
  setupGlobalSearch();
  await refreshSiteSession();
});
