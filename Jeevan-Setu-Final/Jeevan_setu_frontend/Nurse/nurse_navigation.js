/**
 * nurse_navigation.js — Single Source of Truth for Jeevan Setu Nurse Portal
 * Standardized Shared Header & Sidebar Navigation across all Nurse Pages.
 * 
 * Features:
 * - Unified branding: [Icon] Nurse Station
 * - Dynamic Patient Search (database-backed with /patients/nurse-search) + CTRL+K shortcut
 * - Dynamic Notifications bell with live unread badge & notification dropdown
 * - Dynamic Nurse user identity & ward (from authenticated session/localStorage)
 * - Profile avatar with interactive dropdown menu (My Patients, Patient Monitoring, Settings, Logout)
 * - Sidebar navigation with active link highlighting & responsive drawer support
 */

(function () {
  const DEFAULT_NURSE_AVATAR = '../nurse_avatar.jpg';

  const NURSE_NAV_CONFIG = [
    {
      category: 'Patient Care',
      items: [
        {
          id: 'dashboard',
          label: 'Dashboard',
          href: '../Nurse_dashboard/Nurse_dashboard.html',
          match: ['nurse_dashboard', 'dashboard'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 5a1 1 0 011-1h4a1 1 0 011 1v5a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v2a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zM14 12a1 1 0 011-1h4a1 1 0 011 1v7a1 1 0 01-1 1h-4a1 1 0 01-1-1v-7z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'my_patients',
          label: 'My Patients',
          href: '../Nurse_my_patients/Nurse_my_patients.html',
          match: ['nurse_my_patients', 'my_patients'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'alerts',
          label: 'Alerts',
          href: '../Nurse_alerts/Nurse_alerts.html',
          match: ['nurse_alerts', 'alerts'],
          badge: '6',
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'patient_monitoring',
          label: 'Patient Monitoring',
          href: '../nurse_patient_monitoring/nurse_patient_monitoring.html',
          match: ['nurse_patient_monitoring', 'patient_monitoring', 'monitoring'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'enter_vitals',
          label: 'Enter Vitals',
          href: '../Nurse_enter_vitals/Nurse_enter_vitals.html',
          match: ['nurse_enter_vitals', 'enter_vitals', 'vitals'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'nursing_notes',
          label: 'Nursing Notes',
          href: '../Nurse_nursing_notes/Nurse_nursing_notes.html',
          match: ['nurse_nursing_notes', 'nursing_notes', 'notes'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        }
      ]
    }
  ];

  function detectCurrentNursePage() {
    const path = window.location.pathname.toLowerCase();

    if (path.includes('nurse_dashboard')) return 'dashboard';
    if (path.includes('nurse_my_patients')) return 'my_patients';
    if (path.includes('nurse_patient_monitoring')) return 'patient_monitoring';
    if (path.includes('nurse_enter_vitals')) return 'enter_vitals';
    if (path.includes('nurse_nursing_notes')) return 'nursing_notes';
    if (path.includes('nurse_settings') || path.includes('settings')) return 'settings';
    if (path.includes('nurse_alerts')) return 'alerts';
    if (path.includes('nurse_tasks')) {
      window.location.replace('../Nurse_alerts/Nurse_alerts.html?tab=tasks');
      return 'alerts';
    }
    if (path.includes('nurse_transfers')) {
      window.location.replace('../Nurse_dashboard/Nurse_dashboard.html');
      return 'dashboard';
    }
    if (path.includes('nurse_reports')) {
      window.location.replace('../Nurse_dashboard/Nurse_dashboard.html');
      return 'dashboard';
    }

    return 'dashboard';
  }

  function getStoredNurseUser() {
    try {
      const raw = localStorage.getItem('jeevan_setu_user') || sessionStorage.getItem('jeevan_setu_user');
      if (raw) {
        const u = JSON.parse(raw);
        if (u.role && u.role.toLowerCase() === 'nurse') {
          const nd = u.nurse_details || {};
          return {
            id: u.id || u.user_id,
            name: u.full_name || u.name || u.username || 'Nurse',
            username: u.username || 'nurse',
            role: 'Staff Nurse',
            ward: u.ward || nd.ward_assignment || u.department || 'Ward',
            email: u.email || `${u.username || 'nurse'}@jeevansetu.in`,
            avatar: u.avatar || DEFAULT_NURSE_AVATAR
          };
        }
      }
    } catch (e) {
      console.warn('Could not parse stored nurse user:', e);
    }
    return {
      id: null,
      name: 'Nurse',
      username: 'nurse',
      role: 'Staff Nurse',
      ward: 'Ward',
      email: 'nurse@jeevansetu.in',
      avatar: DEFAULT_NURSE_AVATAR
    };
  }

  async function syncLiveNurseHeader() {
    try {
      const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token') || '';
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = 'Bearer ' + token;

      const res = await fetch('/api/v1/auth/me', { headers });
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data && json.data.role && json.data.role.toLowerCase() === 'nurse') {
          const u = json.data;
          const nd = u.nurse_details || {};
          const name = u.full_name || u.username || 'Nurse';
          const ward = u.ward || nd.ward_assignment || u.department || 'Ward';
          const avatar = u.avatar || DEFAULT_NURSE_AVATAR;

          // Sync storage
          localStorage.setItem('jeevan_setu_user', JSON.stringify(u));

          // Update header DOM elements if present
          document.querySelectorAll('.nurse-profile-name, #header-nurse-name, #topbar-nurse-name').forEach(el => {
            el.textContent = name;
          });
          document.querySelectorAll('#header-nurse-ward, #topbar-nurse-ward').forEach(el => {
            el.textContent = ward;
          });
          document.querySelectorAll('#header-nurse-avatar, #topbar-nurse-avatar').forEach(el => {
            if (el.tagName === 'IMG') el.src = avatar;
          });
        }
      }
    } catch (err) {
      console.warn('Nurse header sync warning:', err);
    }
  }

  function injectNurseStyles() {
    if (document.getElementById('nurse-unified-theme-styles')) return;
    const style = document.createElement('style');
    style.id = 'nurse-unified-theme-styles';
    style.textContent = `
      .nurse-top-header {
        background-color: #ffffff !important;
        border-bottom: 1px solid #e2e8f0 !important;
        color: #0f172a !important;
        height: 64px !important;
        min-height: 64px !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05) !important;
      }
      .nurse-header-search-wrap {
        background-color: #f8fafc !important;
        border: 1px solid #cbd5e1 !important;
        transition: all 0.2s ease-in-out;
      }
      .nurse-header-search-wrap:focus-within {
        border-color: #004ac6 !important;
        box-shadow: 0 0 0 2px rgba(0, 74, 198, 0.18) !important;
        background-color: #ffffff !important;
      }
      .nurse-ctrl-k-badge {
        background-color: #f1f5f9 !important;
        color: #64748b !important;
        border: 1px solid #cbd5e1 !important;
        font-family: inherit;
        letter-spacing: 0.04em;
      }
      .nurse-dropdown-menu {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 20px 25px -5px rgba(15, 23, 42, 0.15), 0 8px 10px -6px rgba(15, 23, 42, 0.1) !important;
      }
      .nurse-search-dropdown {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        box-shadow: 0 25px 50px -12px rgba(15, 23, 42, 0.2) !important;
      }
      .sidebar-transition {
        transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    min-width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    max-width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    opacity 0.25s ease,
                    padding 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
      }
      aside[data-purpose="sidebar"],
      aside.w-64,
      aside {
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    width 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
      }
      @media (max-width: 1024px) {
        aside[data-purpose="sidebar"],
        aside.w-64,
        aside {
          transform: translateX(-100%) !important;
          position: fixed !important;
          left: 0 !important;
          top: 0 !important;
          bottom: 0 !important;
          z-index: 50 !important;
        }
        body.sidebar-mobile-open aside[data-purpose="sidebar"],
        body.sidebar-mobile-open aside.w-64,
        body.sidebar-mobile-open aside {
          transform: translateX(0) !important;
          width: 16rem !important;
          min-width: 16rem !important;
          max-width: 16rem !important;
          opacity: 1 !important;
          pointer-events: auto !important;
        }
        .pl-64 {
          padding-left: 0 !important;
        }
        .left-64 {
          left: 0 !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function renderNurseSidebar() {
    let aside = document.querySelector('aside[data-purpose="sidebar"], aside.w-64, aside.w-72, aside');
    if (!aside) return;

    const currentActiveId = detectCurrentNursePage();

    aside.setAttribute('data-purpose', 'sidebar');
    aside.className = 'w-64 bg-[#0f172a] text-slate-300 flex flex-col flex-shrink-0 h-screen fixed left-0 top-0 z-50 shadow-xl select-none -translate-x-full md:translate-x-0 transition-transform duration-200 ease-in-out';

    // Mobile backdrop
    let backdrop = document.getElementById('nurse-sidebar-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'nurse-sidebar-backdrop';
      backdrop.className = 'fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-40 md:hidden hidden transition-opacity';
      backdrop.onclick = window.toggleMobileNurseSidebar;
      document.body.appendChild(backdrop);
    }

    // 1. Branding Header
    const brandingHeaderHtml = `
      <div class="p-4 flex items-center justify-between border-b border-slate-700/50 flex-shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-white rounded-full flex items-center justify-center p-1 shadow-sm flex-shrink-0">
            <svg class="w-7 h-7 text-[#004ac6]" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"></path>
            </svg>
          </div>
          <div>
            <h1 class="font-bold text-white text-sm tracking-wide leading-tight uppercase font-heading">JEEVAN SETU</h1>
            <p class="text-[10px] text-slate-400 leading-tight uppercase mt-0.5 tracking-wider font-semibold">ICU TO HDU TRANSFER SUPPORT SYSTEM</p>
          </div>
        </div>
        <button class="md:hidden text-slate-400 hover:text-white p-1 rounded-lg" onclick="window.toggleMobileNurseSidebar();" aria-label="Close sidebar">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
        </button>
      </div>
    `;

    // 2. Navigation Items
    let navSectionsHtml = '';

    NURSE_NAV_CONFIG.forEach(section => {
      navSectionsHtml += `
        <div class="space-y-1">
          <p class="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">${section.category}</p>
          <ul class="space-y-1">
      `;

      section.items.forEach(item => {
        const isActive = item.id === currentActiveId;
        const activeClass = isActive
          ? 'bg-blue-600 text-white font-semibold shadow-md'
          : 'text-slate-300 hover:bg-slate-800/80 hover:text-white transition-colors';

        navSectionsHtml += `
          <li>
            <a class="flex items-center justify-between px-3 py-2.5 rounded-lg ${activeClass} text-sm group" href="${item.href}">
              <div class="flex items-center gap-3">
                ${item.icon}
                <span class="text-xs font-medium tracking-wide">${item.label}</span>
              </div>
              ${item.badge ? `<span class="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">${item.badge}</span>` : ''}
            </a>
          </li>
        `;
      });

      navSectionsHtml += `
          </ul>
        </div>
      `;
    });

    // 3. Bottom Utility Menu (Collapsible 'More' section)
    const isMoreExpanded = (currentActiveId === 'settings') || sessionStorage.getItem('jeevan_setu_nurse_sidebar_more') === 'true';

    const isSettingsActive = currentActiveId === 'settings';
    const settingsLinkClass = isSettingsActive
      ? 'bg-blue-600 text-white font-semibold shadow-md'
      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60';
    const settingsIconClass = isSettingsActive ? 'text-white' : 'text-slate-400';

    const bottomNavHtml = `
      <div class="p-2.5 border-t border-slate-700/50 flex-shrink-0 bg-[#0c1322]">
        <button id="nurse-sidebar-more-toggle" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800/80 transition-all text-xs font-medium focus:outline-none select-none cursor-pointer" aria-expanded="${isMoreExpanded}" aria-controls="nurse-sidebar-more-menu">
          <div class="flex items-center gap-2.5">
            <svg class="w-4 h-4 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
            <span>More</span>
          </div>
          <svg id="nurse-sidebar-more-icon" class="w-4 h-4 text-slate-400 transition-transform duration-200 ${isMoreExpanded ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M19 9l-7 7-7-7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
        </button>

        <div id="nurse-sidebar-more-menu" class="space-y-1 mt-1 overflow-hidden transition-all duration-300 ${isMoreExpanded ? 'max-h-48 opacity-100' : 'max-h-0 opacity-0 pointer-events-none hidden'}">
          <a class="flex items-center gap-3 px-3 py-2 rounded-lg ${settingsLinkClass} transition-colors text-xs" href="../Nurse_settings/Nurse_settings.html">
            <svg class="w-4 h-4 ${settingsIconClass}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
            <span>Settings</span>
          </a>
          <a class="flex items-center gap-3 px-3 py-2 rounded-lg text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors text-xs font-semibold cursor-pointer" href="javascript:void(0);" onclick="window.logoutNurse();">
            <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
            <span>Logout</span>
          </a>
        </div>
      </div>
    `;

    aside.innerHTML = `
      ${brandingHeaderHtml}
      <nav class="flex-1 overflow-y-auto py-3 px-3 space-y-5 custom-scrollbar">
        ${navSectionsHtml}
      </nav>
      ${bottomNavHtml}
    `;

    setupNurseSidebarMoreToggle();
    standardizePageLayout();
  }

  function setupNurseSidebarMoreToggle() {
    const toggleBtn = document.getElementById('nurse-sidebar-more-toggle');
    const menuEl = document.getElementById('nurse-sidebar-more-menu');
    const iconEl = document.getElementById('nurse-sidebar-more-icon');
    if (!toggleBtn || !menuEl) return;

    toggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const isHidden = menuEl.classList.contains('hidden') || menuEl.classList.contains('max-h-0');
      if (isHidden) {
        menuEl.classList.remove('hidden', 'max-h-0', 'opacity-0', 'pointer-events-none');
        menuEl.classList.add('max-h-48', 'opacity-100');
        if (iconEl) iconEl.classList.add('rotate-180');
        toggleBtn.setAttribute('aria-expanded', 'true');
        sessionStorage.setItem('jeevan_setu_nurse_sidebar_more', 'true');
      } else {
        menuEl.classList.add('max-h-0', 'opacity-0', 'pointer-events-none');
        menuEl.classList.remove('max-h-48', 'opacity-100');
        if (iconEl) iconEl.classList.remove('rotate-180');
        toggleBtn.setAttribute('aria-expanded', 'false');
        sessionStorage.setItem('jeevan_setu_nurse_sidebar_more', 'false');
        setTimeout(() => {
          if (toggleBtn.getAttribute('aria-expanded') === 'false') {
            menuEl.classList.add('hidden');
          }
        }, 300);
      }
    });
  }

  function renderSharedNurseHeader() {
    injectNurseStyles();

    let header = document.querySelector('header.nurse-top-header, header[data-purpose="nurse-header"], header');
    if (!header) {
      const mainContainer = document.querySelector('main, .pl-64, .pl-0, body > div');
      header = document.createElement('header');
      if (mainContainer) {
        mainContainer.insertBefore(header, mainContainer.firstChild);
      } else {
        document.body.insertBefore(header, document.body.firstChild);
      }
    }

    header.className = 'nurse-top-header bg-white text-slate-900 border-b border-slate-200/90 h-16 flex items-center justify-between px-6 fixed top-0 left-0 md:left-64 right-0 z-40 shadow-sm transition-all duration-200';
    header.setAttribute('data-purpose', 'nurse-header');

    const user = getStoredNurseUser();

    header.innerHTML = `
      <!-- LEFT SECTION: Mobile Hamburger + Nurse Station Branding -->
      <div class="flex items-center gap-3 md:gap-4 flex-shrink-0">
        <!-- Mobile Sidebar Hamburger Toggle -->
        <button id="nurse-sidebar-toggle" class="md:hidden text-slate-600 hover:text-slate-900 p-1.5 rounded-lg hover:bg-slate-100 transition-colors focus:outline-none" aria-label="Toggle menu">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M4 6h16M4 12h16M4 18h16" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
        </button>

        <!-- Nurse Station Brand -->
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm flex-shrink-0">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M9 12h6m-3-3v6m9-3a9 9 0 11-18 0 9 9 0 0118 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
          </div>
          <div>
            <h1 class="font-bold text-slate-900 text-base leading-tight tracking-tight">Nurse Station</h1>
          </div>
        </div>
      </div>

      <!-- CENTER / SEARCH SECTION: Live Patient Search with CTRL+K -->
      <div class="relative flex-1 max-w-xs sm:max-w-sm md:max-w-md mx-3 md:mx-6" id="nurse-search-container">
        <div class="nurse-header-search-wrap flex items-center rounded-lg px-3 py-1.5 w-full relative">
          <svg class="w-4 h-4 text-slate-400 flex-shrink-0 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
          <input 
            id="nurse-global-search-input" 
            class="w-full bg-transparent border-none outline-none text-xs sm:text-sm text-slate-800 placeholder-slate-400 focus:ring-0 p-0" 
            placeholder="Search patients..." 
            type="text"
            autocomplete="off"
            spellcheck="false"
          />
          <kbd class="nurse-ctrl-k-badge hidden sm:inline-block text-[10px] font-semibold text-slate-500 px-1.5 py-0.5 rounded ml-2 flex-shrink-0 select-none shadow-xs">CTRL + K</kbd>
        </div>

        <!-- Live Search Results Dropdown -->
        <div id="nurse-search-results-dropdown" class="nurse-search-dropdown absolute left-0 right-0 top-full mt-2 rounded-xl border border-slate-200 bg-white p-2 shadow-2xl z-50 hidden max-h-[420px] overflow-y-auto">
          <div id="nurse-search-results-content">
            <!-- Populated dynamically via search API -->
          </div>
        </div>
      </div>

      <!-- RIGHT SECTION: Notifications Bell + Dynamic Nurse Profile -->
      <div class="flex items-center gap-3 sm:gap-4 flex-shrink-0">
        
        <!-- Notifications Bell Button & Dropdown -->
        <div class="relative" id="nurse-notifications-container">
          <button id="nurse-notifications-btn" class="relative p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer focus:outline-none" title="Notifications">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
            <span id="nurse-notif-badge" class="absolute -top-1 -right-1 bg-red-600 text-white text-[10px] font-bold h-4 min-w-[16px] px-1 flex items-center justify-center rounded-full border border-white shadow-sm" style="display: none;">0</span>
          </button>

          <!-- Notifications Dropdown Panel -->
          <div id="nurse-notifications-dropdown" class="nurse-dropdown-menu absolute right-0 top-full mt-2 w-80 sm:w-96 rounded-xl border border-slate-200 bg-white p-0 shadow-2xl z-50 hidden overflow-hidden">
            <div class="p-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div class="flex items-center space-x-2">
                <span class="text-sm font-bold text-slate-900">Notifications</span>
                <span id="nurse-notif-count-pill" class="text-[10px] bg-blue-100 text-blue-700 font-semibold px-2 py-0.5 rounded-full border border-blue-200">Live</span>
              </div>
              <button id="nurse-mark-read-btn" class="text-xs text-blue-600 hover:text-blue-800 transition-colors font-medium cursor-pointer">Mark all as read</button>
            </div>
            <div id="nurse-notifications-list" class="max-h-72 overflow-y-auto divide-y divide-slate-100">
              <!-- Live notifications injected here -->
            </div>
            <div class="p-2.5 bg-slate-50 border-t border-slate-200 text-center">
              <a href="../Nurse_alerts/Nurse_alerts.html" class="text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors block py-1">View All Alerts &rarr;</a>
            </div>
          </div>
        </div>

        <!-- Nurse Profile Trigger & Dropdown -->
        <div class="relative" id="nurse-profile-container">
          <div id="nurse-profile-trigger" class="flex items-center gap-2.5 sm:gap-3 cursor-pointer p-1 rounded-lg hover:bg-slate-100 transition-colors select-none">
            <div class="text-right hidden sm:block">
              <p id="header-nurse-name" class="text-xs sm:text-sm font-bold text-slate-900 leading-tight nurse-profile-name">${escapeHtml(user.name)}</p>
              <p id="header-nurse-ward" class="text-[11px] font-medium text-slate-500 leading-tight mt-0.5">${escapeHtml(user.ward)}</p>
            </div>
            <div class="w-9 h-9 rounded-full overflow-hidden ring-2 ring-blue-600/30 bg-blue-50 flex items-center justify-center flex-shrink-0">
              <img id="header-nurse-avatar" alt="Avatar" class="w-full h-full object-cover" src="${user.avatar}" onerror="this.onerror=null; this.src='../nurse_avatar.jpg';"/>
            </div>
            <svg id="header-nurse-chevron" class="w-4 h-4 text-slate-400 transition-transform duration-200 hidden sm:block" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M19 9l-7 7-7-7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
          </div>

          <!-- Profile Dropdown Menu -->
          <div id="nurse-profile-dropdown" class="nurse-dropdown-menu absolute right-0 top-full mt-2 w-64 rounded-xl border border-slate-200 bg-white p-2 shadow-2xl z-50 hidden">
            <!-- User Summary -->
            <div class="px-3 py-2.5 border-b border-slate-100 mb-1">
              <p class="text-xs font-bold text-slate-900">${escapeHtml(user.name)}</p>
              <p class="text-[11px] text-slate-500 truncate">${escapeHtml(user.email)}</p>
              <div class="mt-1.5 flex items-center gap-1.5">
                <span class="inline-block text-[10px] bg-blue-50 text-blue-700 font-semibold px-2 py-0.5 rounded-full border border-blue-200">${escapeHtml(user.role)}</span>
                <span class="inline-block text-[10px] bg-emerald-50 text-emerald-700 font-semibold px-2 py-0.5 rounded-full border border-emerald-200">${escapeHtml(user.ward)}</span>
              </div>
            </div>

            <!-- Navigation Links -->
            <a href="../Nurse_my_patients/Nurse_my_patients.html" class="flex items-center space-x-2.5 px-3 py-2 text-xs text-slate-700 hover:text-blue-700 hover:bg-blue-50/60 rounded-lg transition-colors">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
              <span>My Patients</span>
            </a>

            <a href="../nurse_patient_monitoring/nurse_patient_monitoring.html" class="flex items-center space-x-2.5 px-3 py-2 text-xs text-slate-700 hover:text-blue-700 hover:bg-blue-50/60 rounded-lg transition-colors">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
              <span>Patient Monitoring</span>
            </a>

            <a href="../Nurse_enter_vitals/Nurse_enter_vitals.html" class="flex items-center space-x-2.5 px-3 py-2 text-xs text-slate-700 hover:text-blue-700 hover:bg-blue-50/60 rounded-lg transition-colors">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
              <span>Enter Vitals</span>
            </a>

            <a href="../Nurse_settings/Nurse_settings.html" class="flex items-center space-x-2.5 px-3 py-2 text-xs text-slate-700 hover:text-blue-700 hover:bg-blue-50/60 rounded-lg transition-colors">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
              <span>Account Settings</span>
            </a>

            <div class="border-t border-slate-100 my-1"></div>

            <a href="javascript:alert('Jeevan Setu Nurse Help: Contact Nurse In-Charge or IT Support at Ext. 204');" class="flex items-center space-x-2.5 px-3 py-2 text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-lg transition-colors">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
              <span>Help &amp; Guidelines</span>
            </a>

            <div class="border-t border-slate-100 my-1"></div>

            <!-- Logout -->
            <button onclick="window.logoutNurse()" class="w-full text-left flex items-center space-x-2.5 px-3 py-2 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors cursor-pointer">
              <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
              <span class="font-semibold">Sign Out</span>
            </button>
          </div>
        </div>

      </div>
    `;

    setupNurseHeaderInteractions();
    fetchLiveNurseNotifications();
  }

  function setupNurseHeaderInteractions() {
    // 1. Mobile Sidebar Toggle
    const sidebarToggle = document.getElementById('nurse-sidebar-toggle');
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', (e) => {
        e.preventDefault();
        window.toggleMobileNurseSidebar();
      });
    }

    // 2. CTRL + K Shortcut Listener
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        const searchInput = document.getElementById('nurse-global-search-input');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
          openNurseSearchDropdown();
        }
      }
      if (e.key === 'Escape') {
        closeAllNurseHeaderDropdowns();
      }
    });

    // 3. Search Input & Autocomplete
    const searchInput = document.getElementById('nurse-global-search-input');
    const searchDropdown = document.getElementById('nurse-search-results-dropdown');
    let searchDebounceTimer = null;

    if (searchInput) {
      searchInput.addEventListener('focus', () => {
        openNurseSearchDropdown();
      });

      searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
          performNursePatientSearch(query);
        }, 200);
      });

      // Keyboard navigation
      searchInput.addEventListener('keydown', (e) => {
        const items = searchDropdown ? searchDropdown.querySelectorAll('.nurse-search-item') : [];
        if (!items.length) return;

        let activeIdx = Array.from(items).findIndex(el => el.classList.contains('bg-slate-100'));

        if (e.key === 'ArrowDown') {
          e.preventDefault();
          if (activeIdx >= 0) items[activeIdx].classList.remove('bg-slate-100');
          activeIdx = (activeIdx + 1) % items.length;
          items[activeIdx].classList.add('bg-slate-100');
          items[activeIdx].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          if (activeIdx >= 0) items[activeIdx].classList.remove('bg-slate-100');
          activeIdx = (activeIdx - 1 + items.length) % items.length;
          items[activeIdx].classList.add('bg-slate-100');
          items[activeIdx].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'Enter') {
          if (activeIdx >= 0 && items[activeIdx]) {
            e.preventDefault();
            items[activeIdx].click();
          }
        }
      });
    }

    // 4. Notifications Dropdown Toggle
    const notifBtn = document.getElementById('nurse-notifications-btn');
    const notifDropdown = document.getElementById('nurse-notifications-dropdown');
    if (notifBtn && notifDropdown) {
      notifBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = notifDropdown.classList.contains('hidden');
        closeAllNurseHeaderDropdowns();
        if (isHidden) notifDropdown.classList.remove('hidden');
      });
    }

    const markReadBtn = document.getElementById('nurse-mark-read-btn');
    if (markReadBtn) {
      markReadBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        markAllNurseNotificationsRead();
      });
    }

    // 5. Profile Dropdown Toggle
    const profileTrigger = document.getElementById('nurse-profile-trigger');
    const profileDropdown = document.getElementById('nurse-profile-dropdown');
    const profileChevron = document.getElementById('header-nurse-chevron');
    if (profileTrigger && profileDropdown) {
      profileTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = profileDropdown.classList.contains('hidden');
        closeAllNurseHeaderDropdowns();
        if (isHidden) {
          profileDropdown.classList.remove('hidden');
          if (profileChevron) profileChevron.classList.add('rotate-180');
        }
      });
    }

    // Click outside to close
    document.addEventListener('click', (e) => {
      const searchContainer = document.getElementById('nurse-search-container');
      const notifContainer = document.getElementById('nurse-notifications-container');
      const profileContainer = document.getElementById('nurse-profile-container');

      if (!searchContainer?.contains(e.target) &&
          !notifContainer?.contains(e.target) &&
          !profileContainer?.contains(e.target)) {
        closeAllNurseHeaderDropdowns();
      }
    });
  }

  function closeAllNurseHeaderDropdowns() {
    const searchDropdown = document.getElementById('nurse-search-results-dropdown');
    const notifDropdown = document.getElementById('nurse-notifications-dropdown');
    const profileDropdown = document.getElementById('nurse-profile-dropdown');
    const profileChevron = document.getElementById('header-nurse-chevron');

    if (searchDropdown) searchDropdown.classList.add('hidden');
    if (notifDropdown) notifDropdown.classList.add('hidden');
    if (profileDropdown) profileDropdown.classList.add('hidden');
    if (profileChevron) profileChevron.classList.remove('rotate-180');
  }

  function openNurseSearchDropdown() {
    const searchDropdown = document.getElementById('nurse-search-results-dropdown');
    const searchInput = document.getElementById('nurse-global-search-input');
    if (!searchDropdown) return;

    searchDropdown.classList.remove('hidden');
    const query = searchInput ? searchInput.value.trim() : '';
    if (!query) {
      renderNurseSearchSuggestions();
    } else {
      performNursePatientSearch(query);
    }
  }

  function renderNurseSearchSuggestions() {
    const content = document.getElementById('nurse-search-results-content');
    if (!content) return;

    content.innerHTML = `
      <div class="py-2 px-1">
        <p class="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2 px-2">Quick Navigation</p>
        <div class="grid grid-cols-2 gap-2">
          <a href="../Nurse_my_patients/Nurse_my_patients.html" class="nurse-search-item flex items-center space-x-2.5 p-2 rounded-lg bg-slate-50 hover:bg-blue-50 text-xs text-slate-700 transition-colors">
            <span class="w-6 h-6 rounded-md bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs">P</span>
            <span class="font-medium">My Patients</span>
          </a>
          <a href="../nurse_patient_monitoring/nurse_patient_monitoring.html" class="nurse-search-item flex items-center space-x-2.5 p-2 rounded-lg bg-slate-50 hover:bg-blue-50 text-xs text-slate-700 transition-colors">
            <span class="w-6 h-6 rounded-md bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-xs">M</span>
            <span class="font-medium">Monitoring</span>
          </a>
          <a href="../Nurse_enter_vitals/Nurse_enter_vitals.html" class="nurse-search-item flex items-center space-x-2.5 p-2 rounded-lg bg-slate-50 hover:bg-blue-50 text-xs text-slate-700 transition-colors">
            <span class="w-6 h-6 rounded-md bg-purple-100 text-purple-700 flex items-center justify-center font-bold text-xs">V</span>
            <span class="font-medium">Enter Vitals</span>
          </a>
          <a href="../Nurse_alerts/Nurse_alerts.html" class="nurse-search-item flex items-center space-x-2.5 p-2 rounded-lg bg-slate-50 hover:bg-blue-50 text-xs text-slate-700 transition-colors">
            <span class="w-6 h-6 rounded-md bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-xs">A</span>
            <span class="font-medium">Alerts</span>
          </a>
        </div>
      </div>
      <div class="pt-2 border-t border-slate-100 mt-2 flex items-center justify-between text-[11px] text-slate-400 px-2">
        <span>Type patient name, UHID, ward or bed</span>
        <span>Esc to close</span>
      </div>
    `;
  }

  async function performNursePatientSearch(query) {
    const content = document.getElementById('nurse-search-results-content');
    if (!content) return;

    if (!query) {
      renderNurseSearchSuggestions();
      return;
    }

    content.innerHTML = `
      <div class="py-6 text-center text-slate-400">
        <svg class="w-5 h-5 animate-spin mx-auto mb-2 text-blue-600" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span class="text-xs">Searching authorized patients...</span>
      </div>
    `;

    try {
      const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const res = await fetch(`/patients/nurse-search?q=${encodeURIComponent(query)}`, { headers });
      const data = await res.json();

      if (!data.success || !data.data || data.data.length === 0) {
        content.innerHTML = `
          <div class="py-6 text-center text-slate-500">
            <svg class="w-7 h-7 mx-auto mb-2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-width="1.5"></path>
            </svg>
            <p class="text-xs font-semibold text-slate-700">No matching patients found</p>
            <p class="text-[11px] text-slate-400 mt-0.5">No authorized patient matches "${escapeHtml(query)}"</p>
          </div>
        `;
        return;
      }

      let html = '<div class="space-y-1.5 py-1">';
      html += `
        <div class="flex items-center justify-between px-2 mb-1">
          <span class="text-[11px] font-bold text-blue-700 uppercase tracking-wider">Patients Found (${data.count})</span>
        </div>
      `;

      data.data.forEach(p => {
        const riskClass = p.risk_level === 'high' || p.ews_score >= 5
          ? 'bg-red-50 text-red-700 border-red-200'
          : p.risk_level === 'medium' || p.ews_score >= 3
          ? 'bg-amber-50 text-amber-700 border-amber-200'
          : 'bg-emerald-50 text-emerald-700 border-emerald-200';

        html += `
          <a href="../nurse_patient_monitoring/nurse_patient_monitoring.html?patient_id=${encodeURIComponent(p.patient_id)}&patient=${encodeURIComponent(p.name)}" class="nurse-search-item block p-2.5 rounded-lg hover:bg-blue-50/70 border border-transparent hover:border-blue-100 transition-colors">
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-2.5 min-w-0">
                <div class="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs flex-shrink-0">
                  ${escapeHtml(p.name.substring(0, 1))}
                </div>
                <div class="truncate">
                  <p class="text-xs font-bold text-slate-900 leading-tight">${escapeHtml(p.name)} <span class="text-[10px] text-slate-500 font-mono font-normal">(${escapeHtml(p.patient_code)})</span></p>
                  <p class="text-[11px] text-slate-500 truncate mt-0.5">${escapeHtml(p.diagnosis || 'Clinical Care')}</p>
                </div>
              </div>
              <div class="text-right flex-shrink-0 ml-2 space-y-0.5">
                <span class="inline-block text-[10px] bg-slate-100 text-slate-700 font-medium px-2 py-0.5 rounded border border-slate-200">${escapeHtml(p.ward_name || 'Ward')} • ${escapeHtml(p.bed_number || 'Bed')}</span>
                <span class="block text-[9px] font-bold px-1.5 py-0.2 rounded border uppercase text-center ${riskClass}">EWS ${p.ews_score}</span>
              </div>
            </div>
          </a>
        `;
      });

      html += `
        </div>
        <div class="pt-2 border-t border-slate-100 mt-2 flex items-center justify-between text-[10px] text-slate-400 px-2">
          <span>${data.count} patient(s) found</span>
          <span>&uarr;&darr; to navigate &middot; &crarr; to open</span>
        </div>
      `;

      content.innerHTML = html;
    } catch (e) {
      console.error('Error searching patients:', e);
      content.innerHTML = `
        <div class="py-4 text-center text-xs text-red-500">
          Failed to load search results. Please try again.
        </div>
      `;
    }
  }

  async function fetchLiveNurseNotifications() {
    try {
      const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const res = await fetch('/api/v1/notifications?limit=6', { headers });
      const data = await res.json();

      const badge = document.getElementById('nurse-notif-badge');
      const countPill = document.getElementById('nurse-notif-count-pill');
      const list = document.getElementById('nurse-notifications-list');

      if (!list) return;

      const unreadCount = data.unread_count || 0;

      if (badge) {
        if (unreadCount > 0) {
          badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
          badge.style.display = 'flex';
        } else {
          badge.style.display = 'none';
        }
      }

      if (countPill) {
        countPill.textContent = unreadCount > 0 ? `${unreadCount} Unread` : 'All caught up';
      }

      const notifs = data.data || [];
      if (!notifs.length) {
        list.innerHTML = `
          <div class="py-8 px-4 text-center text-slate-500">
            <svg class="w-8 h-8 mx-auto mb-2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" stroke-width="1.5"></path>
            </svg>
            <p class="text-xs font-semibold text-slate-700">No Notifications</p>
            <p class="text-[11px] text-slate-400 mt-0.5">All patient alerts and monitoring tasks are clear.</p>
          </div>
        `;
        return;
      }

      let html = '';
      notifs.forEach(n => {
        const isUnread = !n.is_read;
        const dot = isUnread ? '<span class="w-2 h-2 rounded-full bg-blue-600 flex-shrink-0 mt-1"></span>' : '';
        const timeAgo = formatTimeAgo(n.created_at);

        html += `
          <div class="p-3 hover:bg-slate-50 transition-colors cursor-pointer flex items-start space-x-2.5 ${isUnread ? 'bg-blue-50/40' : ''}">
            ${dot}
            <div class="flex-1 min-w-0">
              <p class="text-xs font-semibold text-slate-900 leading-tight">${escapeHtml(n.title || n.subject || 'Patient Care Alert')}</p>
              <p class="text-[11px] text-slate-600 mt-0.5 leading-snug">${escapeHtml(n.message || n.body || '')}</p>
              <span class="text-[10px] text-slate-400 mt-1 block font-medium">${timeAgo}</span>
            </div>
          </div>
        `;
      });
      list.innerHTML = html;
    } catch (e) {
      console.warn('Could not fetch nurse notifications:', e);
    }
  }

  async function markAllNurseNotificationsRead() {
    try {
      const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      await fetch('/api/v1/notifications/read-all', { method: 'POST', headers });
      fetchLiveNurseNotifications();
    } catch (e) {
      console.warn('Could not mark nurse notifications as read:', e);
    }
  }

  function standardizePageLayout() {
    document.body.classList.add('bg-slate-50', 'text-slate-900');
    
    // Standardize Content Container Offset (pl-0 md:pl-64)
    const contentWrappers = document.querySelectorAll('.pl-72, .ml-72, .pl-64, .ml-64');
    contentWrappers.forEach(el => {
      el.classList.remove('pl-72', 'ml-72', 'pl-64', 'ml-64');
      el.classList.add('pl-0', 'md:pl-64');
    });

    const aside = document.querySelector('aside[data-purpose="sidebar"], aside');
    if (aside && aside.nextElementSibling) {
      const nextEl = aside.nextElementSibling;
      if (nextEl.tagName.toLowerCase() === 'main' || nextEl.classList.contains('flex-1') || nextEl.classList.contains('min-h-screen')) {
        if (!nextEl.classList.contains('md:pl-64') && !nextEl.classList.contains('pl-64')) {
          nextEl.classList.add('pl-0', 'md:pl-64');
        }
      }
    }
  }

  window.toggleMobileNurseSidebar = function () {
    const aside = document.querySelector('aside[data-purpose="sidebar"], aside.w-64, aside');
    const backdrop = document.getElementById('nurse-sidebar-backdrop');
    if (!aside) return;

    const isClosed = aside.classList.contains('-translate-x-full');
    if (isClosed) {
      aside.classList.remove('-translate-x-full');
      if (backdrop) backdrop.classList.remove('hidden');
    } else {
      aside.classList.add('-translate-x-full');
      if (backdrop) backdrop.classList.add('hidden');
    }
  };

  window.logoutNurse = function () {
    localStorage.removeItem('jeevan_setu_token');
    localStorage.removeItem('jeevan_setu_user');
    sessionStorage.clear();
    window.location.href = '../../Login/Login.html';
  };

  function auditNursePortalControls() {
    // Clean up any legacy pagination container if present
    document.querySelectorAll('.nurse-portal-pagination, .admin-portal-pagination, nav[aria-label*="Pages Navigation"]').forEach(el => el.remove());

    // 1. Task Checkboxes interactivity
    document.querySelectorAll('input[type="checkbox"]').forEach(chk => {
      chk.addEventListener('change', function() {
        const textSpan = this.closest('div')?.querySelector('.font-headline-sm');
        if (textSpan) {
          if (this.checked) {
            textSpan.classList.add('line-through', 'text-slate-400');
          } else {
            textSpan.classList.remove('line-through', 'text-slate-400');
          }
        }
      });
    });

    // 2. Alert Acknowledge & Response buttons
    document.querySelectorAll('button').forEach(btn => {
      const text = btn.textContent.trim().toLowerCase();
      if (text.includes('acknowledge') || text.includes('respond now') || text.includes('mark administered') || text.includes('snooze') || text.includes('assign porter') || text.includes('review request')) {
        if (!btn.hasAttribute('data-audit-bound')) {
          btn.setAttribute('data-audit-bound', 'true');
          btn.addEventListener('click', function(e) {
            if (this.closest('form')) return;
            const parentCard = this.closest('.bg-surface-container-low') || this.closest('.bg-surface') || this.closest('.rounded-xl');
            if (parentCard) {
              const prevText = this.innerHTML;
              this.innerHTML = '<span class="inline-flex items-center gap-1 text-emerald-600 font-semibold"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg> Done</span>';
              parentCard.style.opacity = '0.6';
              setTimeout(() => {
                this.innerHTML = prevText;
                parentCard.style.opacity = '1';
              }, 2500);
            }
          });
        }
      }
    });

    // 3. Nursing Notes "Save Note" action
    const saveNoteBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim().toLowerCase() === 'save note');
    const noteTextarea = document.querySelector('textarea');
    if (saveNoteBtn && noteTextarea && !saveNoteBtn.hasAttribute('data-audit-bound')) {
      saveNoteBtn.setAttribute('data-audit-bound', 'true');
      saveNoteBtn.addEventListener('click', function() {
        const val = noteTextarea.value.trim();
        if (!val) {
          alert('Please enter clinical note details before saving.');
          noteTextarea.focus();
          return;
        }
        const prevText = saveNoteBtn.innerHTML;
        saveNoteBtn.innerHTML = 'Saved Successfully!';
        saveNoteBtn.classList.add('bg-green-600');
        setTimeout(() => {
          saveNoteBtn.innerHTML = prevText;
          saveNoteBtn.classList.remove('bg-green-600');
          noteTextarea.value = '';
        }, 2000);
      });
    }

    // 4. Report Print/View actions
    document.querySelectorAll('button').forEach(btn => {
      const text = btn.textContent.trim().toLowerCase();
      if ((text.includes('pdf') || text.includes('print')) && !btn.hasAttribute('data-audit-bound')) {
        btn.setAttribute('data-audit-bound', 'true');
        btn.addEventListener('click', function() {
          window.print();
        });
      }
    });
  }

  function formatTimeAgo(dateStr) {
    if (!dateStr) return 'Just now';
    try {
      const date = new Date(dateStr);
      const diffMs = Date.now() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d ago`;
    } catch (e) {
      return 'Recently';
    }
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Initialize shared Nurse Portal Layout
  function initNursePortal() {
    renderNurseSidebar();
    renderSharedNurseHeader();
    auditNursePortalControls();
    syncLiveNurseHeader();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNursePortal);
  } else {
    initNursePortal();
  }
})();
