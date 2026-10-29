/**
 * doctor_sidebar.js
 * Centralized, shared sidebar management, live header profile hydration, 
 * settings synchronization, dynamic badge updates, and mobile responsive drawer/layout
 * for all Doctor Portal pages.
 * Jeevan Setu - ICU to HDU Transfer DSS
 */

(function () {
  function detectActivePage() {
    const path = window.location.pathname.toLowerCase();
    if (path.includes('doctor_dashboard')) return 'dashboard';
    if (path.includes('doctor_my_patients')) return 'my_patients';
    if (path.includes('doctor_all_patients')) return 'all_patients';
    if (path.includes('doctor_patient_search')) return 'patient_search';
    if (path.includes('doctor_ews_calculator')) return 'ews_calculator';
    if (path.includes('doctor_transfer_recommendations')) return 'transfer_recommendations';
    if (path.includes('doctor_ews_trends')) return 'ews_trends';
    if (path.includes('doctor_patient_summary_ai')) return 'patient_summary_ai';
    if (path.includes('doctor_pending_approvals')) return 'pending_approvals';
    if (path.includes('doctor_alerts_notifications')) return 'alerts_notifications';
    if (path.includes('doctor_patient_reports')) return 'patient_reports';
    if (path.includes('doctor_transfer_reports')) return 'transfer_reports';
    if (path.includes('doctor_audit_logs')) return 'audit_logs';
    if (path.includes('doctor_settings_jeevan')) return 'settings';
    return '';
  }

  function injectDoctorResponsiveStyles() {
    if (document.getElementById('doctor-responsive-theme-styles')) return;
    const style = document.createElement('style');
    style.id = 'doctor-responsive-theme-styles';
    style.textContent = `
      html, body {
        max-width: 100vw;
        overflow-x: hidden;
      }
      #doctor-sidebar,
      aside[data-purpose="sidebar"],
      aside.w-64 {
        transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1),
                    width 0.28s cubic-bezier(0.4, 0, 0.2, 1) !important;
      }
      @media (min-width: 1025px) {
        body.doctor-sidebar-collapsed #doctor-sidebar,
        body.doctor-sidebar-collapsed aside {
          width: 0 !important;
          min-width: 0 !important;
          max-width: 0 !important;
          overflow: hidden !important;
          opacity: 0 !important;
          pointer-events: none !important;
          transform: translateX(-100%) !important;
          border: none !important;
        }
        body.doctor-sidebar-collapsed .pl-64,
        body.doctor-sidebar-collapsed .lg\\:pl-64,
        body.doctor-sidebar-collapsed .md\\:pl-64 {
          padding-left: 0 !important;
        }
        body.doctor-sidebar-collapsed .left-64,
        body.doctor-sidebar-collapsed header.fixed {
          left: 0 !important;
        }
      }
      @media (max-width: 1024px) {
        #doctor-sidebar,
        aside[data-purpose="sidebar"],
        aside.w-64,
        aside {
          position: fixed !important;
          left: 0 !important;
          top: 0 !important;
          bottom: 0 !important;
          height: 100dvh !important;
          z-index: 60 !important;
          transform: translateX(-100%) !important;
          width: 16rem !important;
          max-width: 82vw !important;
        }
        body.sidebar-mobile-open #doctor-sidebar,
        body.sidebar-mobile-open aside[data-purpose="sidebar"],
        body.sidebar-mobile-open aside.w-64,
        body.sidebar-mobile-open aside {
          transform: translateX(0) !important;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.65) !important;
        }
        .pl-64, .md\\:pl-64, .lg\\:pl-64, .ml-64 {
          padding-left: 0 !important;
          margin-left: 0 !important;
        }
        header.left-64, .left-64, header.fixed {
          left: 0 !important;
        }
        header {
          padding-left: 0.75rem !important;
          padding-right: 0.75rem !important;
        }
        main {
          padding-left: 0.75rem;
          padding-right: 0.75rem;
        }
      }
      @media (max-width: 767px) {
        /* Make multi-column layouts stack cleanly on phones */
        .grid-cols-12 > .col-span-8,
        .grid-cols-12 > .col-span-4,
        .grid-cols-12 > .col-span-7,
        .grid-cols-12 > .col-span-5,
        .grid-cols-12 > .col-span-6,
        .grid-cols-12 > .col-span-9,
        .grid-cols-12 > .col-span-3 {
          grid-column: span 12 / span 12 !important;
        }
        section[data-purpose="dashboard-stats"].grid-cols-6,
        .grid-cols-6:not(.sm\\:grid-cols-6):not(.md\\:grid-cols-6):not(.lg\\:grid-cols-6),
        .grid-cols-5:not(.sm\\:grid-cols-5):not(.md\\:grid-cols-5):not(.lg\\:grid-cols-5),
        .grid-cols-4:not(.sm\\:grid-cols-4):not(.md\\:grid-cols-4):not(.lg\\:grid-cols-4) {
          grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        }
        .grid-cols-3:not(.sm\\:grid-cols-3):not(.md\\:grid-cols-3):not(.lg\\:grid-cols-3):not(#demo-role-grid) {
          grid-template-columns: repeat(1, minmax(0, 1fr)) !important;
        }
        /* Header search & toolbar responsiveness */
        header .w-96, header .w-80, header .w-72, header .w-64 {
          width: auto !important;
          max-width: 48vw !important;
          flex: 1 1 auto !important;
        }
        header .pl-8 {
          padding-left: 0.5rem !important;
        }
        header .space-x-8 > :not([hidden]) ~ :not([hidden]) {
          margin-left: 0.5rem !important;
        }
        #active-patient-bar {
          padding: 0.5rem 0.75rem !important;
          flex-wrap: wrap !important;
          gap: 0.5rem !important;
        }
        #patient-dropdown-menu {
          left: 0 !important;
          right: auto !important;
          width: min(18rem, calc(100vw - 24px)) !important;
        }
      }
      @media (max-width: 480px) {
        section[data-purpose="dashboard-stats"].grid-cols-6 {
          grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
          gap: 0.5rem !important;
        }
        #chat-form {
          gap: 0.375rem !important;
        }
        #send-btn {
          padding-left: 0.75rem !important;
          padding-right: 0.75rem !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  window.toggleMobileDoctorSidebar = function (event) {
    if (event) event.stopPropagation();
    const backdrop = document.getElementById('doctor-sidebar-backdrop');
    if (window.innerWidth <= 1024) {
      const isOpen = document.body.classList.toggle('sidebar-mobile-open');
      if (backdrop) {
        backdrop.classList.toggle('hidden', !isOpen);
      }
    } else {
      document.body.classList.toggle('doctor-sidebar-collapsed');
    }
  };

  function setupMobileDoctorDrawer() {
    injectDoctorResponsiveStyles();

    const aside = document.getElementById('doctor-sidebar') || document.querySelector('aside');
    if (!aside) return;

    aside.setAttribute('data-purpose', 'sidebar');

    // 1. Ensure mobile backdrop exists
    let backdrop = document.getElementById('doctor-sidebar-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'doctor-sidebar-backdrop';
      backdrop.className = 'fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 lg:hidden hidden transition-opacity';
      backdrop.addEventListener('click', () => {
        document.body.classList.remove('sidebar-mobile-open');
        backdrop.classList.add('hidden');
      });
      document.body.appendChild(backdrop);
    }

    // 2. Ensure close button inside sidebar branding header on mobile
    const brandBar = aside.querySelector('.border-b');
    if (brandBar && !brandBar.querySelector('#doctor-sidebar-close-btn')) {
      brandBar.classList.add('justify-between');
      const closeBtn = document.createElement('button');
      closeBtn.id = 'doctor-sidebar-close-btn';
      closeBtn.type = 'button';
      closeBtn.className = 'lg:hidden text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors cursor-pointer';
      closeBtn.setAttribute('aria-label', 'Close navigation menu');
      closeBtn.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`;
      closeBtn.addEventListener('click', window.toggleMobileDoctorSidebar);
      brandBar.appendChild(closeBtn);
    }

    // Close mobile drawer when a nav link is clicked on mobile
    aside.querySelectorAll('a.sidebar-nav-item').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 1024) {
          document.body.classList.remove('sidebar-mobile-open');
          if (backdrop) backdrop.classList.add('hidden');
        }
      });
    });

    // 3. Ensure every page's top header has a working mobile hamburger button
    const header = document.querySelector('header');
    if (header) {
      let existingHamburger = null;
      const buttons = header.querySelectorAll('button');
      buttons.forEach(btn => {
        const svgPath = btn.querySelector('svg path');
        const d = svgPath ? (svgPath.getAttribute('d') || '') : '';
        const iconSpan = btn.querySelector('.material-symbols-outlined');
        const iconText = iconSpan ? iconSpan.textContent.trim() : '';
        if (d.includes('M4 6h16') || d.includes('M3 12') || iconText === 'menu') {
          existingHamburger = btn;
        }
      });

      if (existingHamburger) {
        existingHamburger.id = 'doctor-mobile-menu-btn';
        existingHamburger.setAttribute('aria-label', 'Toggle navigation menu');
        existingHamburger.classList.add('cursor-pointer');
        if (!existingHamburger.hasAttribute('data-mobile-bound')) {
          existingHamburger.setAttribute('data-mobile-bound', 'true');
          existingHamburger.addEventListener('click', window.toggleMobileDoctorSidebar);
        }
      } else {
        // Inject a mobile hamburger button at the start of the header's left section
        const hamburgerBtn = document.createElement('button');
        hamburgerBtn.id = 'doctor-mobile-menu-btn';
        hamburgerBtn.type = 'button';
        hamburgerBtn.setAttribute('aria-label', 'Toggle navigation menu');
        hamburgerBtn.setAttribute('data-mobile-bound', 'true');
        hamburgerBtn.className = 'lg:hidden p-2 mr-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors focus:outline-none cursor-pointer flex-shrink-0';
        hamburgerBtn.innerHTML = `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`;
        hamburgerBtn.addEventListener('click', window.toggleMobileDoctorSidebar);

        const firstChild = header.firstElementChild;
        if (firstChild && (firstChild.classList.contains('flex') || firstChild.tagName === 'DIV')) {
          firstChild.insertBefore(hamburgerBtn, firstChild.firstChild);
        } else {
          header.insertBefore(hamburgerBtn, header.firstChild);
        }
      }
    }

    // 4. Wrap any unwrapped tables in overflow-x-auto for controlled horizontal scrolling
    document.querySelectorAll('table').forEach(tbl => {
      const parent = tbl.parentElement;
      if (parent && !parent.classList.contains('overflow-x-auto') && !parent.classList.contains('overflow-auto')) {
        parent.classList.add('overflow-x-auto');
      }
    });
  }

  function highlightActiveSidebarItem() {
    const activeKey = detectActivePage();
    if (!activeKey) return;

    const navItems = document.querySelectorAll('.sidebar-nav-item[data-page]');
    navItems.forEach(item => {
      const page = item.getAttribute('data-page');
      const icon = item.querySelector('.material-symbols-outlined');
      if (page === activeKey) {
        item.classList.remove('text-slate-300', 'hover:bg-white/5');
        item.classList.add('bg-white/10', 'text-cyan-400', 'font-semibold', 'border-l-4', 'border-cyan-400');
        if (icon) {
          icon.classList.remove('text-slate-400');
          icon.classList.add('text-cyan-400');
        }
      } else {
        item.classList.remove('bg-white/10', 'text-cyan-400', 'font-semibold', 'border-l-4', 'border-cyan-400');
        item.classList.add('text-slate-300', 'hover:bg-white/5', 'hover:text-white');
        if (icon) {
          icon.classList.remove('text-cyan-400');
          icon.classList.add('text-slate-400');
        }
      }
    });
  }

  function getAuthToken() {
    return localStorage.getItem('jeevan_setu_token') || localStorage.getItem('token') || sessionStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('token') || '';
  }

  function getAuthHeaders() {
    const token = getAuthToken();
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    };
  }

  function applyDoctorProfileToDOM(user) {
    if (!user) return;

    const rawName = user.full_name || user.username || 'Doctor';
    const formattedName = rawName.startsWith('Dr.') ? rawName : `Dr. ${rawName}`;
    const specialization = (user.doctor_details && user.doctor_details.specialization) || user.specialization || user.department || 'Consultant Intensivist';
    const initials = rawName.replace(/^Dr\.\s*/i, '').trim().split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase() || 'DR';

    // 1. Update Name elements
    const nameSelectors = [
      '#header-doctor-name',
      '#top-doctor-name',
      '.doctor-profile-name',
      '#sidebar-doctor-name'
    ];
    document.querySelectorAll(nameSelectors.join(', ')).forEach(el => {
      el.textContent = formattedName;
    });

    // 2. Update Role / Dept elements
    const deptSelectors = [
      '#header-doctor-dept',
      '#top-doctor-role',
      '.doctor-profile-dept',
      '#sidebar-doctor-dept'
    ];
    document.querySelectorAll(deptSelectors.join(', ')).forEach(el => {
      el.textContent = specialization;
    });

    // 3. Update Avatar / Initials elements
    const avatarSelectors = [
      '#header-avatar-circle',
      '.doctor-profile-avatar',
      '#header-avatar-initials'
    ];
    document.querySelectorAll(avatarSelectors.join(', ')).forEach(el => {
      el.textContent = initials;
    });

    // 4. Update Header Profile Container (in case page doesn't have specific IDs yet)
    const headerProfileContainers = document.querySelectorAll('header .border-l, header .pl-md, header .pl-lg, header .pl-4');
    headerProfileContainers.forEach(container => {
      const nameDiv = container.querySelector('.font-bold, .text-on-surface, .text-label-md, .text-label-sm, p.text-sm');
      const deptDiv = container.querySelector('.text-[10px], .text-[11px], .text-[12px], .text-on-surface-variant, p.text-xs');
      if (nameDiv && !nameDiv.closest('#header-doctor-name')) {
        nameDiv.textContent = formattedName;
      }
      if (deptDiv && !deptDiv.closest('#header-doctor-dept')) {
        deptDiv.textContent = specialization;
      }
      const avatarDiv = container.querySelector('.w-10.h-10, .w-9.h-9, .w-8.h-8');
      if (avatarDiv && !avatarDiv.querySelector('img') && !avatarDiv.id) {
        avatarDiv.innerHTML = `<span class="font-bold text-sm text-white">${initials}</span>`;
      }
    });

    // 5. Populate Settings Page Fields if on Doctor_settings_jeevan.html
    hydrateSettingsPage(user, formattedName, specialization);
  }

  function hydrateSettingsPage(user, formattedName, specialization) {
    const isSettingsPage = window.location.pathname.toLowerCase().includes('settings');
    if (!isSettingsPage) return;

    const docId = user.doctor_details ? user.doctor_details.doctor_id : user.id;
    const docCode = `DOC-${String(docId).padStart(3, '0')}`;
    const email = user.email || `${user.username}@jeevansetu.in`;
    const license = (user.doctor_details && user.doctor_details.license_number) || 'MCI-KA-2015-08942';
    const qual = (user.doctor_details && user.doctor_details.qualification) || 'MD Medicine, DM Critical Care';
    const exp = (user.doctor_details && user.doctor_details.experience_years) || 12;

    function setVal(selectors, val) {
      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
          el.value = val;
          return;
        }
      }
    }

    setVal(['#full-name', '#fullName', 'input[name="full_name"]', 'input[name="fullName"]'], formattedName);
    setVal(['#username', 'input[name="username"]'], user.username || '');
    setVal(['#email', 'input[name="email"]'], email);
    setVal(['#role', 'input[name="role"]'], 'Attending Doctor / Intensivist');
    setVal(['#staff-id', '#doctor-id', '#doctorId', 'input[name="staff_id"]', 'input[name="doctor_id"]'], docCode);
    setVal(['#department', 'input[name="department"]'], user.department || 'ICU / Critical Care');
    setVal(['#specialization', 'input[name="specialization"]'], specialization);
    setVal(['#license-number', '#licenseNumber', 'input[name="license_number"]'], license);
    setVal(['#qualification', 'input[name="qualification"]'], qual);
    setVal(['#experience-years', '#experience', 'input[name="experience_years"]'], exp);

    document.querySelectorAll('#settings-profile-name, .settings-user-name').forEach(el => {
      el.textContent = formattedName;
    });
    document.querySelectorAll('#settings-profile-role, .settings-user-role').forEach(el => {
      el.textContent = `${specialization} | ${docCode}`;
    });
  }

  async function syncLiveDoctorHeader() {
    try {
      const cached = localStorage.getItem('jeevan_setu_user');
      if (cached) {
        const cachedUser = JSON.parse(cached);
        applyDoctorProfileToDOM(cachedUser);
      }
    } catch (e) {}

    const token = getAuthToken();
    if (!token) {
      const path = window.location.pathname.toLowerCase();
      if (!path.includes('login')) {
        window.location.href = '../../Login/Login.html';
      }
      return;
    }

    try {
      const res = await fetch('/api/v1/auth/me', { headers: getAuthHeaders() });
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data) {
          const user = json.data;
          localStorage.setItem('jeevan_setu_user', JSON.stringify(user));
          localStorage.setItem('user', JSON.stringify(user));
          localStorage.setItem('userName', user.full_name || user.username);
          localStorage.setItem('user_id', String(user.id));
          localStorage.setItem('role', user.role);

          applyDoctorProfileToDOM(user);
        }
      } else if (res.status === 401 || res.status === 403) {
        console.warn('[Doctor Sidebar] Session expired or invalid token');
      }
    } catch (e) {
      console.warn('[Doctor Sidebar] Could not sync live doctor header:', e);
    }
  }

  async function fetchSidebarBadgeCounts() {
    try {
      const res = await fetch('/api/v1/decision/pending', { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        const pendingList = Array.isArray(data) ? data : (data.pending_transfers || data.recommendations || []);
        const total = pendingList.length;
        const badge = document.getElementById('sidebar-pending-count');
        if (badge) {
          badge.textContent = total;
          badge.style.display = total > 0 ? 'inline-block' : 'none';
        }
      }
    } catch (e) {}

    try {
      const res = await fetch('/api/v1/notifications/unread-count', { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        const count = typeof data.unread_count === 'number' ? data.unread_count : (data.count || 0);
        const badge = document.getElementById('sidebar-alerts-count');
        if (badge) {
          badge.textContent = count;
          badge.style.display = count > 0 ? 'inline-block' : 'none';
        }
      }
    } catch (e) {}
  }

  window.handleDoctorLogout = async function (event) {
    if (event) event.preventDefault();
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST', headers: getAuthHeaders() }).catch(() => {});
    } catch (e) {}
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '../../Login/Login.html';
  };

  function initDoctorSidebar() {
    setupMobileDoctorDrawer();
    highlightActiveSidebarItem();
    syncLiveDoctorHeader();
    if (window.AutoRefreshManager) {
      window.AutoRefreshManager.start('doctor_sidebar_badges', fetchSidebarBadgeCounts, 10000);
    } else {
      fetchSidebarBadgeCounts();
      setInterval(fetchSidebarBadgeCounts, 10000);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDoctorSidebar);
  } else {
    initDoctorSidebar();
  }
})();
