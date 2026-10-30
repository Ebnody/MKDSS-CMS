(function () {
  "use strict";
  const root = document.documentElement;
  const storageKey = "mkdss-theme";
  const moon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 15.5A8.5 8.5 0 0 1 8.5 3.5a8.5 8.5 0 1 0 12 12z"/></svg>';
  const sun = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></svg>';
  function applyTheme(theme) {
    root.dataset.theme = theme;
    const button = document.getElementById("theme-toggle");
    if (button) {
      const dark = theme === "dark";
      button.setAttribute("aria-pressed", String(dark));
      button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
      button.title = dark ? "Switch to light mode" : "Switch to dark mode";
      const icon = button.querySelector(".mk-theme-icon");
      if (icon) icon.innerHTML = dark ? sun : moon;
      const label = button.querySelector(".mk-theme-label");
      if (label) label.textContent = dark ? "Light mode" : "Dark mode";
    }
  }
  let savedTheme = "light";
  try { savedTheme = localStorage.getItem(storageKey) || "light"; } catch (_) {}
  applyTheme(savedTheme);
  function getCookie(name) {
    const prefix = name + "=";
    return document.cookie.split(";").map(v => v.trim()).find(v => v.indexOf(prefix) === 0)?.slice(prefix.length) || "";
  }
  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.content) || getCookie("csrftoken");
  }
  function setUnreadCount(count) {
    document.querySelectorAll(".notification-badge").forEach(el => el.remove());
    const button = document.getElementById("notification-button");
    if (!button || !count) return;
    const badge = document.createElement("span");
    badge.className = "notification-badge mk-notification-badge";
    badge.textContent = count > 99 ? "99+" : String(count);
    button.appendChild(badge);
  }
  async function markNotificationRead(item) {
    const id = item.dataset.notificationId;
    if (!id) return false;
    const response = await fetch("/notifications/" + id + "/read/", {
      method: "POST", headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin"
    });
    if (!response.ok) return false;
    const data = await response.json();
    item.classList.remove("unread");
    setUnreadCount(Number(data.unread || 0));
    if (data.url) window.location.assign(data.url);
    return true;
  }
  function closeSidebar() {
    const sidebar = document.getElementById("mk-sidebar");
    const overlay = document.getElementById("mk-sidebar-overlay");
    const trigger = document.getElementById("mk-menu-button");
    if (sidebar) sidebar.classList.remove("open");
    if (overlay) overlay.classList.remove("open");
    if (trigger) trigger.setAttribute("aria-expanded", "false");
  }
  document.addEventListener("click", async function (event) {
    const menuButton = event.target.closest("#mk-menu-button");
    if (menuButton) {
      const sidebar = document.getElementById("mk-sidebar");
      const overlay = document.getElementById("mk-sidebar-overlay");
      const open = !!sidebar && !sidebar.classList.contains("open");
      if (sidebar) sidebar.classList.toggle("open", open);
      if (overlay) overlay.classList.toggle("open", open);
      menuButton.setAttribute("aria-expanded", String(open));
      return;
    }
    if (event.target.closest("#mk-sidebar-overlay")) { closeSidebar(); return; }
    const card = event.target.closest("[data-dashboard-card][data-dashboard-href]");
    if (card && !event.target.closest("a,button,input,select,textarea,form,[role='button']")) {
      window.location.assign(card.dataset.dashboardHref);
      return;
    }
    const themeButton = event.target.closest("#theme-toggle");
    if (themeButton) {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      try { localStorage.setItem(storageKey, next); } catch (_) {}
      applyTheme(next);
      return;
    }
    const notificationItem = event.target.closest("[data-notification-id]");
    if (notificationItem) {
      event.preventDefault();
      try { await markNotificationRead(notificationItem); } catch (_) {}
      return;
    }
    const bell = event.target.closest("#notification-button");
    const panel = document.getElementById("notification-panel");
    if (bell && panel) {
      panel.classList.toggle("open");
      bell.setAttribute("aria-expanded", String(panel.classList.contains("open")));
      return;
    }
    if (panel && !event.target.closest(".mk-notification-wrap")) {
      panel.classList.remove("open");
      const bellButton = document.getElementById("notification-button");
      if (bellButton) bellButton.setAttribute("aria-expanded", "false");
    }
    if (event.target.closest(".mk-nav a")) closeSidebar();
  });
  document.addEventListener("keydown", function (event) {
    const card = event.target.closest && event.target.closest("[data-dashboard-card][data-dashboard-href]");
    if (card && (event.key === "Enter" || event.key === " ") && !event.target.closest("a,button,input,select,textarea,form")) {
      event.preventDefault();
      window.location.assign(card.dataset.dashboardHref);
      return;
    }
    if (event.key === "Escape") {
      closeSidebar();
      const panel = document.getElementById("notification-panel");
      if (panel) panel.classList.remove("open");
      const bell = document.getElementById("notification-button");
      if (bell) bell.setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("DOMContentLoaded", function () {
    const markAll = document.getElementById("mark-all-notifications");
    if (markAll) markAll.addEventListener("click", async function (event) {
      event.preventDefault(); event.stopPropagation();
      try {
        const response = await fetch("/notifications/read-all/", {
          method: "POST", headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin"
        });
        if (response.ok) {
          document.querySelectorAll("[data-notification-id]").forEach(item => item.classList.remove("unread"));
          setUnreadCount(0);
        }
      } catch (_) {}
    });
  });
})();
