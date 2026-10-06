(function () {
  "use strict";

  const root = document.documentElement;
  const storageKey = "mkdss-theme";

  function applyTheme(theme) {
    root.dataset.theme = theme;
    const button = document.getElementById("theme-toggle");
    if (button) {
      const dark = theme === "dark";
      button.setAttribute("aria-pressed", String(dark));
      button.title = dark ? "Switch to light mode" : "Switch to dark mode";
      const icon = button.querySelector(".theme-icon");
      if (icon) icon.textContent = dark ? "☀" : "☾";
    }
  }

  const savedTheme = localStorage.getItem(storageKey) || "light";
  applyTheme(savedTheme);

  function getCookie(name) {
    const prefix = name + "=";
    return document.cookie
      .split(";")
      .map(v => v.trim())
      .find(v => v.indexOf(prefix) === 0)?.slice(prefix.length) || "";
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
    badge.className = "notification-badge";
    badge.textContent = count > 99 ? "99+" : String(count);
    button.appendChild(badge);
  }

  async function markNotificationRead(item) {
    const id = item.dataset.notificationId;
    if (!id) return false;

    const response = await fetch("/notifications/" + id + "/read/", {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    });

    if (!response.ok) return false;
    const data = await response.json();
    item.classList.remove("unread");
    setUnreadCount(Number(data.unread || 0));

    if (data.url) {
      window.location.assign(data.url);
    }
    return true;
  }

  document.addEventListener("click", async function (event) {
    const themeButton = event.target.closest("#theme-toggle");
    if (themeButton) {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      localStorage.setItem(storageKey, next);
      applyTheme(next);
      return;
    }

    const notificationItem = event.target.closest("[data-notification-id]");
    if (notificationItem) {
      // Prevent the browser's default GET. The notification must first be
      // marked read through the authenticated POST endpoint, then navigated.
      event.preventDefault();
      try {
        await markNotificationRead(notificationItem);
      } catch (_) {
        // Keep the user on the current page if the read operation fails.
      }
      return;
    }

    const bell = event.target.closest("#notification-button");
    const panel = document.getElementById("notification-panel");
    if (bell && panel) {
      panel.classList.toggle("open");
      bell.setAttribute("aria-expanded", String(panel.classList.contains("open")));
      return;
    }

    if (panel && !event.target.closest(".notification-wrap")) {
      panel.classList.remove("open");
      const bellButton = document.getElementById("notification-button");
      if (bellButton) bellButton.setAttribute("aria-expanded", "false");
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      const panel = document.getElementById("notification-panel");
      if (panel) panel.classList.remove("open");
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-notification-id]").forEach(function (item) {
      // no-op: delegated click handling is installed above
    });

    document.querySelectorAll("#mark-all-notifications").forEach(function (markAll) {
      markAll.addEventListener("click", async function (event) {
        event.preventDefault();
        event.stopPropagation();
        try {
          const response = await fetch("/notifications/read-all/", {
            method: "POST",
            headers: {
              "X-CSRFToken": csrfToken(),
              "X-Requested-With": "XMLHttpRequest",
            },
            credentials: "same-origin",
          });
          if (response.ok) {
            document.querySelectorAll("[data-notification-id]").forEach(item => item.classList.remove("unread"));
            setUnreadCount(0);
          }
        } catch (_) {}
      });
    });
  });
})();
