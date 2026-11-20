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

  function ensureDoctorUnifiedResponsiveCSS() {
    if (document.getElementById('jeevan-responsive-unified-styles')) return;
    const link = document.createElement('link');
    link.id = 'jeevan-responsive-unified-styles';
    link.rel = 'stylesheet';
    link.href = '/static/css/responsive_unified.css';
    document.head.appendChild(link);
  }

  function injectDoctorResponsiveStyles() {
    ensureDoctorUnifiedResponsiveCSS();
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
          max-width: 85vw !important;
        }
        body.sidebar-mobile-open #doctor-sidebar,
        body.sidebar-mobile-open aside[data-purpose="sidebar"],
        body.sidebar-mobile-open aside.w-64,
        body.sidebar-mobile-open aside {
          transform: translateX(0) !important;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8) !important;
        }
        .pl-64, .md\\:pl-64, .lg\\:pl-64, .ml-64 {
          padding-left: 0 !important;
          margin-left: 0 !important;
        }
        header.left-64, .left-64, header.fixed {
          left: 0 !important;
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
          gap: 0.625rem !important;
        }
        .grid-cols-3:not(.sm\\:grid-cols-3):not(.md\\:grid-cols-3):not(.lg\\:grid-cols-3):not(#demo-role-grid) {
          grid-template-columns: repeat(1, minmax(0, 1fr)) !important;
          gap: 0.75rem !important;
        }
        /* Patient Cards Grid */
        #my-patients-grid,
        #all-patients-grid {
          grid-template-columns: repeat(1, minmax(0, 1fr)) !important;
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
        section[data-purpose="dashboard-stats"].grid-cols-6,
        section[data-purpose="dashboard-stats"] {
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
        .js-sync-indicator span[data-sync-text] {
          display: none !important;
        }
        .js-sync-indicator {
          padding: 0.35rem !important;
        }
      }
      @media (max-width: 360px) {
        section[data-purpose="dashboard-stats"] {
          grid-template-columns: repeat(1, minmax(0, 1fr)) !important;
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

  // --- Doctor Availability Management ---
  let currentDoctorAvailability = 'active';
  let isDoctorAvailabilityUpdating = false;

  try {
    const cached = localStorage.getItem('jeevan_setu_user');
    if (cached) {
      const cachedUser = JSON.parse(cached);
      if (cachedUser.availability) currentDoctorAvailability = cachedUser.availability;
      else if (cachedUser.doctor_details && cachedUser.doctor_details.availability) currentDoctorAvailability = cachedUser.doctor_details.availability;
    }
  } catch (e) {}

  function showAvailabilityToast(message, type = 'success') {
    let container = document.getElementById('availability-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'availability-toast-container';
      container.className = 'fixed top-4 right-4 z-[999999] flex flex-col gap-2 pointer-events-none';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    const isSuccess = type === 'success';
    const bgColor = isSuccess ? 'bg-emerald-600' : 'bg-rose-600';
    const icon = isSuccess
      ? '<svg class="w-4 h-4 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
      : '<svg class="w-4 h-4 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';

    toast.className = `flex items-center gap-2.5 px-3.5 py-2 rounded-lg shadow-lg text-white text-xs font-semibold ${bgColor} pointer-events-auto transition-all duration-200 transform translate-y-[-8px] opacity-0`;
    toast.innerHTML = `${icon}<span>${message}</span>`;
    container.appendChild(toast);

    requestAnimationFrame(() => {
      toast.classList.remove('translate-y-[-8px]', 'opacity-0');
      toast.classList.add('translate-y-0', 'opacity-100');
    });

    setTimeout(() => {
      toast.classList.remove('translate-y-0', 'opacity-100');
      toast.classList.add('translate-y-[-8px]', 'opacity-0');
      setTimeout(() => toast.remove(), 250);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getDoctorPageTitle() {
    const activeKey = detectActivePage();
    const titleMap = {
      'dashboard': 'Doctor Dashboard',
      'my_patients': 'My Assigned Patients',
      'all_patients': 'All Patients Directory',
      'patient_search': 'Patient Search',
      'ews_calculator': 'EWS Calculator',
      'transfer_recommendations': 'Transfer DSS',
      'ews_trends': 'EWS Trends & Vitals',
      'patient_summary_ai': 'Clinical AI Assistant',
      'pending_approvals': 'Pending ICU Transfers',
      'alerts_notifications': 'Alerts & Notifications',
      'patient_reports': 'Patient Clinical Reports',
      'transfer_reports': 'Transfer DSS Reports',
      'audit_logs': 'System Audit Logs',
      'settings': 'Doctor Profile & Settings'
    };
    if (titleMap[activeKey]) return titleMap[activeKey];
    const existingH = document.querySelector('header h2, header h1, header .font-bold');
    if (existingH && existingH.textContent.trim()) return existingH.textContent.trim();
    return 'Doctor Portal';
  }

  function getStoredDoctorUser() {
    try {
      const raw = localStorage.getItem('jeevan_setu_user') || sessionStorage.getItem('jeevan_setu_user');
      if (raw) {
        const u = JSON.parse(raw);
        const rawName = u.full_name || u.name || u.username || 'Dr. Thanush H';
        const formattedName = rawName.startsWith('Dr.') ? rawName : `Dr. ${rawName}`;
        const specialization = (u.doctor_details && u.doctor_details.specialization) || u.specialization || u.department || 'General Medicine';
        let avail = currentDoctorAvailability || 'active';
        if (u.availability) avail = u.availability;
        else if (u.doctor_details && u.doctor_details.availability) avail = u.doctor_details.availability;
        const avatar = u.avatar || 'https://lh3.googleusercontent.com/aida-public/AB6AXuDMEbtSCl4pEF41D5sTxFOToWhBlcIEOBQjfl1K2nHP6aRqaABpczGfDsSDBmg2I1XtDztWaaFaMkIPzuo4g0PjfBw2GwnJoOLiLL3ZkNVB595rBpr-CmvzwhjzLpLSgYHFttDeW1wz13KJLhsrtGXyQEr0uKQ7_TJ6feRDAojxvos5gEWmk2bV96eoeG8262vMS0v1-wWhNvm1RpwjO0bs_Y5R1bfuSxzjm_rlLotdR6LG1TX15vUtrRIBPHD-4alPvgARBNNYmg';
        return {
          name: formattedName,
          dept: specialization,
          avatar: avatar,
          availability: avail
        };
      }
    } catch (e) {}
    return {
      name: 'Dr. Thanush H',
      dept: 'General Medicine',
      avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDMEbtSCl4pEF41D5sTxFOToWhBlcIEOBQjfl1K2nHP6aRqaABpczGfDsSDBmg2I1XtDztWaaFaMkIPzuo4g0PjfBw2GwnJoOLiLL3ZkNVB595rBpr-CmvzwhjzLpLSgYHFttDeW1wz13KJLhsrtGXyQEr0uKQ7_TJ6feRDAojxvos5gEWmk2bV96eoeG8262vMS0v1-wWhNvm1RpwjO0bs_Y5R1bfuSxzjm_rlLotdR6LG1TX15vUtrRIBPHD-4alPvgARBNNYmg',
      availability: currentDoctorAvailability || 'active'
    };
  }

  function renderSharedDoctorHeader() {
    injectDoctorResponsiveStyles();

    let header = document.querySelector('header.doctor-top-header, header[data-purpose="doctor-header"], header');
    if (!header) {
      const mainContainer = document.querySelector('main, .pl-64, body > div');
      header = document.createElement('header');
      if (mainContainer) mainContainer.insertBefore(header, mainContainer.firstChild);
      else document.body.insertBefore(header, document.body.firstChild);
    }

    // Preserve any custom selected ward value if one existed
    let selectedWard = 'ICU - General Ward';
    const existingSelect = header.querySelector('select');
    if (existingSelect && existingSelect.value) {
      selectedWard = existingSelect.value;
    }

    header.className = 'doctor-top-header portal-header bg-[#0b1528] text-white border-b border-slate-700/80 sticky top-0 z-40 transition-all duration-300 shadow-md';
    header.setAttribute('data-purpose', 'doctor-header');

    const pageTitle = getDoctorPageTitle();
    const doc = getStoredDoctorUser();
    const isActive = (currentDoctorAvailability || doc.availability) === 'active';

    header.innerHTML = `
      <!-- ROW 1: [☰ Menu] [Logo / Page Title] [Mobile Profile Avatar] -->
      <div class="doctor-header-row-1 flex items-center justify-between w-full">
        <!-- Left: Hamburger Toggle + Brand / Page Title -->
        <div class="flex items-center gap-2.5 sm:gap-3 flex-shrink-0">
          <button id="doctor-sidebar-toggle" type="button" class="text-slate-300 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors focus:outline-none cursor-pointer flex-shrink-0" aria-label="Toggle navigation menu" onclick="window.toggleMobileDoctorSidebar(event)">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M4 6h16M4 12h16M4 18h16" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path>
            </svg>
          </button>
          <div class="flex items-center gap-2">
            <img src="/assets/jeevan_setu_logo.png" class="w-6 h-6 object-contain hidden sm:inline-block flex-shrink-0" alt="Logo" onerror="this.onerror=null; this.src='../../assets/jeevan_setu_logo.png';" />
            <h2 id="doctor-page-title" class="font-bold text-white text-base sm:text-lg tracking-tight truncate">${escapeHtml(pageTitle)}</h2>
          </div>
        </div>

        <!-- Right (Mobile Only): Profile Avatar with Online indicator -->
        <div class="doctor-header-mobile-profile">
          <div class="relative cursor-pointer p-0.5" id="doctor-mobile-avatar-trigger" title="${escapeHtml(doc.name)} (${escapeHtml(doc.dept)})">
            <img id="doctor-mobile-avatar-img" class="w-8 h-8 rounded-full object-cover ring-2 ring-cyan-500/50 shadow-sm" src="${doc.avatar}" alt="${escapeHtml(doc.name)}" onerror="this.onerror=null; this.src='https://lh3.googleusercontent.com/aida-public/AB6AXuDMEbtSCl4pEF41D5sTxFOToWhBlcIEOBQjfl1K2nHP6aRqaABpczGfDsSDBmg2I1XtDztWaaFaMkIPzuo4g0PjfBw2GwnJoOLiLL3ZkNVB595rBpr-CmvzwhjzLpLSgYHFttDeW1wz13KJLhsrtGXyQEr0uKQ7_TJ6feRDAojxvos5gEWmk2bV96eoeG8262vMS0v1-wWhNvm1RpwjO0bs_Y5R1bfuSxzjm_rlLotdR6LG1TX15vUtrRIBPHD-4alPvgARBNNYmg';" />
            <span id="doctor-mobile-avatar-dot" class="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full ${isActive ? 'bg-emerald-500' : 'bg-rose-500'} ring-2 ring-[#0b1528]"></span>
          </div>
        </div>
      </div>

      <!-- ROW 2: [Ward Selector] [Active/Inactive Availability] [Sync Indicator] [Desktop Profile] -->
      <div class="doctor-header-row-2 flex items-center justify-between w-full">
        <!-- Left: Ward Selector -->
        <div class="doctor-header-ward-wrap relative flex items-center">
          <select id="doctor-ward-select" class="bg-slate-800 text-slate-200 border border-slate-700 text-xs rounded-lg px-2.5 py-1.5 focus:ring-1 focus:ring-cyan-500 focus:outline-none cursor-pointer">
            <option value="ICU - General Ward" ${selectedWard === 'ICU - General Ward' ? 'selected' : ''}>ICU - General Ward</option>
            <option value="HDU - Cardiac" ${selectedWard === 'HDU - Cardiac' ? 'selected' : ''}>HDU - Cardiac</option>
            <option value="ICU - Trauma" ${selectedWard === 'ICU - Trauma' ? 'selected' : ''}>ICU - Trauma</option>
            <option value="HDU - Step-down" ${selectedWard === 'HDU - Step-down' ? 'selected' : ''}>HDU - Step-down</option>
          </select>
        </div>

        <!-- Right: Availability + Sync Indicator + Desktop Profile -->
        <div class="flex items-center gap-2 sm:gap-3 flex-shrink-0">
          <!-- Availability Controls -->
          <div id="doctor-availability-wrapper" class="flex items-center flex-shrink-0">
            <div id="doctor-availability-container" class="flex items-center bg-slate-800/80 p-0.5 rounded-lg border border-slate-700 shadow-2xs select-none" data-availability="${currentDoctorAvailability}">
              <button id="doc-btn-active" type="button" onclick="window.changeDoctorAvailability('active')"
                class="flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer shadow-xs ${isActive ? 'bg-emerald-600 text-white border border-emerald-600' : 'text-slate-400 hover:text-white hover:bg-white/10 border border-transparent'} focus:outline-none" title="Set working availability to Active">
                <span class="w-2 h-2 rounded-full ${isActive ? 'bg-white animate-pulse' : 'bg-emerald-500 hidden'}"></span>
                <span>Active</span>
              </button>
              <button id="doc-btn-inactive" type="button" onclick="window.changeDoctorAvailability('inactive')"
                class="flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer ${!isActive ? 'bg-rose-600 text-white border border-rose-600' : 'text-slate-400 hover:text-white hover:bg-white/10 border border-transparent'} focus:outline-none" title="Set working availability to Inactive">
                <span class="w-2 h-2 rounded-full ${!isActive ? 'bg-white animate-pulse' : 'bg-rose-500 hidden'}"></span>
                <span>Inactive</span>
              </button>
            </div>
          </div>

          <!-- Live Sync Freshness -->
          <div id="doctor-sync-indicator-wrap" class="flex items-center">
            <div id="doctor-sync-indicator" class="js-sync-indicator inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 cursor-pointer select-none transition-all shadow-xs hover:bg-emerald-500/20" title="Data automatically refreshing every 5s • Click to sync now">
              <span data-sync-dot class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span data-sync-text id="doctor-sync-text">Live</span>
            </div>
          </div>

          <!-- Desktop Profile Block (Hidden on mobile via responsive_unified.css) -->
          <div class="doctor-header-desktop-profile flex items-center space-x-3 border-l border-slate-700/80 pl-3 sm:pl-4">
            <div class="text-right">
              <p class="text-xs sm:text-sm font-bold text-white leading-tight"><span id="header-doctor-name" class="doctor-profile-name">${escapeHtml(doc.name)}</span></p>
              <p class="text-[11px] text-slate-400 leading-tight mt-0.5"><span id="header-doctor-dept" class="doctor-profile-dept">${escapeHtml(doc.dept)}</span></p>
              <div class="flex items-center justify-end">
                <span id="doctor-desktop-dot" class="w-2 h-2 rounded-full ${isActive ? 'bg-emerald-500' : 'bg-rose-500'} mr-1"></span>
                <span id="doctor-desktop-online-label" class="text-[10px] text-slate-400">${isActive ? 'Online' : 'Offline'}</span>
              </div>
            </div>
            <img id="desktop-doctor-avatar" alt="Doctor Portrait" class="w-9 h-9 sm:w-10 sm:h-10 rounded-full object-cover border-2 border-slate-700 shadow-sm" src="${doc.avatar}" onerror="this.onerror=null; this.src='https://lh3.googleusercontent.com/aida-public/AB6AXuDMEbtSCl4pEF41D5sTxFOToWhBlcIEOBQjfl1K2nHP6aRqaABpczGfDsSDBmg2I1XtDztWaaFaMkIPzuo4g0PjfBw2GwnJoOLiLL3ZkNVB595rBpr-CmvzwhjzLpLSgYHFttDeW1wz13KJLhsrtGXyQEr0uKQ7_TJ6feRDAojxvos5gEWmk2bV96eoeG8262vMS0v1-wWhNvm1RpwjO0bs_Y5R1bfuSxzjm_rlLotdR6LG1TX15vUtrRIBPHD-4alPvgARBNNYmg';" />
          </div>
        </div>
      </div>

      <!-- ROW 3: Secondary info (Doctor Name • Dept • Online Status) -->
      <div class="doctor-header-row-3 flex items-center justify-between w-full text-[11px] pt-1 text-slate-400 border-t border-slate-700/60">
        <span id="doctor-row3-name-dept" class="truncate font-medium">${escapeHtml(doc.name)} • ${escapeHtml(doc.dept)}</span>
        <span id="doctor-row3-status" class="flex items-center gap-1.5 font-semibold ${isActive ? 'text-emerald-400' : 'text-rose-400'}">
          <span class="w-1.5 h-1.5 rounded-full ${isActive ? 'bg-emerald-400' : 'bg-rose-400'} animate-pulse"></span>
          <span>${isActive ? 'Duty Active' : 'Duty Inactive'}</span>
        </span>
      </div>
    `;
  }

  function injectDoctorAvailabilityControls() {
    if (document.getElementById('doctor-availability-container')) return;

    const header = document.querySelector('header');
    if (!header) return;

    // Look for doctor profile container on the right side of the header
    const profileContainer = header.querySelector('.border-l, #doctor-profile-container, .doctor-profile-name')?.closest('.flex.items-center') ||
                             header.querySelector('.doctor-profile-name')?.parentElement?.parentElement;
    if (!profileContainer) return;

    const wrapper = document.createElement('div');
    wrapper.id = 'doctor-availability-wrapper';
    wrapper.className = 'border-l pl-2 sm:pl-3 lg:pl-6 flex items-center flex-shrink-0 gap-3';
    wrapper.innerHTML = `
      <div id="doctor-sync-indicator-wrap" class="flex items-center">
        <div id="doctor-sync-indicator" class="js-sync-indicator inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 cursor-pointer select-none transition-all shadow-xs hover:bg-emerald-500/20" title="Data automatically refreshing every 5s • Click to sync now">
          <span data-sync-dot class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span data-sync-text id="doctor-sync-text">Live</span>
        </div>
      </div>
      <div id="doctor-availability-container" class="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200 shadow-2xs select-none" data-availability="active">
        <button id="doc-btn-active" type="button" onclick="window.changeDoctorAvailability('active')"
          class="flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer shadow-xs bg-emerald-600 text-white border border-emerald-600 focus:outline-none" title="Set working availability to Active">
          <span class="w-2 h-2 rounded-full bg-white animate-pulse"></span>
          <span>Active</span>
        </button>
        <button id="doc-btn-inactive" type="button" onclick="window.changeDoctorAvailability('inactive')"
          class="flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 border border-transparent focus:outline-none" title="Set working availability to Inactive">
          <span class="w-2 h-2 rounded-full bg-rose-500 hidden"></span>
          <span>Inactive</span>
        </button>
      </div>
    `;

    profileContainer.parentNode.insertBefore(wrapper, profileContainer);
  }

  function updateDoctorAvailabilityUI(status, isUpdating = false) {
    currentDoctorAvailability = status;
    const container = document.getElementById('doctor-availability-container');
    const btnActive = document.getElementById('doc-btn-active');
    const btnInactive = document.getElementById('doc-btn-inactive');

    if (container) container.setAttribute('data-availability', status);

    const activeClasses = 'flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer shadow-xs bg-emerald-600 text-white border border-emerald-600 focus:outline-none';
    const inactiveSelectedClasses = 'flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer shadow-xs bg-rose-600 text-white border border-rose-600 focus:outline-none';
    const unselectedClasses = 'flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer text-slate-400 hover:text-white hover:bg-white/10 border border-transparent focus:outline-none';

    if (btnActive && btnInactive) {
      if (status === 'inactive') {
        btnActive.className = unselectedClasses;
        btnActive.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500 hidden"></span><span>Active</span>`;
        btnInactive.className = inactiveSelectedClasses;
        btnInactive.innerHTML = `<span class="w-2 h-2 rounded-full bg-white animate-pulse"></span><span>Inactive</span>`;
      } else {
        btnActive.className = activeClasses;
        btnActive.innerHTML = `<span class="w-2 h-2 rounded-full bg-white animate-pulse"></span><span>Active</span>`;
        btnInactive.className = unselectedClasses;
        btnInactive.innerHTML = `<span class="w-2 h-2 rounded-full bg-rose-500 hidden"></span><span>Inactive</span>`;
      }

      if (isUpdating) {
        btnActive.disabled = true;
        btnInactive.disabled = true;
        btnActive.classList.add('opacity-60', 'cursor-not-allowed', 'pointer-events-none');
        btnInactive.classList.add('opacity-60', 'cursor-not-allowed', 'pointer-events-none');
      } else {
        btnActive.disabled = false;
        btnInactive.disabled = false;
        btnActive.classList.remove('opacity-60', 'cursor-not-allowed', 'pointer-events-none');
        btnInactive.classList.remove('opacity-60', 'cursor-not-allowed', 'pointer-events-none');
      }
    }

    // Update mobile avatar status dot
    const mobileDot = document.getElementById('doctor-mobile-avatar-dot');
    if (mobileDot) {
      mobileDot.className = `absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full ${status === 'active' ? 'bg-emerald-500' : 'bg-rose-500'} ring-2 ring-[#0b1528]`;
    }

    // Update desktop status dot & text
    const desktopDot = document.getElementById('doctor-desktop-dot');
    if (desktopDot) {
      desktopDot.className = `w-2 h-2 rounded-full ${status === 'active' ? 'bg-emerald-500' : 'bg-rose-500'} mr-1`;
    }
    const desktopLabel = document.getElementById('doctor-desktop-online-label');
    if (desktopLabel) {
      desktopLabel.textContent = status === 'active' ? 'Online' : 'Offline';
    }

    // Update Row 3 status
    const row3Status = document.getElementById('doctor-row3-status');
    if (row3Status) {
      row3Status.className = `flex items-center gap-1.5 font-semibold ${status === 'active' ? 'text-emerald-400' : 'text-rose-400'}`;
      row3Status.innerHTML = `
        <span class="w-1.5 h-1.5 rounded-full ${status === 'active' ? 'bg-emerald-400' : 'bg-rose-400'} animate-pulse"></span>
        <span>${status === 'active' ? 'Duty Active' : 'Duty Inactive'}</span>
      `;
    }
  }

  function escapeModalHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function injectAvailabilityModalStyles() {
    if (document.getElementById('jeevan-availability-modal-styles')) return;
    const style = document.createElement('style');
    style.id = 'jeevan-availability-modal-styles';
    style.textContent = `
      .js-avail-modal-backdrop {
        position: fixed;
        inset: 0;
        background-color: rgba(10, 15, 29, 0.78);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        z-index: 999999;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 1rem;
        opacity: 0;
        transition: opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      }
      .js-avail-modal-backdrop.js-modal-open {
        opacity: 1;
      }
      .js-avail-modal-backdrop.js-modal-closing {
        opacity: 0;
      }
      .js-avail-modal-card {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 1rem;
        width: 100%;
        max-width: 28rem;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.05);
        overflow: hidden;
        color: #f1f5f9;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        transform: scale(0.95) translateY(8px);
        transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
      }
      .js-avail-modal-backdrop.js-modal-open .js-avail-modal-card {
        transform: scale(1) translateY(0);
      }
      .js-avail-modal-backdrop.js-modal-closing .js-avail-modal-card {
        transform: scale(0.95) translateY(8px);
      }
      .js-avail-modal-header {
        padding: 1.125rem 1.25rem;
        border-bottom: 1px solid rgba(51, 65, 85, 0.7);
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #0f172a;
      }
      .js-avail-modal-title-wrap {
        display: flex;
        align-items: center;
        gap: 0.75rem;
      }
      .js-avail-modal-icon-badge {
        width: 2.25rem;
        height: 2.25rem;
        border-radius: 0.5rem;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }
      .js-avail-modal-icon-badge.active {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.35);
        color: #34d399;
      }
      .js-avail-modal-icon-badge.inactive {
        background: rgba(244, 63, 94, 0.15);
        border: 1px solid rgba(244, 63, 94, 0.35);
        color: #fb7185;
      }
      .js-avail-modal-title {
        font-size: 1rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
        line-height: 1.25;
      }
      .js-avail-modal-subtitle {
        font-size: 0.6875rem;
        font-weight: 500;
        color: #94a3b8;
        margin: 0.15rem 0 0 0;
        letter-spacing: 0.03em;
        text-transform: uppercase;
      }
      .js-avail-modal-close {
        background: transparent;
        border: none;
        color: #94a3b8;
        cursor: pointer;
        padding: 0.375rem;
        border-radius: 0.375rem;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.15s ease;
      }
      .js-avail-modal-close:hover {
        color: #ffffff;
        background: rgba(255, 255, 255, 0.08);
      }
      .js-avail-modal-body {
        padding: 1.25rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
      }
      .js-avail-modal-message {
        font-size: 0.875rem;
        line-height: 1.5;
        color: #cbd5e1;
        margin: 0;
      }
      .js-avail-modal-status-box {
        border-radius: 0.75rem;
        padding: 0.875rem 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.375rem;
        border: 1px solid #334155;
        background: #1e293b;
      }
      .js-avail-modal-status-box.active {
        background: rgba(6, 78, 59, 0.22);
        border-color: rgba(16, 185, 129, 0.35);
      }
      .js-avail-modal-status-box.inactive {
        background: rgba(136, 19, 55, 0.22);
        border-color: rgba(244, 63, 94, 0.35);
      }
      .js-avail-modal-status-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .js-avail-modal-status-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.03em;
      }
      .js-avail-modal-status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.25rem 0.625rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.02em;
      }
      .js-avail-modal-status-badge.badge-active {
        background: #059669;
        color: #ffffff;
      }
      .js-avail-modal-status-badge.badge-inactive {
        background: #e11d48;
        color: #ffffff;
      }
      .js-avail-dot {
        width: 0.5rem;
        height: 0.5rem;
        border-radius: 9999px;
        background: #ffffff;
        display: inline-block;
      }
      .js-avail-dot.dot-active {
        animation: jsModalPulse 1.8s infinite;
      }
      .js-avail-modal-status-desc {
        font-size: 0.75rem;
        color: #94a3b8;
        margin: 0;
        line-height: 1.4;
      }
      .js-avail-modal-error {
        background: rgba(225, 29, 72, 0.15);
        border: 1px solid rgba(225, 29, 72, 0.45);
        color: #fecdd3;
        padding: 0.625rem 0.75rem;
        border-radius: 0.5rem;
        font-size: 0.75rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        line-height: 1.35;
      }
      .js-avail-modal-footer {
        padding: 1rem 1.25rem;
        background: #0f172a;
        border-top: 1px solid rgba(51, 65, 85, 0.7);
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 0.75rem;
      }
      .js-avail-btn-cancel {
        background: #1e293b;
        border: 1px solid #334155;
        color: #cbd5e1;
        font-size: 0.8125rem;
        font-weight: 600;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        cursor: pointer;
        transition: all 0.15s ease;
      }
      .js-avail-btn-cancel:hover:not(:disabled) {
        background: #334155;
        color: #ffffff;
      }
      .js-avail-btn-confirm {
        background: #2563eb;
        border: 1px solid #1d4ed8;
        color: #ffffff;
        font-size: 0.8125rem;
        font-weight: 600;
        padding: 0.5rem 1.15rem;
        border-radius: 0.5rem;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.25);
        transition: all 0.15s ease;
      }
      .js-avail-btn-confirm:hover:not(:disabled) {
        background: #1d4ed8;
      }
      .js-avail-btn-cancel:disabled,
      .js-avail-btn-confirm:disabled,
      .js-avail-modal-close:disabled {
        opacity: 0.6;
        cursor: not-allowed;
        pointer-events: none;
      }
      @keyframes jsModalPulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.45; transform: scale(0.9); }
      }
    `;
    document.head.appendChild(style);
  }

  function showAvailabilityConfirmModal({ roleTitle, targetStatus, onConfirm, onCancel }) {
    injectAvailabilityModalStyles();

    // Remove any existing availability modal
    const existing = document.getElementById('jeevan-availability-modal');
    if (existing) existing.remove();

    const previousFocusedElement = document.activeElement;
    const isTargetActive = targetStatus === 'active';
    const targetLabel = isTargetActive ? 'Active' : 'Inactive';

    const modalBackdrop = document.createElement('div');
    modalBackdrop.id = 'jeevan-availability-modal';
    modalBackdrop.className = 'js-avail-modal-backdrop';
    modalBackdrop.setAttribute('role', 'dialog');
    modalBackdrop.setAttribute('aria-modal', 'true');
    modalBackdrop.setAttribute('aria-labelledby', 'availability-modal-title');
    modalBackdrop.setAttribute('aria-describedby', 'availability-modal-desc');

    const iconSvg = isTargetActive
      ? `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`
      : `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;

    modalBackdrop.innerHTML = `
      <div class="js-avail-modal-card" id="availability-modal-card">
        <div class="js-avail-modal-header">
          <div class="js-avail-modal-title-wrap">
            <div class="js-avail-modal-icon-badge ${isTargetActive ? 'active' : 'inactive'}">
              ${iconSvg}
            </div>
            <div>
              <h3 id="availability-modal-title" class="js-avail-modal-title">Confirm Availability Change</h3>
              <p class="js-avail-modal-subtitle">${escapeModalHtml(roleTitle)} Availability</p>
            </div>
          </div>
          <button type="button" class="js-avail-modal-close" id="availability-modal-close-btn" aria-label="Close dialog">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>

        <div class="js-avail-modal-body">
          <p id="availability-modal-desc" class="js-avail-modal-message">
            Are you sure you want to change your working availability to <strong class="${isTargetActive ? 'text-emerald-400' : 'text-rose-400'}">${targetLabel}</strong>?
          </p>

          <div class="js-avail-modal-status-box ${isTargetActive ? 'active' : 'inactive'}">
            <div class="js-avail-modal-status-row">
              <span class="js-avail-modal-status-label">Selected Status</span>
              <span class="js-avail-modal-status-badge ${isTargetActive ? 'badge-active' : 'badge-inactive'}">
                <i class="js-avail-dot ${isTargetActive ? 'dot-active' : ''}"></i>
                <span>${targetLabel}</span>
              </span>
            </div>
            <p class="js-avail-modal-status-desc">
              ${isTargetActive 
                ? 'You will be marked available for active clinical duties and patient assignment.' 
                : 'You will be marked off-duty. Existing patient records and transfers remain assigned to you.'}
            </p>
          </div>

          <div id="availability-modal-error" class="js-avail-modal-error" style="display: none;" role="alert">
            <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            <span id="availability-modal-error-text"></span>
          </div>
        </div>

        <div class="js-avail-modal-footer">
          <button type="button" id="availability-modal-cancel-btn" class="js-avail-btn-cancel">
            Cancel
          </button>
          <button type="button" id="availability-modal-confirm-btn" class="js-avail-btn-confirm">
            <span id="availability-modal-spinner" style="display: none;">
              <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            </span>
            <span id="availability-modal-confirm-text">Confirm</span>
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(modalBackdrop);
    const originalBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // Animate in
    requestAnimationFrame(() => {
      modalBackdrop.classList.add('js-modal-open');
    });

    const closeBtn = modalBackdrop.querySelector('#availability-modal-close-btn');
    const cancelBtn = modalBackdrop.querySelector('#availability-modal-cancel-btn');
    const confirmBtn = modalBackdrop.querySelector('#availability-modal-confirm-btn');
    const spinner = modalBackdrop.querySelector('#availability-modal-spinner');
    const confirmText = modalBackdrop.querySelector('#availability-modal-confirm-text');
    const errorBox = modalBackdrop.querySelector('#availability-modal-error');
    const errorText = modalBackdrop.querySelector('#availability-modal-error-text');

    // Focus Confirm button initially
    if (confirmBtn) confirmBtn.focus();

    let isSubmitting = false;

    function closeModal(confirmedResult = false) {
      if (isSubmitting && !confirmedResult) return;

      document.removeEventListener('keydown', handleKeydown);
      modalBackdrop.classList.remove('js-modal-open');
      modalBackdrop.classList.add('js-modal-closing');

      setTimeout(() => {
        document.body.style.overflow = originalBodyOverflow;
        modalBackdrop.remove();
        if (previousFocusedElement && typeof previousFocusedElement.focus === 'function') {
          try { previousFocusedElement.focus(); } catch (e) {}
        }
        if (!confirmedResult && typeof onCancel === 'function') {
          onCancel();
        }
      }, 200);
    }

    function handleKeydown(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeModal(false);
      } else if (e.key === 'Tab') {
        const focusable = modalBackdrop.querySelectorAll('button:not([disabled]), [tabindex]:not([tabindex="-1"])');
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    }

    document.addEventListener('keydown', handleKeydown);

    // Close on backdrop click (click outside modal card)
    modalBackdrop.addEventListener('click', (e) => {
      if (e.target === modalBackdrop && !isSubmitting) {
        closeModal(false);
      }
    });

    closeBtn.addEventListener('click', () => {
      if (!isSubmitting) closeModal(false);
    });

    cancelBtn.addEventListener('click', () => {
      if (!isSubmitting) closeModal(false);
    });

    confirmBtn.addEventListener('click', async () => {
      if (isSubmitting) return;
      isSubmitting = true;

      // Loading state
      confirmBtn.disabled = true;
      cancelBtn.disabled = true;
      closeBtn.disabled = true;
      spinner.style.display = 'inline-block';
      confirmText.textContent = 'Updating...';
      errorBox.style.display = 'none';

      try {
        await onConfirm();
        closeModal(true);
      } catch (err) {
        isSubmitting = false;
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
        closeBtn.disabled = false;
        spinner.style.display = 'none';
        confirmText.textContent = 'Confirm';

        const message = err.message || 'Failed to update availability. Please try again.';
        errorText.textContent = message;
        errorBox.style.display = 'flex';
      }
    });
  }

  window.changeDoctorAvailability = function (targetStatus) {
    if (isDoctorAvailabilityUpdating) return;
    if (targetStatus === currentDoctorAvailability) return;

    showAvailabilityConfirmModal({
      roleTitle: 'Doctor',
      targetStatus: targetStatus,
      onConfirm: async () => {
        isDoctorAvailabilityUpdating = true;
        updateDoctorAvailabilityUI(targetStatus, true);

        const token = getAuthToken();
        const res = await fetch('/api/doctor/availability', {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': token ? `Bearer ${token}` : ''
          },
          credentials: 'include',
          body: JSON.stringify({ availability: targetStatus })
        });

        const data = await res.json().catch(() => ({}));

        if (res.ok && data.success) {
          currentDoctorAvailability = targetStatus;
          updateDoctorAvailabilityUI(targetStatus, false);

          // Update cached user in storage
          try {
            const uStr = localStorage.getItem('jeevan_setu_user');
            if (uStr) {
              const u = JSON.parse(uStr);
              u.availability = targetStatus;
              if (u.doctor_details) u.doctor_details.availability = targetStatus;
              localStorage.setItem('jeevan_setu_user', JSON.stringify(u));
            }
          } catch (e) {}

          const targetLabel = targetStatus === 'active' ? 'Active' : 'Inactive';
          showAvailabilityToast(`Doctor availability set to ${targetLabel}.`, 'success');
          isDoctorAvailabilityUpdating = false;
        } else {
          isDoctorAvailabilityUpdating = false;
          updateDoctorAvailabilityUI(currentDoctorAvailability, false);
          const errorMsg = data.error || data.message || `Server returned status ${res.status}`;
          showAvailabilityToast(`Failed to update availability: ${errorMsg}`, 'error');
          throw new Error(errorMsg);
        }
      },
      onCancel: () => {
        updateDoctorAvailabilityUI(currentDoctorAvailability, false);
      }
    });
  };

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

    const row3NameDept = document.getElementById('doctor-row3-name-dept');
    if (row3NameDept) row3NameDept.textContent = `${formattedName} • ${specialization}`;

    if (user.avatar) {
      const dAvatar = document.getElementById('desktop-doctor-avatar');
      if (dAvatar) dAvatar.src = user.avatar;
      const mAvatar = document.getElementById('doctor-mobile-avatar-img');
      if (mAvatar) mAvatar.src = user.avatar;
    }

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

    // 6. Update Doctor Availability Selector
    if (user.availability) {
      currentDoctorAvailability = user.availability;
    } else if (user.doctor_details && user.doctor_details.availability) {
      currentDoctorAvailability = user.doctor_details.availability;
    }
    updateDoctorAvailabilityUI(currentDoctorAvailability, false);
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

  async function syncDoctorAvailability() {
    if (isDoctorAvailabilityUpdating) return;
    try {
      const res = await fetch('/api/doctor/availability', {
        headers: getAuthHeaders(),
        credentials: 'include'
      });
      if (res.ok) {
        const json = await res.json();
        const avail = json.availability || (json.data && json.data.availability);
        if (avail && avail !== currentDoctorAvailability && !isDoctorAvailabilityUpdating) {
          currentDoctorAvailability = avail;
          updateDoctorAvailabilityUI(avail, false);
          try {
            const uStr = localStorage.getItem('jeevan_setu_user');
            if (uStr) {
              const u = JSON.parse(uStr);
              u.availability = avail;
              if (u.doctor_details) u.doctor_details.availability = avail;
              localStorage.setItem('jeevan_setu_user', JSON.stringify(u));
            }
          } catch (e) {}
        }
      }
    } catch (e) {
      console.warn('[Doctor Sidebar] Availability poll error:', e);
    }
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
    renderSharedDoctorHeader();
    setupMobileDoctorDrawer();
    highlightActiveSidebarItem();
    updateDoctorAvailabilityUI(currentDoctorAvailability, false);
    syncLiveDoctorHeader();
    if (window.AutoRefreshManager) {
      window.AutoRefreshManager.attachIndicator('#doctor-sync-indicator-wrap');
      window.AutoRefreshManager.start('doctor_sidebar_badges', fetchSidebarBadgeCounts, 5000);
      window.AutoRefreshManager.start('doctor_availability_sync', syncDoctorAvailability, 5000);
    } else {
      fetchSidebarBadgeCounts();
      setInterval(fetchSidebarBadgeCounts, 5000);
      setInterval(syncDoctorAvailability, 5000);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDoctorSidebar);
  } else {
    initDoctorSidebar();
  }
})();
