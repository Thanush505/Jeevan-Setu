/**
 * doctor_sidebar.js
 * Centralized, shared sidebar management, live header profile hydration, 
 * settings synchronization, and dynamic badge updates for all Doctor Portal pages.
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
    // Check if we are on the settings page
    const settingsForm = document.getElementById('doctor-settings-form') || document.querySelector('form.settings-form') || document.querySelector('form');
    const isSettingsPage = window.location.pathname.toLowerCase().includes('settings');
    if (!isSettingsPage) return;

    const docId = user.doctor_details ? user.doctor_details.doctor_id : user.id;
    const docCode = `DOC-${String(docId).padStart(3, '0')}`;
    const email = user.email || `${user.username}@jeevansetu.in`;
    const license = (user.doctor_details && user.doctor_details.license_number) || 'MCI-KA-2015-08942';
    const qual = (user.doctor_details && user.doctor_details.qualification) || 'MD Medicine, DM Critical Care';
    const exp = (user.doctor_details && user.doctor_details.experience_years) || 12;

    // Helper to safely set input values by query selector
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

    // Update settings header card name & role
    document.querySelectorAll('#settings-profile-name, .settings-user-name').forEach(el => {
      el.textContent = formattedName;
    });
    document.querySelectorAll('#settings-profile-role, .settings-user-role').forEach(el => {
      el.textContent = `${specialization} | ${docCode}`;
    });
  }

  async function syncLiveDoctorHeader() {
    // 1. Instant fallback from localStorage while waiting for network
    try {
      const cached = localStorage.getItem('jeevan_setu_user');
      if (cached) {
        const cachedUser = JSON.parse(cached);
        applyDoctorProfileToDOM(cachedUser);
      }
    } catch (e) {}

    // 2. Authoritative live fetch from /api/v1/auth/me
    const token = getAuthToken();
    if (!token) {
      // If no token on a protected doctor page, redirect to login
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
        // Stale or invalid session
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
    highlightActiveSidebarItem();
    syncLiveDoctorHeader();
    fetchSidebarBadgeCounts();
    setInterval(fetchSidebarBadgeCounts, 15000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDoctorSidebar);
  } else {
    initDoctorSidebar();
  }
})();
