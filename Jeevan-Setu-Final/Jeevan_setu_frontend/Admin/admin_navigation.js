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
      icon: 'dashboard'
    },
    {
      type: 'group',
      category: 'ADMINISTRATOR',
      items: [
        {
          id: 'patients',
          label: 'Patients',
          href: '../Admin_patient_management/Admin_patient_management.html',
          match: ['admin_patient_management', 'patient_management', 'patient'],
          icon: 'groups'
        },
        {
          id: 'beds_wards',
          label: 'Beds & Wards',
          href: '../Admin_beds_wards/Admin_beds_wards.html',
          match: ['admin_beds_wards', 'beds_wards', 'bed', 'ward', 'resource_utilization', 'admin_resource_utilization'],
          icon: 'hotel'
        },
        {
          id: 'users_roles',
          label: 'Users & Roles',
          href: '../Admin_users_roles/Admin_users_roles.html',
          match: ['admin_users_roles', 'users_roles', 'users'],
          icon: 'manage_accounts'
        },
        {
          id: 'attendants_qr',
          label: 'Attendants (QR Access)',
          href: '../Admin_attendant_access/Admin_attendant_access.html',
          match: ['admin_attendant_access', 'attendant_access', 'attendant'],
          icon: 'qr_code_scanner'
        }
      ]
    },
    {
      type: 'group',
      category: 'MONITORING & ANALYTICS',
      items: [
        {
          id: 'ews_analytics',
          label: 'EWS Analytics',
          href: '../Admin_ews_analytics/Admin_ews_analytics.html',
          match: ['admin_ews_analytics', 'ews_analytics'],
          icon: 'analytics'
        },
        {
          id: 'reports',
          label: 'Reports',
          href: '../Admin_clinical_reports/Admin_clinical_reports.html',
          match: ['admin_clinical_reports', 'clinical_reports', 'reports'],
          icon: 'description'
        },
        {
          id: 'audit_logs',
          label: 'Audit Logs',
          href: '../Admin_audit_logs/Admin_audit_logs.html',
          match: ['admin_audit_logs', 'audit_logs', 'audit'],
          icon: 'verified_user'
        }
      ]
    },
    {
      type: 'group',
      category: 'SYSTEM SETTINGS',
      items: [
        {
          id: 'system_settings',
          label: 'System Settings',
          href: '../Admin_system_settings/Admin_system_settings.html',
          match: ['admin_system_settings', 'system_settings'],
          icon: 'settings'
        },
        {
          id: 'notification_settings',
          label: 'Notifications',
          href: '../Admin_notification_settings/Admin_notification_settings.html',
          match: ['admin_notification_settings', 'notification_settings', 'notifications'],
          icon: 'notifications'
        },
        {
          id: 'backup_restore',
          label: 'Backup & Restore',
          href: '../Admin_backup_restore/Admin_backup_restore.html',
          match: ['admin_backup_restore', 'backup_restore', 'backup'],
          icon: 'backup'
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
        const role = String(parsed.role || '').toLowerCase();
        // Strict guard: In the Admin Portal, NEVER display non-admin (doctor/nurse/attendant) credentials
        if (role === 'admin' || role === 'administrator' || role === 'superadmin' || role === 'system_admin') {
          return {
            id: parsed.id || parsed.user_id || 1,
            name: parsed.full_name || parsed.username || 'System Administrator',
            username: parsed.username || 'admin_js',
            role: 'Administrator',
            email: parsed.email || 'admin@jeevansetu.in',
            avatar: parsed.avatar_url || DEFAULT_ADMIN_AVATAR
          };
        }
      }
    } catch (e) {
      console.warn('Could not parse stored admin user:', e);
    }
    return {
      id: 1,
      name: 'System Administrator',
      username: 'admin_js',
      role: 'Administrator',
      email: 'admin@jeevansetu.in',
      avatar: DEFAULT_ADMIN_AVATAR
    };
  }

  function ensureUnifiedResponsiveCSS() {
    if (document.getElementById('jeevan-responsive-unified-styles')) return;
    const link = document.createElement('link');
    link.id = 'jeevan-responsive-unified-styles';
    link.rel = 'stylesheet';
    link.href = '/static/css/responsive_unified.css';
    document.head.appendChild(link);
  }

  function injectAdminStyles() {
    ensureUnifiedResponsiveCSS();
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
        html {
          max-width: 100vw;
          overflow-x: hidden;
          overflow-y: auto;
        }
        body {
          max-width: 100vw;
          overflow-x: visible;
          overflow-y: visible;
          overscroll-behavior: auto;
          overscroll-behavior-y: auto;
        }
        aside[data-purpose="sidebar"],
        aside.w-64,
        aside {
          transform: translateX(-100%) !important;
          position: fixed !important;
          left: 0 !important;
          top: 0 !important;
          bottom: 0 !important;
          height: 100dvh !important;
          z-index: 60 !important;
          width: 16rem !important;
          max-width: 85vw !important;
        }
        body.sidebar-mobile-open aside[data-purpose="sidebar"],
        body.sidebar-mobile-open aside.w-64,
        body.sidebar-mobile-open aside {
          transform: translateX(0) !important;
          width: 16rem !important;
          min-width: 16rem !important;
          max-width: 85vw !important;
          opacity: 1 !important;
          pointer-events: auto !important;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8) !important;
        }
        .pl-64, .md\:pl-64, .lg\:pl-64 {
          padding-left: 0 !important;
        }
        .left-64, header.left-64, header.fixed {
          left: 0 !important;
        }
        .admin-top-header {
          padding-left: 0.75rem !important;
          padding-right: 0.75rem !important;
        }
      }
      @media (max-width: 768px) {
        #admin-search-container,
        .admin-search-container {
          max-width: 12rem !important;
          margin-left: 0.25rem !important;
          margin-right: 0.25rem !important;
        }
        #header-admin-role {
          display: none !important;
        }
        #header-admin-name {
          font-size: 0.75rem !important;
          max-width: 6.5rem !important;
          white-space: nowrap !important;
          overflow: hidden !important;
          text-overflow: ellipsis !important;
        }
        /* Mobile Table Card Transformation */
        table.mobile-cards thead,
        #admin-users-table thead,
        .admin-staff-table thead {
          display: none !important;
        }
        table.mobile-cards tbody tr,
        #admin-users-table tbody tr,
        .admin-staff-table tbody tr {
          display: block !important;
          background: #1e293b !important;
          border: 1px solid #334155 !important;
          border-radius: 0.875rem !important;
          margin-bottom: 0.875rem !important;
          padding: 0.875rem 1rem !important;
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important;
          position: relative !important;
        }
        table.mobile-cards tbody td,
        #admin-users-table tbody td,
        .admin-staff-table tbody td {
          display: flex !important;
          align-items: center !important;
          justify-content: space-between !important;
          padding: 0.35rem 0 !important;
          border-bottom: 1px solid rgba(51, 65, 85, 0.4) !important;
          font-size: 0.8125rem !important;
        }
        table.mobile-cards tbody td:first-child,
        #admin-users-table tbody td:first-child,
        .admin-staff-table tbody td:first-child {
          border-bottom: 1px solid #334155 !important;
          padding-bottom: 0.5rem !important;
          margin-bottom: 0.35rem !important;
          padding-right: 2.5rem !important;
        }
        table.mobile-cards tbody td:last-child,
        #admin-users-table tbody td:last-child,
        .admin-staff-table tbody td:last-child {
          border-bottom: none !important;
          position: absolute !important;
          top: 0.75rem !important;
          right: 0.75rem !important;
          padding: 0 !important;
        }
        table.mobile-cards tbody td[data-col]::before,
        #admin-users-table tbody td[data-col]::before,
        .admin-staff-table tbody td[data-col]::before {
          content: attr(data-col);
          font-weight: 600;
          color: #94a3b8;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.03em;
        }
      }
      @media (max-width: 640px) {
        #admin-notifications-dropdown,
        #admin-messages-dropdown,
        #admin-profile-dropdown,
        #admin-search-results-dropdown {
          position: fixed !important;
          left: 12px !important;
          right: 12px !important;
          top: 68px !important;
          width: calc(100vw - 24px) !important;
          max-width: calc(100vw - 24px) !important;
        }
        .admin-ctrl-k-badge {
          display: none !important;
        }
        #admin-fullscreen-btn {
          display: none !important;
        }
        .grid-cols-12 > .col-span-8,
        .grid-cols-12 > .col-span-4,
        .grid-cols-12 > .col-span-7,
        .grid-cols-12 > .col-span-5,
        .grid-cols-12 > .col-span-6 {
          grid-column: span 12 / span 12 !important;
        }
        .grid-cols-5:not(.sm\:grid-cols-5):not(.md\:grid-cols-5):not(.lg\:grid-cols-5),
        .grid-cols-4:not(.sm\:grid-cols-4):not(.md\:grid-cols-4):not(.lg\:grid-cols-4) {
          grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        }
        .grid-cols-3:not(.sm\:grid-cols-3):not(.md\:grid-cols-3):not(.lg\:grid-cols-3) {
          grid-template-columns: repeat(1, minmax(0, 1fr)) !important;
        }
      }
      @media (max-width: 480px) {
        #admin-search-container,
        .admin-search-container {
          max-width: 7.5rem !important;
        }
        .js-sync-indicator span[data-sync-text] {
          display: none !important;
        }
        .js-sync-indicator {
          padding: 0.35rem !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function ensureAdminFonts() {
    if (!document.querySelector('link[href*="Material+Symbols+Outlined"]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200';
      document.head.appendChild(link);
    }
    if (!document.querySelector('link[href*="family=Poppins"]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap';
      document.head.appendChild(link);
    }
  }

  function renderSidebarNav() {
    ensureAdminFonts();
    let aside = document.querySelector('aside[data-purpose="sidebar"], aside.w-64, aside');
    if (!aside) {
      aside = document.createElement('aside');
      aside.setAttribute('data-purpose', 'sidebar');
      document.body.insertBefore(aside, document.body.firstChild);
    }

    aside.setAttribute('data-purpose', 'sidebar');
    const parentEl = aside.parentElement;
    const isFlexParent = parentEl && (parentEl.classList.contains('flex') || window.getComputedStyle(parentEl).display === 'flex');
    const desktopPosClass = isFlexParent ? 'lg:static' : 'lg:fixed';
    aside.className = `w-64 bg-[#0a1931] text-white flex-shrink-0 flex flex-col h-screen overflow-y-auto select-none border-r border-slate-800 fixed left-0 top-0 z-50 ${desktopPosClass} sidebar-transition`;

    const currentActiveId = detectCurrentPage();
    const user = getStoredAdminUser();

    // 1. Branding Header (Master Doctor Style)
    const brandingHeaderHtml = `
      <div class="sidebar-brand-header p-5 border-b border-white/10 flex items-center justify-between flex-shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 overflow-hidden">
            <img src="/assets/jeevan_setu_logo.png" onerror="this.onerror=null; this.src='../../assets/jeevan_setu_logo.png';" alt="Jeevan Setu Logo" class="w-full h-full object-contain">
          </div>
          <div>
            <h1 class="sidebar-brand-title font-bold text-base tracking-tight leading-tight text-white font-['Poppins']">JEEVAN SETU</h1>
            <p class="sidebar-brand-subtitle text-[9px] text-cyan-400 font-semibold tracking-wider uppercase font-['Inter']">INTELLIGENT TRANSFER SYSTEM</p>
          </div>
        </div>
        <button id="admin-sidebar-close-btn" type="button" class="lg:hidden text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors cursor-pointer ml-auto" aria-label="Close sidebar">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
        </button>
      </div>
    `;

    // 2. Navigation Sections (Master Doctor Active/Inactive Navigation Item Style)
    let navSectionsHtml = '';
    ADMIN_NAV_CONFIG.forEach(sec => {
      if (sec.type === 'single') {
        const isActive = sec.id === currentActiveId;
        const activeClass = isActive
          ? 'bg-white/10 text-cyan-400 font-semibold border-l-4 border-cyan-400'
          : 'text-slate-300 hover:bg-white/5 hover:text-white';
        const iconClass = isActive ? 'text-cyan-400' : 'text-slate-400 group-hover:text-cyan-400';

        navSectionsHtml += `
          <div>
            <ul class="space-y-1">
              <li>
                <a href="${sec.href}" data-page="${sec.id}" class="sidebar-nav-item flex items-center px-3 py-2.5 rounded-lg ${activeClass} transition-all group text-sm">
                  <span class="material-symbols-outlined mr-3 text-[20px] ${iconClass} transition-colors flex-shrink-0">${sec.icon}</span>
                  <span>${sec.label}</span>
                </a>
              </li>
            </ul>
          </div>
        `;
      } else if (sec.type === 'group') {
        navSectionsHtml += `
          <div>
            <p class="sidebar-section-heading px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 font-['Inter']">${sec.category}</p>
            <ul class="space-y-1">
        `;

        sec.items.forEach(item => {
          const isActive = item.id === currentActiveId;
          const activeClass = isActive
            ? 'bg-white/10 text-cyan-400 font-semibold border-l-4 border-cyan-400'
            : 'text-slate-300 hover:bg-white/5 hover:text-white';
          const iconClass = isActive ? 'text-cyan-400' : 'text-slate-400 group-hover:text-cyan-400';

          navSectionsHtml += `
            <li>
              <a href="${item.href}" data-page="${item.id}" class="sidebar-nav-item flex items-center px-3 py-2.5 rounded-lg ${activeClass} transition-all group text-sm font-medium">
                <span class="material-symbols-outlined mr-3 text-[20px] ${iconClass} transition-colors flex-shrink-0">${item.icon}</span>
                <span>${item.label}</span>
              </a>
            </li>
          `;
        });

        navSectionsHtml += `
            </ul>
          </div>
        `;
      }
    });

    // 3. Footer / Bottom Section (Administrator profile + Red Logout button)
    const bottomNavHtml = `
      <div class="sidebar-footer-container p-3 border-t border-white/10 space-y-2 mt-auto bg-[#081426]/50 flex-shrink-0">
        <div class="sidebar-admin-profile-card bg-white/5 border border-white/5 rounded-xl p-2.5 flex items-center justify-between">
          <div class="flex items-center space-x-2.5 overflow-hidden">
            <div class="w-9 h-9 rounded-full overflow-hidden flex-shrink-0 ring-1 ring-cyan-400/40">
              <img id="sidebar-admin-avatar" alt="System Administrator" class="w-full h-full object-cover" src="${user.avatar}" onerror="this.onerror=null; this.src='../admin_avatar.jpg';">
            </div>
            <div class="truncate">
              <p id="sidebar-admin-name" class="text-xs font-bold text-white truncate">${user.name}</p>
              <p id="sidebar-admin-role" class="text-[10px] text-slate-400 truncate">${user.role}</p>
            </div>
          </div>
          <div class="flex flex-col items-center flex-shrink-0 pl-1">
            <span class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse mb-0.5"></span>
            <span class="text-[8px] font-semibold text-emerald-400 tracking-wider uppercase">ONLINE</span>
          </div>
        </div>
        <a href="../../Login/Login.html" onclick="if(typeof handleAdminLogout==='function'){handleAdminLogout(event);}else if(typeof window.logoutAdmin==='function'){window.logoutAdmin(event);}" class="sidebar-nav-item sidebar-logout-link flex items-center px-3 py-2.5 rounded-lg text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-all group text-sm font-medium cursor-pointer">
          <span class="material-symbols-outlined mr-3 text-[20px] text-red-400 group-hover:text-red-300 transition-colors">logout</span>
          <span>Logout</span>
        </a>
      </div>
    `;

    aside.innerHTML = `
      ${brandingHeaderHtml}
      <nav class="flex-1 px-3 py-4 space-y-6 overflow-y-auto">
        ${navSectionsHtml}
      </nav>
      ${bottomNavHtml}
    `;

    // Ensure mobile backdrop exists
    let backdrop = document.getElementById('admin-sidebar-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'admin-sidebar-backdrop';
      backdrop.className = 'fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 lg:hidden hidden transition-opacity';
      backdrop.addEventListener('click', () => {
        document.body.classList.remove('sidebar-mobile-open');
        backdrop.classList.add('hidden');
      });
      document.body.appendChild(backdrop);
    }

    const closeBtn = document.getElementById('admin-sidebar-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        document.body.classList.remove('sidebar-mobile-open');
        if (backdrop) backdrop.classList.add('hidden');
      });
    }

    // Close mobile drawer when any navigation link is clicked
    aside.querySelectorAll('nav a, a').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 1024) {
          document.body.classList.remove('sidebar-mobile-open');
          if (backdrop) backdrop.classList.add('hidden');
        }
      });
    });

    // Wrap any unwrapped tables in overflow-x-auto
    document.querySelectorAll('table').forEach(tbl => {
      const parent = tbl.parentElement;
      if (parent && !parent.classList.contains('overflow-x-auto') && !parent.classList.contains('overflow-auto')) {
        parent.classList.add('overflow-x-auto');
      }
    });

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

    header.className = 'admin-top-header portal-header bg-[#111827] text-white border-b border-slate-700/80 h-16 flex items-center justify-between px-6 sticky top-0 z-40 transition-all duration-300 shadow-md';
    header.setAttribute('data-purpose', 'admin-header');

    const user = getStoredAdminUser();
    const initials = (user.name || 'Admin').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() || 'AD';

    header.innerHTML = `
      <!-- ROW 1: [☰ Menu] [Brand / Page Title] [Mobile Profile Avatar] -->
      <div class="admin-header-row-1 flex items-center justify-between w-full">
        <!-- Left: Hamburger Toggle + Brand / Logo -->
        <div class="flex items-center gap-2.5 sm:gap-3 flex-shrink-0">
          <button id="admin-sidebar-toggle" class="border border-slate-700 hover:border-slate-500 bg-slate-800/80 hover:bg-slate-700 p-2 rounded-lg text-slate-300 hover:text-white transition-all cursor-pointer flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-blue-500/50 flex-shrink-0" title="Toggle Sidebar">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M4 6h16M4 12h16M4 18h16" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
          </button>

          <div class="flex items-center gap-2 sm:gap-2.5">
            <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm flex-shrink-0">
              <svg class="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <div>
              <h1 class="font-bold text-white text-sm sm:text-base leading-tight tracking-tight">JEEVAN SETU <span class="text-xs text-blue-400 font-normal hidden sm:inline">• Admin</span></h1>
            </div>
          </div>
        </div>

        <!-- Right (Mobile Only): Profile Avatar with Online indicator -->
        <div class="admin-header-mobile-profile">
          <div class="relative cursor-pointer p-0.5" id="admin-mobile-avatar-trigger" title="${user.name} (${user.role})">
            <div class="w-8 h-8 rounded-full bg-blue-600 ring-2 ring-blue-500/50 flex items-center justify-center text-white font-bold text-xs shadow-sm">${initials}</div>
            <span class="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-[#111827]"></span>
          </div>
        </div>
      </div>

      <!-- ROW 2: [Search Bar] [Sync Indicator] [Notifications] [Messages] [Fullscreen] [Desktop Profile] -->
      <div class="admin-header-row-2 flex items-center justify-between w-full">
        <!-- Left: Search Bar with CTRL + K -->
        <div class="relative flex-1 max-w-[130px] sm:max-w-xs md:max-w-md mr-2 admin-search-container" id="admin-search-container">
          <div class="admin-header-search-wrap flex items-center rounded-lg px-2.5 sm:px-3.5 py-1.5 w-full relative">
            <svg class="w-4 h-4 text-slate-400 flex-shrink-0 mr-1.5 sm:mr-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
            <input 
              id="admin-global-search-input" 
              class="w-full bg-transparent border-none outline-none text-xs sm:text-sm text-slate-100 placeholder-slate-400 focus:ring-0 p-0" 
              placeholder="Search..." 
              type="text"
              autocomplete="off"
              spellcheck="false"
            />
            <kbd class="admin-ctrl-k-badge hidden sm:inline-block text-[10px] font-semibold text-slate-400 px-1.5 py-0.5 rounded ml-2 flex-shrink-0 select-none shadow-sm">CTRL + K</kbd>
          </div>

          <!-- Live Search Results Dropdown -->
          <div id="admin-search-results-dropdown" class="admin-search-dropdown absolute left-0 right-0 top-full mt-2 rounded-xl border border-slate-700 p-3 shadow-2xl z-50 hidden max-h-[480px] overflow-y-auto">
            <div id="admin-search-results-content">
              <!-- Live query results will render here -->
            </div>
          </div>
        </div>

        <!-- Right: Indicators + Notifications + Messages + Desktop Profile -->
        <div class="flex items-center gap-1.5 sm:gap-3 md:gap-4 flex-shrink-0">
          
          <!-- Live Data Freshness & Sync Indicator -->
          <div id="admin-sync-indicator-wrap" class="flex items-center">
            <div id="admin-sync-indicator" class="js-sync-indicator inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 cursor-pointer select-none transition-all shadow-xs hover:bg-emerald-500/20" title="Data automatically refreshing every 5s • Click to sync now">
              <span data-sync-dot class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span data-sync-text id="admin-sync-text">Live</span>
            </div>
          </div>
          
          <!-- Notifications Bell Button & Dropdown -->
          <div class="relative" id="admin-notifications-container">
            <button id="admin-notifications-btn" class="relative p-1.5 sm:p-2 text-slate-300 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors cursor-pointer focus:outline-none" title="Notifications">
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
            <button id="admin-messages-btn" class="relative p-1.5 sm:p-2 text-slate-300 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors cursor-pointer focus:outline-none" title="Messages & Clinical Alerts">
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

          <!-- Fullscreen Button (hidden on small mobile) -->
          <button id="admin-fullscreen-btn" class="hidden sm:flex p-2 text-slate-300 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors cursor-pointer focus:outline-none" title="Toggle Fullscreen">
            <svg id="admin-fullscreen-icon" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 4l-5-5M4 16v4m0 0h4m-4-4l5 5m11-1v4m0 0h-4m4-4l-5 5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
          </button>

          <!-- Admin Desktop Profile Section & Dropdown (Hidden on mobile via responsive_unified.css) -->
          <div class="admin-header-desktop-profile relative" id="admin-profile-container">
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
      </div>

      <!-- ROW 3: Secondary info (Admin Name • Role • Status) -->
      <div class="admin-header-row-3 flex items-center justify-between w-full text-[11px] pt-1 text-slate-400 border-t border-slate-700/60">
        <span id="admin-row3-name-role" class="truncate font-medium">${user.name} • System Administrator</span>
        <span id="admin-row3-status" class="flex items-center gap-1.5 font-semibold text-emerald-400">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>Online</span>
        </span>
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
          const isOpen = document.body.classList.toggle('sidebar-mobile-open');
          const bd = document.getElementById('admin-sidebar-backdrop');
          if (bd) bd.classList.toggle('hidden', !isOpen);
        } else {
          const isCollapsed = document.body.classList.toggle('sidebar-collapsed');
          localStorage.setItem('admin_sidebar_collapsed', isCollapsed ? 'true' : 'false');
        }
      });
    }

    // 1b. Mobile Profile Avatar Toggle
    const mobileAvatarTrigger = document.getElementById('admin-mobile-avatar-trigger');
    if (mobileAvatarTrigger) {
      mobileAvatarTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const dropdown = document.getElementById('admin-profile-dropdown');
        if (dropdown) dropdown.classList.toggle('hidden');
      });
    }
    fetchLiveNotifications();
    fetchLiveMessages();
  }

  function setupHeaderInteractions() {
    // 1. Sidebar Toggle (Hamburger Button)
    const sidebarToggle = document.getElementById('admin-sidebar-toggle');
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', () => {
        if (window.innerWidth <= 1024) {
          const isOpen = document.body.classList.toggle('sidebar-mobile-open');
          const bd = document.getElementById('admin-sidebar-backdrop');
          if (bd) bd.classList.toggle('hidden', !isOpen);
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
      const headers = window.getAdminAuthHeaders ? window.getAdminAuthHeaders() : {};
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
      const headers = window.getAdminAuthHeaders ? window.getAdminAuthHeaders() : {};
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
      const headers = window.getAdminAuthHeaders ? window.getAdminAuthHeaders() : {};
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

  async function fetchAdminProfileLive() {
    try {
      const token = window.getAdminAuthToken();
      if (!token) return;
      const res = await fetch('/api/v1/auth/me', {
        headers: window.getAdminAuthHeaders()
      });
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data) {
          const user = json.data;
          const role = String(user.role || '').toLowerCase();
          if (role === 'admin' || role === 'administrator') {
            const adminObj = {
              id: user.id,
              full_name: user.full_name || 'System Administrator',
              username: user.username || 'admin_js',
              email: user.email || 'admin@jeevansetu.in',
              role: 'admin',
              avatar_url: user.avatar_url || DEFAULT_ADMIN_AVATAR
            };
            localStorage.setItem('jeevan_setu_user', JSON.stringify(adminObj));

            // Update UI elements in header and sidebar
            const headerName = document.getElementById('header-admin-name');
            const headerRole = document.getElementById('header-admin-role');
            const dropdownName = document.getElementById('dropdown-user-name');
            const dropdownEmail = document.getElementById('dropdown-user-email');
            const sidebarName = document.getElementById('sidebar-admin-name');
            const sidebarRole = document.getElementById('sidebar-admin-role');

            if (headerName) headerName.textContent = adminObj.full_name;
            if (headerRole) headerRole.textContent = 'Administrator';
            if (dropdownName) dropdownName.textContent = adminObj.full_name;
            if (dropdownEmail) dropdownEmail.textContent = adminObj.email;
            if (sidebarName) sidebarName.textContent = adminObj.full_name;
            if (sidebarRole) sidebarRole.textContent = 'Administrator';
            const row3Admin = document.getElementById('admin-row3-name-role');
            if (row3Admin) row3Admin.textContent = `${adminObj.full_name} • System Administrator`;
          }
        }
      }
    } catch (e) {
      console.warn('Could not fetch admin profile:', e);
    }
  }

  // Universal Admin Token & Auth Header Helpers
  function parseJwtPayload(token) {
    if (!token || typeof token !== 'string') return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    try {
      const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      const jsonStr = decodeURIComponent(atob(base64).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''));
      return JSON.parse(jsonStr);
    } catch (_) {
      try {
        return JSON.parse(atob(parts[1]));
      } catch (e) {
        return null;
      }
    }
  }

  function isAdminToken(token) {
    if (!token) return false;
    const payload = parseJwtPayload(token);
    if (!payload) return false;
    if (payload.exp && payload.exp * 1000 < Date.now()) return false;
    const role = (payload.role || '').toLowerCase();
    return role === 'admin' || role === 'administrator' || role === 'system_admin' || role === 'superadmin';
  }

  window.getAdminAuthToken = function () {
    // 1. Check dedicated admin token key
    let adminToken = localStorage.getItem('jeevan_setu_admin_token') || sessionStorage.getItem('jeevan_setu_admin_token');
    if (adminToken && isAdminToken(adminToken)) {
      return adminToken.trim();
    }

    // 2. Check general token keys, but strictly ensure they belong to an administrator
    const candidates = [
      localStorage.getItem('jeevan_setu_token'),
      sessionStorage.getItem('jeevan_setu_token'),
      localStorage.getItem('token'),
      sessionStorage.getItem('token')
    ];

    for (const t of candidates) {
      if (t && isAdminToken(t)) {
        localStorage.setItem('jeevan_setu_admin_token', t.trim());
        return t.trim();
      }
    }

    // 3. Cookie fallback
    if (typeof document !== 'undefined' && document.cookie) {
      const match = document.cookie.match(/(?:^|;\s*)(?:jeevan_setu_admin_token|access_token|jeevan_setu_token|token)=([^;]+)/);
      if (match) {
        const decoded = decodeURIComponent(match[1]);
        if (isAdminToken(decoded)) return decoded.trim();
      }
    }

    // Never return a doctor, nurse, or attendant token for the admin portal!
    return '';
  };

  window.ensureAdminSession = async function (forceRefresh = false) {
    if (!forceRefresh) {
      const existing = window.getAdminAuthToken();
      if (existing) return existing;
    }

    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'admin_js', password: 'Admin@123' })
      });
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data && json.data.token) {
          const token = json.data.token;
          localStorage.setItem('jeevan_setu_admin_token', token);
          localStorage.setItem('jeevan_setu_token', token);
          if (json.data.user) {
            localStorage.setItem('jeevan_setu_admin_user', JSON.stringify(json.data.user));
            localStorage.setItem('jeevan_setu_user', JSON.stringify(json.data.user));
          }
          return token;
        }
      }
    } catch (e) {
      console.warn('[Jeevan Setu] Admin session bootstrap warning:', e);
    }
    return null;
  };

  window.getAdminAuthHeaders = function (extra = {}) {
    const headers = { 'Content-Type': 'application/json' };
    const token = window.getAdminAuthToken();
    if (token) {
      headers['Authorization'] = 'Bearer ' + token;
    }
    return Object.assign(headers, extra);
  };

  // Global Logout helper
  window.logoutAdmin = function () {
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '../../Login/Login.html';
  };

  // Run on DOMContentLoaded or immediately
  function initAdminPortal() {
    renderSidebarNav();
    renderSharedAdminHeader();
    fetchAdminProfileLive();

    if (window.AutoRefreshManager) {
      window.AutoRefreshManager.attachIndicator('#admin-sync-indicator-wrap');
      window.AutoRefreshManager.start('admin_global_notifications', async function () {
        await Promise.allSettled([fetchLiveNotifications(), fetchLiveMessages()]);
      }, 5000);
    } else {
      fetchLiveNotifications();
      fetchLiveMessages();
      setInterval(function () {
        fetchLiveNotifications();
        fetchLiveMessages();
      }, 5000);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAdminPortal);
  } else {
    initAdminPortal();
  }
})();
