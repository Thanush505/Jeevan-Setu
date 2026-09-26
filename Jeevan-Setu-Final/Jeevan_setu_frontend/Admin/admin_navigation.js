/**
 * admin_navigation.js — Single Source of Truth for Jeevan Setu Admin Navigation & Top Header
 * Standardizes the top navbar across all Admin pages with live search, CTRL+K shortcut,
 * live notifications, system alerts, fullscreen toggle, authenticated profile, and sidebar collapse.
 */

(function () {
  const DEFAULT_ADMIN_AVATAR = '../admin_avatar.jpg';

  const ADMIN_NAV_CONFIG = [
    {
      type: 'single',
      id: 'dashboard',
      label: 'Dashboard',
      href: '../Administrator_dashboard_/Administrator_dashboard_.html',
      match: ['administrator_dashboard', 'dashboard'],
      icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
    },
    {
      type: 'group',
      category: 'Management',
      items: [
        {
          id: 'patients',
          label: 'Patients',
          href: '../Admin_patient_management/Admin_patient_management.html',
          match: ['admin_patient_management', 'patient_management', 'patient'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'beds_wards',
          label: 'Beds & Wards',
          href: '../Admin_beds_wards/Admin_beds_wards.html',
          match: ['admin_beds_wards', 'beds_wards', 'bed', 'ward', 'resource_utilization', 'admin_resource_utilization'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'users_roles',
          label: 'Users & Roles',
          href: '../Admin_users_roles/Admin_users_roles.html',
          match: ['admin_users_roles', 'users_roles', 'users'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'attendants_qr',
          label: 'Attendants (QR Access)',
          href: '../Admin_attendant_access/Admin_attendant_access.html',
          match: ['admin_attendant_access', 'attendant_access', 'attendant'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        }
      ]
    },
    {
      type: 'group',
      category: 'Monitoring & Analytics',
      items: [
        {
          id: 'ews_analytics',
          label: 'EWS Analytics',
          href: '../Admin_ews_analytics/Admin_ews_analytics.html',
          match: ['admin_ews_analytics', 'ews_analytics'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'reports',
          label: 'Reports',
          href: '../Admin_clinical_reports/Admin_clinical_reports.html',
          match: ['admin_clinical_reports', 'clinical_reports', 'reports'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'audit_logs',
          label: 'Audit Logs',
          href: '../Admin_audit_logs/Admin_audit_logs.html',
          match: ['admin_audit_logs', 'audit_logs', 'audit'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        }
      ]
    },
    {
      type: 'group',
      category: 'System Settings',
      items: [
        {
          id: 'system_settings',
          label: 'System Settings',
          href: '../Admin_system_settings/Admin_system_settings.html',
          match: ['admin_system_settings', 'system_settings'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'notification_settings',
          label: 'Notifications',
          href: '../Admin_notification_settings/Admin_notification_settings.html',
          match: ['admin_notification_settings', 'notification_settings', 'notifications'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        },
        {
          id: 'backup_restore',
          label: 'Backup & Restore',
          href: '../Admin_backup_restore/Admin_backup_restore.html',
          match: ['admin_backup_restore', 'backup_restore', 'backup'],
          icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>`
        }
      ]
    }
  ];

  function detectCurrentPage() {
    const path = window.location.pathname.toLowerCase();
    if (path.includes('admin_attendant_access') || path.includes('attendant')) return 'attendants_qr';
    if (path.includes('admin_patient_management') || path.includes('patient_management')) return 'patients';
    if (path.includes('admin_beds_wards') || path.includes('beds_wards') || path.includes('resource_utilization')) return 'beds_wards';
    if (path.includes('admin_users_roles') || path.includes('users_roles')) return 'users_roles';
    if (path.includes('admin_ews_analytics') || path.includes('ews_analytics')) return 'ews_analytics';
    if (path.includes('admin_clinical_reports') || path.includes('clinical_reports') || path.includes('reports')) return 'reports';
    if (path.includes('admin_audit_logs') || path.includes('audit_logs')) return 'audit_logs';
    if (path.includes('admin_system_settings') || path.includes('system_settings')) return 'system_settings';
    if (path.includes('admin_notification_settings') || path.includes('notification_settings')) return 'notification_settings';
    if (path.includes('admin_backup_restore') || path.includes('backup_restore')) return 'backup_restore';
    if (path.includes('administrator_dashboard') || path.includes('dashboard')) return 'dashboard';
    return 'dashboard';
  }

  function getStoredAdminUser() {
    try {
      const u = localStorage.getItem('jeevan_setu_user') || sessionStorage.getItem('jeevan_setu_user');
      if (u) {
        const parsed = JSON.parse(u);
        return {
          id: parsed.id || parsed.user_id || 1,
          name: parsed.full_name || parsed.username || 'Admin User',
          username: parsed.username || 'admin_js',
          role: (parsed.role === 'admin' ? 'Administrator' : (parsed.role || 'Administrator')),
          email: parsed.email || 'admin@jeevansetu.org',
          avatar: parsed.avatar_url || DEFAULT_ADMIN_AVATAR
        };
      }
    } catch (e) {
      console.warn('Could not parse stored admin user:', e);
    }
    return {
      id: 1,
      name: 'Admin User',
      username: 'admin_js',
      role: 'Administrator',
      email: 'admin@jeevansetu.org',
      avatar: DEFAULT_ADMIN_AVATAR
    };
  }

  function injectAdminStyles() {
    if (document.getElementById('admin-unified-theme-styles')) return;
    const style = document.createElement('style');
    style.id = 'admin-unified-theme-styles';
    style.textContent = `
      .admin-top-header {
        background-color: #111827 !important;
        border-bottom: 1px solid #1f2937 !important;
        color: #f8fafc !important;
        height: 64px !important;
        min-height: 64px !important;
      }
      .admin-header-search-wrap {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        transition: all 0.2s ease-in-out;
      }
      .admin-header-search-wrap:focus-within {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25) !important;
        background-color: #0f172a !important;
      }
      .admin-ctrl-k-badge {
        background-color: #334155 !important;
        color: #94a3b8 !important;
        border: 1px solid #475569 !important;
        font-family: inherit;
        letter-spacing: 0.05em;
      }
      .admin-dropdown-menu {
        background-color: #0f172a !important;
        border: 1px solid #334155 !important;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5) !important;
      }
      .admin-search-dropdown {
        background-color: #0f172a !important;
        border: 1px solid #334155 !important;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7) !important;
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
        transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    min-width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    max-width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    opacity 0.25s ease,
                    padding 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
      }
      body.sidebar-collapsed aside[data-purpose="sidebar"],
      body.sidebar-collapsed aside.w-64,
      body.sidebar-collapsed aside {
        width: 0 !important;
        min-width: 0 !important;
        max-width: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-left: 0 !important;
        border: none !important;
        overflow: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
        transform: translateX(-100%) !important;
      }
      body.sidebar-collapsed .pl-64 {
        padding-left: 0 !important;
      }
      body.sidebar-collapsed .left-64,
      body.sidebar-collapsed header.fixed,
      body.sidebar-collapsed header.left-64,
      body.sidebar-collapsed header[data-purpose="admin-header"].fixed {
        left: 0 !important;
      }
      body.sidebar-collapsed main,
      body.sidebar-collapsed .pl-64 > main,
      body.sidebar-collapsed .flex-1 {
        width: 100% !important;
        max-width: 100% !important;
      }
      .pl-64, .left-64, header {
        transition: padding-left 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    left 0.3s cubic-bezier(0.4, 0, 0.2, 1),
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

  function renderSidebarNav() {
    const aside = document.querySelector('aside[data-purpose="sidebar"], aside.w-64, aside');
    if (!aside) return;

    aside.setAttribute('data-purpose', 'sidebar');
    aside.classList.add('sidebar-transition');

    const nav = aside.querySelector('nav');
    if (!nav) return;

    const currentActiveId = detectCurrentPage();
    let navHtml = '';

    ADMIN_NAV_CONFIG.forEach(sec => {
      if (sec.type === 'single') {
        const isActive = sec.id === currentActiveId;
        const activeClass = isActive
          ? 'bg-blue-600 text-white font-medium shadow-md'
          : 'text-slate-300 hover:bg-white/10 transition-colors font-medium';

        navHtml += `
          <div>
            <a class="flex items-center space-x-3 px-4 py-2.5 rounded-lg ${activeClass}" href="${sec.href}">
              ${sec.icon}
              <span>${sec.label}</span>
            </a>
          </div>
        `;
      } else if (sec.type === 'group') {
        navHtml += `
          <div>
            <p class="text-slate-400 text-[10px] font-bold uppercase tracking-widest mb-3 px-4">${sec.category}</p>
            <ul class="space-y-1.5">
        `;

        sec.items.forEach(item => {
          const isActive = item.id === currentActiveId;
          const activeClass = isActive
            ? 'bg-blue-600 text-white font-medium shadow-md'
            : 'text-slate-300 hover:bg-white/10 transition-colors';

          navHtml += `
            <li>
              <a class="flex items-center space-x-3 px-4 py-2 rounded-lg ${activeClass} text-sm" href="${item.href}">
                ${item.icon}
                <span>${item.label}</span>
              </a>
            </li>
          `;
        });

        navHtml += `
            </ul>
          </div>
        `;
      }
    });

    nav.innerHTML = navHtml;
    nav.className = 'flex-1 px-4 py-4 space-y-6';

    syncAdminUserProfile(aside);
  }

  function syncAdminUserProfile(aside) {
    try {
      const user = getStoredAdminUser();
      const nameEl = aside.querySelector('#sidebar-admin-name') || aside.querySelector('p.text-xs.font-bold');
      if (nameEl && !nameEl.id.includes('brand')) {
        nameEl.textContent = user.name;
      }
      const roleEl = aside.querySelector('p.text-\\[10px\\].text-slate-400') || aside.querySelector('#sidebar-admin-role');
      if (roleEl) {
        roleEl.textContent = user.role;
      }
      const avatarImg = aside.querySelector('img[alt*="Admin"], img[alt*="Avatar"]');
      if (avatarImg) {
        avatarImg.src = user.avatar;
      }
    } catch (e) {
      console.warn('Could not sync user profile in sidebar:', e);
    }
  }

  function renderSharedAdminHeader() {
    injectAdminStyles();

    // Check if sidebar collapse state was previously stored
    if (localStorage.getItem('admin_sidebar_collapsed') === 'true') {
      document.body.classList.add('sidebar-collapsed');
    }

    let header = document.querySelector('header.admin-top-header, header[data-purpose="admin-header"], header');
    if (!header) {
      const mainContainer = document.querySelector('main, .pl-64, body > div');
      header = document.createElement('header');
      if (mainContainer) {
        mainContainer.insertBefore(header, mainContainer.firstChild);
      } else {
        document.body.insertBefore(header, document.body.firstChild);
      }
    }

    header.className = 'admin-top-header bg-[#111827] text-white border-b border-slate-700/80 h-16 flex items-center justify-between px-6 sticky top-0 z-40 transition-all duration-300 shadow-md';
    header.setAttribute('data-purpose', 'admin-header');

    const user = getStoredAdminUser();

    header.innerHTML = `
      <!-- LEFT SECTION: Hamburger Toggle + Search Bar -->
      <div class="flex items-center space-x-4 flex-1 max-w-2xl">
        <!-- Hamburger / Sidebar Toggle -->
        <button id="admin-sidebar-toggle" class="border border-slate-700 hover:border-slate-500 bg-slate-800/80 hover:bg-slate-700 p-2 rounded-lg text-slate-300 hover:text-white transition-all cursor-pointer flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-blue-500/50 flex-shrink-0" title="Toggle Sidebar">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M4 6h16M4 12h16M4 18h16" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
        </button>

        <!-- Search Bar with CTRL + K -->
        <div class="relative flex-1 max-w-lg admin-search-container" id="admin-search-container">
          <div class="admin-header-search-wrap flex items-center rounded-lg px-3.5 py-1.5 w-full relative">
            <svg class="w-4 h-4 text-slate-400 flex-shrink-0 mr-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
            <input 
              id="admin-global-search-input" 
              class="w-full bg-transparent border-none outline-none text-sm text-slate-100 placeholder-slate-400 focus:ring-0" 
              placeholder="Search patients, beds, users..." 
              type="text"
              autocomplete="off"
              spellcheck="false"
            />
            <kbd class="admin-ctrl-k-badge text-[10px] font-semibold text-slate-400 px-1.5 py-0.5 rounded ml-2 flex-shrink-0 select-none shadow-sm">CTRL + K</kbd>
          </div>

          <!-- Live Search Results Dropdown -->
          <div id="admin-search-results-dropdown" class="admin-search-dropdown absolute left-0 right-0 top-full mt-2 rounded-xl border border-slate-700 p-3 shadow-2xl z-50 hidden max-h-[480px] overflow-y-auto">
            <div id="admin-search-results-content">
              <!-- Live query results will render here -->
            </div>
          </div>
        </div>
      </div>

      <!-- RIGHT SECTION: Notifications + Messages + Fullscreen + Profile -->
      <div class="flex items-center space-x-4 md:space-x-5 flex-shrink-0">
        
        <!-- Notifications Bell Button & Dropdown -->
        <div class="relative" id="admin-notifications-container">
          <button id="admin-notifications-btn" class="relative p-2 text-slate-300 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors cursor-pointer focus:outline-none" title="Notifications">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
            <span id="admin-notif-badge" class="absolute -top-1 -right-1 bg-red-600 text-white text-[10px] font-bold h-4 min-w-[16px] px-1 flex items-center justify-center rounded-full border border-[#111827] shadow-sm">3</span>
          </button>

          <!-- Notifications Dropdown -->
          <div id="admin-notifications-dropdown" class="admin-dropdown-menu absolute right-0 top-full mt-2 w-80 md:w-96 rounded-xl border border-slate-700 p-0 shadow-2xl z-50 hidden overflow-hidden">
            <div class="p-3.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
              <div class="flex items-center space-x-2">
                <span class="text-sm font-bold text-slate-100">Notifications</span>
                <span id="admin-notif-count-pill" class="text-[10px] bg-blue-500/20 text-blue-400 font-semibold px-2 py-0.5 rounded-full border border-blue-500/30">Live</span>
              </div>
              <button id="admin-mark-read-btn" class="text-xs text-blue-400 hover:text-blue-300 transition-colors font-medium cursor-pointer">Mark all as read</button>
            </div>
            <div id="admin-notifications-list" class="max-h-72 overflow-y-auto divide-y divide-slate-800/60">
              <!-- Notifications populated dynamically -->
            </div>
            <div class="p-2.5 bg-slate-900/90 border-t border-slate-800 text-center">
              <a href="../Admin_notification_settings/Admin_notification_settings.html" class="text-xs text-slate-400 hover:text-slate-200 transition-colors block py-1">View All Notification Settings &rarr;</a>
            </div>
          </div>
        </div>

        <!-- Messages / Alerts Button & Dropdown -->
        <div class="relative" id="admin-messages-container">
          <button id="admin-messages-btn" class="relative p-2 text-slate-300 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors cursor-pointer focus:outline-none" title="Messages & Clinical Alerts">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
            <span id="admin-msg-badge" class="absolute -top-1 -right-1 bg-red-600 text-white text-[10px] font-bold h-4 min-w-[16px] px-1 flex items-center justify-center rounded-full border border-[#111827] shadow-sm">2</span>
          </button>

          <!-- Messages Dropdown -->
          <div id="admin-messages-dropdown" class="admin-dropdown-menu absolute right-0 top-full mt-2 w-80 md:w-96 rounded-xl border border-slate-700 p-0 shadow-2xl z-50 hidden overflow-hidden">
            <div class="p-3.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
              <span class="text-sm font-bold text-slate-100">Clinical Messages &amp; System Alerts</span>
              <span class="text-[10px] bg-emerald-500/20 text-emerald-400 font-semibold px-2 py-0.5 rounded-full border border-emerald-500/30">Active</span>
            </div>
            <div id="admin-messages-list" class="max-h-72 overflow-y-auto divide-y divide-slate-800/60">
              <!-- Messages populated dynamically -->
            </div>
            <div class="p-2.5 bg-slate-900/90 border-t border-slate-800 text-center">
              <a href="../Admin_audit_logs/Admin_audit_logs.html" class="text-xs text-slate-400 hover:text-slate-200 transition-colors block py-1">View Full Audit &amp; Event Logs &rarr;</a>
            </div>
          </div>
        </div>

        <!-- Fullscreen Button -->
        <button id="admin-fullscreen-btn" class="p-2 text-slate-300 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors cursor-pointer focus:outline-none" title="Toggle Fullscreen">
          <svg id="admin-fullscreen-icon" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 4l-5-5M4 16v4m0 0h4m-4-4l5 5m11-1v4m0 0h-4m4-4l-5 5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
        </button>

        <!-- Admin Profile Section & Dropdown -->
        <div class="relative" id="admin-profile-container">
          <div id="admin-profile-trigger" class="flex items-center space-x-3 cursor-pointer p-1.5 rounded-lg hover:bg-slate-800/80 transition-colors select-none">
            <div class="text-right hidden sm:block">
              <p id="header-admin-name" class="text-xs font-semibold text-slate-100 leading-tight">${user.name}</p>
              <p id="header-admin-role" class="text-[10px] text-slate-400 leading-tight mt-0.5">${user.role}</p>
            </div>
            <div class="w-9 h-9 rounded-full overflow-hidden ring-2 ring-blue-500/40 bg-slate-700 flex-shrink-0">
              <img id="header-admin-avatar" alt="Avatar" class="w-full h-full object-cover" src="${user.avatar}"/>
            </div>
            <svg id="header-profile-chevron" class="w-4 h-4 text-slate-400 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M19 9l-7 7-7-7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
          </div>

          <!-- Profile Dropdown Menu -->
          <div id="admin-profile-dropdown" class="admin-dropdown-menu absolute right-0 top-full mt-2 w-64 rounded-xl border border-slate-700 p-2 shadow-2xl z-50 hidden">
            <!-- User Summary Header -->
            <div class="px-3 py-2.5 border-b border-slate-800 mb-1">
              <p class="text-xs font-bold text-slate-100" id="dropdown-user-name">${user.name}</p>
              <p class="text-[11px] text-slate-400 truncate" id="dropdown-user-email">${user.email}</p>
              <span class="inline-block mt-1.5 text-[10px] bg-blue-500/20 text-blue-300 font-semibold px-2 py-0.5 rounded-full border border-blue-500/30">${user.role}</span>
            </div>

            <!-- Menu Navigation Links -->
            <a href="../Admin_system_settings/Admin_system_settings.html" class="flex items-center space-x-2.5 px-3 py-2 text-xs text-slate-300 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
              <span>System Settings</span>
            </a>

            <a href="../Admin_notification_settings/Admin_notification_settings.html" class="flex items-center space-x-2.5 px-3 py-2 text-xs text-slate-300 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
              <span>Notification Preferences</span>
            </a>

            <a href="../Admin_audit_logs/Admin_audit_logs.html" class="flex items-center space-x-2.5 px-3 py-2 text-xs text-slate-300 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
              <span>Audit Trail Logs</span>
            </a>

            <div class="border-t border-slate-800 my-1"></div>

            <!-- Logout Button -->
            <button onclick="window.logoutAdmin()" class="w-full text-left flex items-center space-x-2.5 px-3 py-2 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg transition-colors cursor-pointer">
              <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
              <span>Sign Out</span>
            </button>
          </div>
        </div>

      </div>
    `;

    setupHeaderInteractions();
    fetchLiveNotifications();
    fetchLiveMessages();
  }

  function setupHeaderInteractions() {
    // 1. Sidebar Toggle (Hamburger Button)
    const sidebarToggle = document.getElementById('admin-sidebar-toggle');
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', () => {
        if (window.innerWidth <= 1024) {
          document.body.classList.toggle('sidebar-mobile-open');
        } else {
          document.body.classList.toggle('sidebar-collapsed');
          const isCollapsed = document.body.classList.contains('sidebar-collapsed');
          localStorage.setItem('admin_sidebar_collapsed', isCollapsed ? 'true' : 'false');
        }
      });
    }

    // 2. CTRL + K / CMD + K Shortcut Listener
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        const searchInput = document.getElementById('admin-global-search-input');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
          openSearchDropdown();
        }
      }
      if (e.key === 'Escape') {
        closeAllHeaderDropdowns();
      }
    });

    // 3. Global Search Input & Autocomplete
    const searchInput = document.getElementById('admin-global-search-input');
    const searchDropdown = document.getElementById('admin-search-results-dropdown');
    let searchDebounceTimer = null;

    if (searchInput) {
      searchInput.addEventListener('focus', () => {
        openSearchDropdown();
      });

      searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
          performGlobalSearch(query);
        }, 220);
      });

      // Keyboard navigation in search results
      searchInput.addEventListener('keydown', (e) => {
        const items = searchDropdown ? searchDropdown.querySelectorAll('.admin-search-item') : [];
        if (!items.length) return;

        let activeIdx = Array.from(items).findIndex(el => el.classList.contains('bg-slate-800'));

        if (e.key === 'ArrowDown') {
          e.preventDefault();
          if (activeIdx >= 0) items[activeIdx].classList.remove('bg-slate-800');
          activeIdx = (activeIdx + 1) % items.length;
          items[activeIdx].classList.add('bg-slate-800');
          items[activeIdx].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          if (activeIdx >= 0) items[activeIdx].classList.remove('bg-slate-800');
          activeIdx = (activeIdx - 1 + items.length) % items.length;
          items[activeIdx].classList.add('bg-slate-800');
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
    const notifBtn = document.getElementById('admin-notifications-btn');
    const notifDropdown = document.getElementById('admin-notifications-dropdown');
    if (notifBtn && notifDropdown) {
      notifBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = notifDropdown.classList.contains('hidden');
        closeAllHeaderDropdowns();
        if (isHidden) notifDropdown.classList.remove('hidden');
      });
    }

    const markReadBtn = document.getElementById('admin-mark-read-btn');
    if (markReadBtn) {
      markReadBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        markAllNotificationsRead();
      });
    }

    // 5. Messages Dropdown Toggle
    const msgBtn = document.getElementById('admin-messages-btn');
    const msgDropdown = document.getElementById('admin-messages-dropdown');
    if (msgBtn && msgDropdown) {
      msgBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = msgDropdown.classList.contains('hidden');
        closeAllHeaderDropdowns();
        if (isHidden) msgDropdown.classList.remove('hidden');
      });
    }

    // 6. Fullscreen Button Toggle
    const fullscreenBtn = document.getElementById('admin-fullscreen-btn');
    if (fullscreenBtn) {
      fullscreenBtn.addEventListener('click', () => {
        toggleBrowserFullscreen();
      });
    }

    document.addEventListener('fullscreenchange', () => {
      updateFullscreenIcon();
    });

    // 7. Profile Dropdown Toggle
    const profileTrigger = document.getElementById('admin-profile-trigger');
    const profileDropdown = document.getElementById('admin-profile-dropdown');
    const profileChevron = document.getElementById('header-profile-chevron');
    if (profileTrigger && profileDropdown) {
      profileTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = profileDropdown.classList.contains('hidden');
        closeAllHeaderDropdowns();
        if (isHidden) {
          profileDropdown.classList.remove('hidden');
          if (profileChevron) profileChevron.classList.add('rotate-180');
        }
      });
    }

    // Global Click outside to close dropdowns
    document.addEventListener('click', (e) => {
      const searchContainer = document.getElementById('admin-search-container');
      const notifContainer = document.getElementById('admin-notifications-container');
      const msgContainer = document.getElementById('admin-messages-container');
      const profileContainer = document.getElementById('admin-profile-container');

      if (!searchContainer?.contains(e.target) &&
          !notifContainer?.contains(e.target) &&
          !msgContainer?.contains(e.target) &&
          !profileContainer?.contains(e.target)) {
        closeAllHeaderDropdowns();
      }
    });
  }

  function closeAllHeaderDropdowns() {
    const searchDropdown = document.getElementById('admin-search-results-dropdown');
    const notifDropdown = document.getElementById('admin-notifications-dropdown');
    const msgDropdown = document.getElementById('admin-messages-dropdown');
    const profileDropdown = document.getElementById('admin-profile-dropdown');
    const profileChevron = document.getElementById('header-profile-chevron');

    if (searchDropdown) searchDropdown.classList.add('hidden');
    if (notifDropdown) notifDropdown.classList.add('hidden');
    if (msgDropdown) msgDropdown.classList.add('hidden');
    if (profileDropdown) profileDropdown.classList.add('hidden');
    if (profileChevron) profileChevron.classList.remove('rotate-180');
  }

  function openSearchDropdown() {
    const searchDropdown = document.getElementById('admin-search-results-dropdown');
    const searchInput = document.getElementById('admin-global-search-input');
    if (!searchDropdown) return;

    searchDropdown.classList.remove('hidden');
    const query = searchInput ? searchInput.value.trim() : '';
    if (!query) {
      renderSearchSuggestions();
    } else {
      performGlobalSearch(query);
    }
  }

  function renderSearchSuggestions() {
    const content = document.getElementById('admin-search-results-content');
    if (!content) return;

    content.innerHTML = `
      <div class="py-2 px-1">
        <p class="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2 px-2">Quick Navigation</p>
        <div class="grid grid-cols-2 gap-2">
          <a href="../Admin_patient_management/Admin_patient_management.html" class="admin-search-item flex items-center space-x-2.5 p-2 rounded-lg bg-slate-800/60 hover:bg-slate-800 text-xs text-slate-200 transition-colors">
            <span class="w-6 h-6 rounded-md bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-xs">P</span>
            <span>Patient Roster</span>
          </a>
          <a href="../Admin_beds_wards/Admin_beds_wards.html" class="admin-search-item flex items-center space-x-2.5 p-2 rounded-lg bg-slate-800/60 hover:bg-slate-800 text-xs text-slate-200 transition-colors">
            <span class="w-6 h-6 rounded-md bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs">B</span>
            <span>Beds &amp; Wards</span>
          </a>
          <a href="../Admin_clinical_reports/Admin_clinical_reports.html" class="admin-search-item flex items-center space-x-2.5 p-2 rounded-lg bg-slate-800/60 hover:bg-slate-800 text-xs text-slate-200 transition-colors">
            <span class="w-6 h-6 rounded-md bg-purple-500/20 text-purple-400 flex items-center justify-center font-bold text-xs">R</span>
            <span>Clinical Reports</span>
          </a>
          <a href="../Admin_users_roles/Admin_users_roles.html" class="admin-search-item flex items-center space-x-2.5 p-2 rounded-lg bg-slate-800/60 hover:bg-slate-800 text-xs text-slate-200 transition-colors">
            <span class="w-6 h-6 rounded-md bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-xs">U</span>
            <span>Users &amp; Roles</span>
          </a>
        </div>
      </div>
      <div class="pt-2 border-t border-slate-800 mt-2 flex items-center justify-between text-[11px] text-slate-500 px-2">
        <span>Type to search patients, beds, or staff</span>
        <span>Esc to close</span>
      </div>
    `;
  }

  async function performGlobalSearch(query) {
    const content = document.getElementById('admin-search-results-content');
    if (!content) return;

    if (!query) {
      renderSearchSuggestions();
      return;
    }

    content.innerHTML = `
      <div class="py-6 text-center text-slate-400">
        <svg class="w-5 h-5 animate-spin mx-auto mb-2 text-blue-500" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span class="text-xs">Searching database records...</span>
      </div>
    `;

    try {
      const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const res = await fetch(`/api/v1/users/global-search?q=${encodeURIComponent(query)}`, { headers });
      const data = await res.json();

      if (!data.success || data.total === 0) {
        content.innerHTML = `
          <div class="py-6 text-center text-slate-400">
            <svg class="w-8 h-8 mx-auto mb-2 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-width="1.5"></path>
            </svg>
            <p class="text-xs font-medium text-slate-300">No matching records found</p>
            <p class="text-[11px] text-slate-500 mt-0.5">No patients, beds, or staff match "${escapeHtml(query)}"</p>
          </div>
        `;
        return;
      }

      let html = '<div class="space-y-3 py-1">';

      // 1. Patients Results
      if (data.results.patients && data.results.patients.length > 0) {
        html += `
          <div>
            <div class="flex items-center justify-between px-2 mb-1.5">
              <span class="text-[11px] font-bold text-blue-400 uppercase tracking-wider">Patients (${data.results.patients.length})</span>
            </div>
            <div class="space-y-1">
        `;
        data.results.patients.forEach(p => {
          html += `
            <a href="../Admin_patient_management/Admin_patient_management.html?search=${encodeURIComponent(p.name)}" class="admin-search-item block p-2.5 rounded-lg hover:bg-slate-800 transition-colors">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-2.5 min-w-0">
                  <div class="w-7 h-7 rounded bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-xs flex-shrink-0">
                    ${escapeHtml(p.name.substring(0, 1))}
                  </div>
                  <div class="truncate">
                    <p class="text-xs font-semibold text-slate-100">${escapeHtml(p.name)} <span class="text-[10px] text-slate-400 font-mono font-normal">(${escapeHtml(p.patient_code)})</span></p>
                    <p class="text-[11px] text-slate-400 truncate">${escapeHtml(p.diagnosis)}</p>
                  </div>
                </div>
                <div class="text-right flex-shrink-0 ml-2">
                  <span class="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700">${escapeHtml(p.ward)} · ${escapeHtml(p.bed)}</span>
                </div>
              </div>
            </a>
          `;
        });
        html += `</div></div>`;
      }

      // 2. Beds & Wards Results
      if (data.results.beds && data.results.beds.length > 0) {
        html += `
          <div>
            <div class="flex items-center justify-between px-2 mb-1.5">
              <span class="text-[11px] font-bold text-emerald-400 uppercase tracking-wider">Beds &amp; Wards (${data.results.beds.length})</span>
            </div>
            <div class="grid grid-cols-2 gap-1.5">
        `;
        data.results.beds.forEach(b => {
          const isOcc = b.status === 'occupied';
          const statusBadge = isOcc
            ? '<span class="text-[10px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded border border-red-500/20">Occupied</span>'
            : '<span class="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">Available</span>';

          html += `
            <a href="../Admin_beds_wards/Admin_beds_wards.html?bed=${encodeURIComponent(b.bed_number)}" class="admin-search-item flex items-center justify-between p-2 rounded-lg bg-slate-800/40 hover:bg-slate-800 transition-colors">
              <div>
                <p class="text-xs font-semibold text-slate-100">${escapeHtml(b.bed_number)}</p>
                <p class="text-[10px] text-slate-400">${escapeHtml(b.ward_name || 'Ward')}</p>
              </div>
              <div>${statusBadge}</div>
            </a>
          `;
        });
        html += `</div></div>`;
      }

      // 3. Users & Staff Results
      if (data.results.users && data.results.users.length > 0) {
        html += `
          <div>
            <div class="flex items-center justify-between px-2 mb-1.5">
              <span class="text-[11px] font-bold text-purple-400 uppercase tracking-wider">Staff &amp; Users (${data.results.users.length})</span>
            </div>
            <div class="space-y-1">
        `;
        data.results.users.forEach(u => {
          html += `
            <a href="../Admin_users_roles/Admin_users_roles.html?search=${encodeURIComponent(u.username)}" class="admin-search-item block p-2 rounded-lg hover:bg-slate-800 transition-colors">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-2 min-w-0">
                  <div class="w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center font-bold text-[10px] flex-shrink-0">
                    ${escapeHtml(u.name.substring(0, 1))}
                  </div>
                  <div class="truncate">
                    <p class="text-xs font-medium text-slate-200">${escapeHtml(u.name)} <span class="text-[10px] text-slate-400">(@${escapeHtml(u.username)})</span></p>
                  </div>
                </div>
                <div class="flex-shrink-0">
                  <span class="text-[10px] bg-slate-800 text-purple-300 font-medium px-2 py-0.5 rounded capitalize border border-slate-700">${escapeHtml(u.role)}</span>
                </div>
              </div>
            </a>
          `;
        });
        html += `</div></div>`;
      }

      html += `
        </div>
        <div class="pt-2 border-t border-slate-800 mt-2 flex items-center justify-between text-[10px] text-slate-500 px-2">
          <span>${data.total} result(s) found</span>
          <span>&uarr;&darr; to navigate &middot; &crarr; to open &middot; Esc to close</span>
        </div>
      `;

      content.innerHTML = html;
    } catch (e) {
      console.error('Error during global search:', e);
      content.innerHTML = `
        <div class="py-4 text-center text-xs text-red-400">
          Failed to load search results. Please try again.
        </div>
      `;
    }
  }

  async function fetchLiveNotifications() {
    try {
      const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const res = await fetch('/api/v1/notifications?limit=6', { headers });
      const data = await res.json();

      const badge = document.getElementById('admin-notif-badge');
      const countPill = document.getElementById('admin-notif-count-pill');
      const list = document.getElementById('admin-notifications-list');

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
          <div class="py-8 px-4 text-center text-slate-400">
            <svg class="w-8 h-8 mx-auto mb-2 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" stroke-width="1.5"></path>
            </svg>
            <p class="text-xs font-semibold text-slate-300">No Notifications</p>
            <p class="text-[11px] text-slate-500 mt-0.5">All patient monitoring events are clear.</p>
          </div>
        `;
        return;
      }

      let html = '';
      notifs.forEach(n => {
        const isUnread = !n.is_read;
        const dot = isUnread ? '<span class="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0 mt-1"></span>' : '';
        const timeAgo = formatTimeAgo(n.created_at);

        html += `
          <div class="p-3 hover:bg-slate-800/70 transition-colors cursor-pointer flex items-start space-x-2.5 ${isUnread ? 'bg-slate-800/30' : ''}">
            ${dot}
            <div class="flex-1 min-w-0">
              <p class="text-xs font-semibold text-slate-100 leading-tight">${escapeHtml(n.title || n.subject || 'System Notification')}</p>
              <p class="text-[11px] text-slate-400 mt-0.5 leading-snug">${escapeHtml(n.message || n.body || '')}</p>
              <span class="text-[10px] text-slate-500 mt-1 block">${timeAgo}</span>
            </div>
          </div>
        `;
      });
      list.innerHTML = html;
    } catch (e) {
      console.warn('Could not fetch notifications:', e);
    }
  }

  async function markAllNotificationsRead() {
    try {
      const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      await fetch('/api/v1/notifications/read-all', { method: 'POST', headers });
      fetchLiveNotifications();
    } catch (e) {
      console.warn('Could not mark all notifications as read:', e);
    }
  }

  async function fetchLiveMessages() {
    try {
      const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const res = await fetch('/alert/api/active', { headers });
      const data = await res.json();

      const badge = document.getElementById('admin-msg-badge');
      const list = document.getElementById('admin-messages-list');
      if (!list) return;

      const alerts = data.data || [];
      if (badge) {
        if (alerts.length > 0) {
          badge.textContent = alerts.length > 99 ? '99+' : alerts.length;
          badge.style.display = 'flex';
        } else {
          badge.style.display = 'none';
        }
      }

      if (!alerts.length) {
        list.innerHTML = `
          <div class="py-8 px-4 text-center text-slate-400">
            <svg class="w-8 h-8 mx-auto mb-2 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" stroke-width="1.5"></path>
            </svg>
            <p class="text-xs font-semibold text-slate-300">No Unread Messages</p>
            <p class="text-[11px] text-slate-500 mt-0.5">Clinical communication channels are operating normally.</p>
          </div>
        `;
        return;
      }

      let html = '';
      alerts.slice(0, 5).forEach(a => {
        const severityClass = a.severity === 'critical' ? 'text-red-400 bg-red-500/10 border-red-500/30' : 'text-amber-400 bg-amber-500/10 border-amber-500/30';
        html += `
          <div class="p-3 hover:bg-slate-800/70 transition-colors flex items-start space-x-2.5">
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between">
                <p class="text-xs font-semibold text-slate-100">${escapeHtml(a.patient_name || a.alert_type || 'Clinical Alert')}</p>
                <span class="text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase ${severityClass}">${escapeHtml(a.severity || 'ALERT')}</span>
              </div>
              <p class="text-[11px] text-slate-400 mt-0.5">${escapeHtml(a.message || 'Immediate clinical attention required')}</p>
              <span class="text-[10px] text-slate-500 mt-1 block">${formatTimeAgo(a.created_at)}</span>
            </div>
          </div>
        `;
      });
      list.innerHTML = html;
    } catch (e) {
      console.warn('Could not fetch active alerts/messages:', e);
    }
  }

  function toggleBrowserFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(err => {
        console.warn('Fullscreen error:', err);
      });
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  }

  function updateFullscreenIcon() {
    const icon = document.getElementById('admin-fullscreen-icon');
    if (!icon) return;

    if (document.fullscreenElement) {
      // Exit fullscreen icon (compress corners)
      icon.innerHTML = `<path d="M4 14h6m0 0v6m0-6l-7 7m17-11h-6m0 0V4m0 6l7-7m-7 17v-6m0 0h6m-6 0l7 7M10 4v6m0 0H4m6 0L3 3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>`;
    } else {
      // Enter fullscreen icon (expand corners)
      icon.innerHTML = `<path d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 4l-5-5M4 16v4m0 0h4m-4-4l5 5m11-1v4m0 0h-4m4-4l-5 5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>`;
    }
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

  // Global Logout helper
  window.logoutAdmin = function () {
    localStorage.removeItem('jeevan_setu_token');
    localStorage.removeItem('jeevan_setu_user');
    sessionStorage.clear();
    window.location.href = '../../Login/Login.html';
  };

  // Run on DOMContentLoaded or immediately
  function initAdminPortal() {
    renderSidebarNav();
    renderSharedAdminHeader();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAdminPortal);
  } else {
    initAdminPortal();
  }
})();
