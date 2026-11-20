/**
 * dropdown_enhancer.js — Global Theme-Matched Accessible Dropdown System for Jeevan Setu
 *
 * Progressively enhances native <select> elements into dark-themed, cyan-accented
 * custom dropdowns while keeping the underlying <select> 100% synchronized
 * (value, options, change events, form submission, programmatic .value updates,
 * and dynamic MutationObserver option changes).
 */
(function () {
  if (window.__jeevanDropdownEnhancerLoaded) return;
  window.__jeevanDropdownEnhancerLoaded = true;

  const VALUE_DESC = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
  const IDX_DESC = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');

  let activeMenuState = null; // { select, wrapper, trigger, menu, cleanup }
  let idCounter = 0;

  function closeActiveMenu(restoreFocus = false) {
    if (!activeMenuState) return;
    const { trigger, menu, cleanup } = activeMenuState;
    activeMenuState = null;
    trigger.setAttribute('aria-expanded', 'false');
    trigger.classList.remove('is-open');
    if (menu && menu.parentNode) menu.parentNode.removeChild(menu);
    if (cleanup) cleanup();
    if (restoreFocus) {
      try { trigger.focus(); } catch (e) {}
    }
  }

  function getSelectedSummary(select) {
    if (select.multiple) {
      const selected = Array.from(select.options).filter(o => o.selected);
      if (selected.length === 0) return 'Select options...';
      if (selected.length === 1) return selected[0].textContent.trim();
      return `${selected.length} selected`;
    }
    const opt = select.options[select.selectedIndex];
    return opt ? opt.textContent.trim() : 'Select...';
  }

  function syncTriggerLabel(select, labelEl, trigger) {
    labelEl.textContent = getSelectedSummary(select);
    trigger.disabled = !!select.disabled;
    trigger.classList.toggle('is-disabled', !!select.disabled);
  }

  function positionMenu(trigger, menu) {
    const rect = trigger.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const gap = 6;

    menu.style.minWidth = `${Math.max(rect.width, 160)}px`;
    menu.style.maxWidth = `${Math.min(vw - 16, Math.max(rect.width + 80, 320))}px`;

    // Measure menu height
    const menuH = Math.min(menu.scrollHeight || 240, 280);
    const spaceBelow = vh - rect.bottom - gap - 8;
    const spaceAbove = rect.top - gap - 8;

    let top;
    let maxH;
    if (spaceBelow >= Math.min(menuH, 160) || spaceBelow >= spaceAbove) {
      top = rect.bottom + gap;
      maxH = Math.max(120, Math.min(280, spaceBelow));
      menu.classList.remove('is-flipped');
    } else {
      maxH = Math.max(120, Math.min(280, spaceAbove));
      const actualH = Math.min(menuH, maxH);
      top = Math.max(8, rect.top - gap - actualH);
      menu.classList.add('is-flipped');
    }

    let left = rect.left;
    const menuW = Math.min(menu.offsetWidth || rect.width, vw - 16);
    if (left + menuW > vw - 8) {
      left = Math.max(8, vw - menuW - 8);
    }
    if (left < 8) left = 8;

    menu.style.top = `${top}px`;
    menu.style.left = `${left}px`;
    menu.style.maxHeight = `${maxH}px`;
  }

  function openMenu(select, wrapper, trigger, labelEl) {
    if (select.disabled) return;
    if (activeMenuState && activeMenuState.select === select) {
      closeActiveMenu(true);
      return;
    }
    closeActiveMenu(false);

    const menuId = `js-dropdown-menu-${++idCounter}`;
    const menu = document.createElement('div');
    menu.id = menuId;
    menu.className = 'js-dropdown-menu';
    menu.setAttribute('role', 'listbox');
    if (select.multiple) menu.setAttribute('aria-multiselectable', 'true');

    const options = Array.from(select.options);
    if (options.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'js-dropdown-empty';
      empty.textContent = 'No options available';
      menu.appendChild(empty);
    } else {
      options.forEach((opt, idx) => {
        if (opt.hidden) return;
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'js-dropdown-option';
        if (opt.selected) item.classList.add('is-selected');
        if (opt.disabled) item.classList.add('is-disabled');
        item.disabled = !!opt.disabled;
        item.setAttribute('role', 'option');
        item.setAttribute('aria-selected', opt.selected ? 'true' : 'false');
        item.setAttribute('data-index', String(idx));

        const textSpan = document.createElement('span');
        textSpan.className = 'js-dropdown-option-text';
        textSpan.textContent = opt.textContent.trim();

        const checkSpan = document.createElement('span');
        checkSpan.className = 'js-dropdown-option-check';
        checkSpan.innerHTML = opt.selected
          ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>'
          : '';

        item.appendChild(textSpan);
        item.appendChild(checkSpan);

        item.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          if (opt.disabled) return;

          if (select.multiple) {
            opt.selected = !opt.selected;
            item.classList.toggle('is-selected', opt.selected);
            item.setAttribute('aria-selected', opt.selected ? 'true' : 'false');
            checkSpan.innerHTML = opt.selected
              ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>'
              : '';
            syncTriggerLabel(select, labelEl, trigger);
            select.dispatchEvent(new Event('change', { bubbles: true }));
          } else {
            const changed = select.selectedIndex !== idx;
            if (IDX_DESC && IDX_DESC.set) {
              IDX_DESC.set.call(select, idx);
            } else {
              select.selectedIndex = idx;
            }
            syncTriggerLabel(select, labelEl, trigger);
            closeActiveMenu(true);
            if (changed) {
              select.dispatchEvent(new Event('input', { bubbles: true }));
              select.dispatchEvent(new Event('change', { bubbles: true }));
            }
          }
        });

        menu.appendChild(item);
      });
    }

    document.body.appendChild(menu);
    trigger.setAttribute('aria-expanded', 'true');
    trigger.setAttribute('aria-controls', menuId);
    trigger.classList.add('is-open');
    positionMenu(trigger, menu);

    // Focus selected or first enabled option
    const focusTarget = menu.querySelector('.js-dropdown-option.is-selected:not(:disabled)')
      || menu.querySelector('.js-dropdown-option:not(:disabled)');
    if (focusTarget) {
      focusTarget.scrollIntoView({ block: 'nearest' });
    }

    const onOutsideClick = (ev) => {
      if (!menu.contains(ev.target) && !trigger.contains(ev.target)) {
        closeActiveMenu(false);
      }
    };
    const onScrollOrResize = () => {
      if (!document.body.contains(trigger)) {
        closeActiveMenu(false);
        return;
      }
      positionMenu(trigger, menu);
    };
    const onMenuKeyDown = (ev) => {
      const items = Array.from(menu.querySelectorAll('.js-dropdown-option:not(:disabled)'));
      if (!items.length) return;
      const curIdx = items.indexOf(document.activeElement);

      if (ev.key === 'Escape') {
        ev.preventDefault();
        closeActiveMenu(true);
      } else if (ev.key === 'ArrowDown') {
        ev.preventDefault();
        const next = items[(curIdx + 1) % items.length];
        next.focus();
      } else if (ev.key === 'ArrowUp') {
        ev.preventDefault();
        const prev = items[(curIdx - 1 + items.length) % items.length];
        prev.focus();
      } else if (ev.key === 'Home') {
        ev.preventDefault();
        items[0].focus();
      } else if (ev.key === 'End') {
        ev.preventDefault();
        items[items.length - 1].focus();
      } else if (ev.key === 'Tab') {
        closeActiveMenu(false);
      }
    };

    menu.addEventListener('keydown', onMenuKeyDown);
    setTimeout(() => {
      document.addEventListener('mousedown', onOutsideClick, true);
      window.addEventListener('resize', onScrollOrResize, true);
      window.addEventListener('scroll', onScrollOrResize, true);
    }, 0);

    activeMenuState = {
      select,
      wrapper,
      trigger,
      menu,
      cleanup: () => {
        document.removeEventListener('mousedown', onOutsideClick, true);
        window.removeEventListener('resize', onScrollOrResize, true);
        window.removeEventListener('scroll', onScrollOrResize, true);
        menu.removeEventListener('keydown', onMenuKeyDown);
      }
    };
  }

  function enhanceSelect(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    if (select.dataset.jsDropdownEnhanced === '1' || select.dataset.nativeSelect === 'true') return;
    select.dataset.jsDropdownEnhanced = '1';

    // Hide native select accessibly while keeping it in DOM for forms, .value, and listeners
    select.classList.add('js-native-select-hidden');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    const wrapper = document.createElement('div');
    wrapper.className = 'js-dropdown';

    // Inherit width/flex classes from select so layout alignment stays identical
    const copyWidthClasses = ['w-full', 'sm:w-auto', 'sm:w-64', 'flex-1'];
    copyWidthClasses.forEach(cls => {
      if (select.classList.contains(cls)) wrapper.classList.add(cls);
    });

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'js-dropdown-trigger';
    trigger.setAttribute('role', 'combobox');
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    if (select.getAttribute('aria-label')) {
      trigger.setAttribute('aria-label', select.getAttribute('aria-label'));
    }

    const labelEl = document.createElement('span');
    labelEl.className = 'js-dropdown-label';

    const arrowEl = document.createElement('span');
    arrowEl.className = 'js-dropdown-arrow';
    arrowEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>';

    trigger.appendChild(labelEl);
    trigger.appendChild(arrowEl);

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    wrapper.appendChild(trigger);

    syncTriggerLabel(select, labelEl, trigger);

    // Intercept programmatic .value and .selectedIndex updates
    if (VALUE_DESC && VALUE_DESC.get && VALUE_DESC.set) {
      Object.defineProperty(select, 'value', {
        configurable: true,
        get() {
          return VALUE_DESC.get.call(this);
        },
        set(val) {
          VALUE_DESC.set.call(this, val);
          syncTriggerLabel(this, labelEl, trigger);
        }
      });
    }
    if (IDX_DESC && IDX_DESC.get && IDX_DESC.set) {
      Object.defineProperty(select, 'selectedIndex', {
        configurable: true,
        get() {
          return IDX_DESC.get.call(this);
        },
        set(val) {
          IDX_DESC.set.call(this, val);
          syncTriggerLabel(this, labelEl, trigger);
        }
      });
    }

    // Sync on native change or form reset
    select.addEventListener('change', () => syncTriggerLabel(select, labelEl, trigger));
    if (select.form) {
      select.form.addEventListener('reset', () => {
        setTimeout(() => syncTriggerLabel(select, labelEl, trigger), 0);
      });
    }

    // Watch dynamic <option> mutations or disabled state changes
    const optObserver = new MutationObserver(() => {
      syncTriggerLabel(select, labelEl, trigger);
    });
    optObserver.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'selected'] });

    trigger.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      openMenu(select, wrapper, trigger, labelEl);
    });

    trigger.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openMenu(select, wrapper, trigger, labelEl);
        setTimeout(() => {
          if (activeMenuState && activeMenuState.menu) {
            const first = activeMenuState.menu.querySelector('.js-dropdown-option.is-selected:not(:disabled)')
              || activeMenuState.menu.querySelector('.js-dropdown-option:not(:disabled)');
            if (first) first.focus();
          }
        }, 0);
      }
    });
  }

  function enhanceAllSelects(root = document) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('select').forEach(enhanceSelect);
  }

  function initDropdownEnhancer() {
    enhanceAllSelects(document);
    const bodyObserver = new MutationObserver((mutations) => {
      for (const m of mutations) {
        m.addedNodes.forEach((node) => {
          if (node.nodeType !== 1) return;
          if (node.tagName === 'SELECT') enhanceSelect(node);
          else if (node.querySelectorAll) enhanceAllSelects(node);
        });
      }
    });
    if (document.body) {
      bodyObserver.observe(document.body, { childList: true, subtree: true });
    }
  }

  window.JeevanDropdownEnhancer = {
    enhanceAll: enhanceAllSelects,
    enhanceSelect,
    closeAll: () => closeActiveMenu(false)
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDropdownEnhancer);
  } else {
    initDropdownEnhancer();
  }
})();
