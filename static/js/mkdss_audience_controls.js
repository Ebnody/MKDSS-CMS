(function () {
  "use strict";
  function setupAudienceForm(form) {
    const audience = form.querySelector('[data-audience-select]');
    const departmentField = form.querySelector('[data-audience-field="department"]');
    const selectedField = form.querySelector('[data-audience-field="selected"]');
    const departmentSelect = form.querySelector('[data-audience-department]');
    const departmentDropdown = form.querySelector('[data-department-dropdown]');
    const departmentOptions = Array.from(form.querySelectorAll('[data-department-option]'));
    const summary = form.querySelector('[data-department-summary]');
    if (!audience) return;

    function updateSummary() {
      const count = departmentOptions.filter((item) => item.checked).length;
      if (summary) summary.textContent = count ? count + ' department(s) selected' : 'Choose departments';
    }
    function updateFields() {
      const value = audience.value;
      const useDepartment = value === 'DEPARTMENT';
      const useSelected = value === 'SELECTED_MANAGERS';
      if (departmentField) departmentField.hidden = !useDepartment;
      if (selectedField) selectedField.hidden = !useSelected;
      if (departmentSelect) {
        departmentSelect.disabled = !useDepartment;
        if (!useDepartment) departmentSelect.value = '';
      }
      departmentOptions.forEach((item) => {
        item.disabled = !useSelected;
        if (!useSelected) item.checked = false;
      });
      if (departmentDropdown) {
        departmentDropdown.setAttribute('aria-disabled', String(!useSelected));
        if (!useSelected) departmentDropdown.open = false;
      }
      updateSummary();
    }
    audience.addEventListener('change', updateFields);
    departmentOptions.forEach((item) => item.addEventListener('change', updateSummary));
    updateFields();
  }
  function setupActiveNavigation() {
    const currentPath = window.location.pathname.replace(/\/+$/, '') || '/';
    const links = Array.from(document.querySelectorAll('.mk-nav a.mk-nav-item[href]'));
    let best = null;
    let bestLength = -1;
    links.forEach((link) => {
      try {
        const path = new URL(link.href, window.location.origin).pathname.replace(/\/+$/, '') || '/';
        const matches = path === '/' ? currentPath === '/' : (currentPath === path || currentPath.startsWith(path + '/'));
        if (matches && path.length > bestLength) { best = link; bestLength = path.length; }
      } catch (_) {}
    });
    links.forEach((link) => {
      const active = link === best;
      link.classList.toggle('is-active', active);
      if (active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  }
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-audience-form]').forEach(setupAudienceForm);
    setupActiveNavigation();
  });
})();
