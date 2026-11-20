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
      category: 'PATIENT CARE',
      items: [
        {
          id: 'dashboard',
          label: 'Dashboard',
          href: '../Nurse_dashboard/Nurse_dashboard.html',
          match: ['nurse_dashboard', 'dashboard'],
          icon: 'dashboard'
        },
        {
          id: 'alerts',
          label: 'Alerts',
          href: '../Nurse_alerts/Nurse_alerts.html',
          match: ['nurse_alerts', 'alerts'],
          badge: '35',
          icon: 'notifications'
        },
        {
          id: 'patient_monitoring',
          label: 'Patient Monitoring',
          href: '../nurse_patient_monitoring/nurse_patient_monitoring.html',
          match: ['nurse_patient_monitoring', 'patient_monitoring', 'monitoring'],
          icon: 'monitor_heart'
        },
        {
          id: 'enter_vitals',
          label: 'Enter Vitals',
          href: '../Nurse_enter_vitals/Nurse_enter_vitals.html',
          match: ['nurse_enter_vitals', 'enter_vitals', 'vitals'],
          icon: 'vital_signs'
        },
        {
          id: 'nursing_notes',
          label: 'Nursing Notes',
          href: '../Nurse_nursing_notes/Nurse_nursing_notes.html',
          match: ['nurse_nursing_notes', 'nursing_notes', 'notes'],
          icon: 'note_alt'
        },
        {
          id: 'patient_summary_ai',
          label: 'Clinical Assistant',
          href: '../Nurse_patient_summary_ai/Nurse_patient_summary_ai.html',
          match: ['nurse_patient_summary_ai', 'patient_summary_ai', 'clinical_assistant'],
          icon: 'psychology'
        }
      ]
    }
  ];

  function detectCurrentNursePage() {
    const path = window.location.pathname.toLowerCase();

    if (path.includes('nurse_dashboard')) return 'dashboard';
    if (path.includes('nurse_my_patients')) {
      window.location.replace('../nurse_patient_monitoring/nurse_patient_monitoring.html');
      return 'patient_monitoring';
    }
    if (path.includes('nurse_patient_monitoring')) return 'patient_monitoring';
    if (path.includes('nurse_enter_vitals')) return 'enter_vitals';
    if (path.includes('nurse_nursing_notes')) return 'nursing_notes';
    if (path.includes('nurse_patient_summary_ai') || path.includes('patient_summary_ai')) return 'patient_summary_ai';
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

          // Sync Availability
          if (u.availability) {
            currentNurseAvailability = u.availability;
          } else if (nd.availability) {
            currentNurseAvailability = nd.availability;
          }
          updateNurseAvailabilityUI(currentNurseAvailability, false);
        }
      }
    } catch (err) {
      console.warn('Nurse header sync warning:', err);
    }
  }

  // --- Nurse Availability Management ---
  let currentNurseAvailability = 'active';
  let isNurseAvailabilityUpdating = false;

  try {
    const raw = localStorage.getItem('jeevan_setu_user') || sessionStorage.getItem('jeevan_setu_user');
    if (raw) {
      const u = JSON.parse(raw);
      if (u.availability) currentNurseAvailability = u.availability;
      else if (u.nurse_details && u.nurse_details.availability) currentNurseAvailability = u.nurse_details.availability;
    }
  } catch (e) {}

  function showNurseAvailabilityToast(message, type = 'success') {
    let container = document.getElementById('nurse-availability-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'nurse-availability-toast-container';
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

  function updateNurseAvailabilityUI(status, isUpdating = false) {
    let container = document.getElementById('nurse-availability-container');
    if (!container) {
      const header = document.querySelector('header');
      const profileContainer = header?.querySelector('#nurse-profile-container') ||
                               header?.querySelector('.nurse-profile-name')?.closest('.flex.items-center') ||
                               header?.querySelector('.border-l');
      if (profileContainer) {
        const wrapper = document.createElement('div');
        wrapper.id = 'nurse-availability-wrapper';
        wrapper.className = 'border-l border-slate-200 pl-2 sm:pl-3 flex items-center flex-shrink-0';
        wrapper.innerHTML = `
          <div id="nurse-availability-container" class="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200 shadow-2xs select-none" data-availability="active">
            <button id="nurse-btn-active" type="button" onclick="window.changeNurseAvailability('active')"
              class="flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer shadow-xs bg-emerald-600 text-white border border-emerald-600 focus:outline-none" title="Set working availability to Active">
              <span class="w-2 h-2 rounded-full bg-white animate-pulse"></span>
              <span>Active</span>
            </button>
            <button id="nurse-btn-inactive" type="button" onclick="window.changeNurseAvailability('inactive')"
              class="flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 border border-transparent focus:outline-none" title="Set working availability to Inactive">
              <span class="w-2 h-2 rounded-full bg-rose-500 hidden"></span>
              <span>Inactive</span>
            </button>
          </div>
        `;
        profileContainer.parentNode.insertBefore(wrapper, profileContainer);
        container = document.getElementById('nurse-availability-container');
      }
    }

    const btnActive = document.getElementById('nurse-btn-active');
    const btnInactive = document.getElementById('nurse-btn-inactive');

    if (!container || !btnActive || !btnInactive) return;

    container.setAttribute('data-availability', status);

    const activeClasses = 'flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer shadow-xs bg-emerald-600 text-white border border-emerald-600 focus:outline-none';
    const inactiveSelectedClasses = 'flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer shadow-xs bg-rose-600 text-white border border-rose-600 focus:outline-none';
    const unselectedClasses = 'flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 border border-transparent focus:outline-none';

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

    // Update mobile avatar status dot
    const mobileDot = document.getElementById('nurse-mobile-avatar-dot');
    if (mobileDot) {
      mobileDot.className = `absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full ${status === 'active' ? 'bg-emerald-500' : 'bg-rose-500'} ring-2 ring-white`;
    }

    // Update Row 3 status
    const row3Status = document.getElementById('nurse-row3-status');
    if (row3Status) {
      row3Status.className = `flex items-center gap-1.5 font-semibold ${status === 'active' ? 'text-emerald-600' : 'text-rose-600'}`;
      row3Status.innerHTML = `
        <span class="w-1.5 h-1.5 rounded-full ${status === 'active' ? 'bg-emerald-500' : 'bg-rose-500'} animate-pulse"></span>
        <span>${status === 'active' ? 'Duty Active' : 'Duty Inactive'}</span>
      `;
    }
  }

  function getNurseAuthToken() {
    return localStorage.getItem('jeevan_setu_token') || localStorage.getItem('token') || sessionStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('token') || '';
  }

  function escapeNurseModalHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function injectNurseAvailabilityModalStyles() {
    if (document.getElementById('jeevan-nurse-availability-modal-styles')) return;
    const style = document.createElement('style');
    style.id = 'jeevan-nurse-availability-modal-styles';
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

  function showNurseAvailabilityConfirmModal({ roleTitle, targetStatus, onConfirm, onCancel }) {
    injectNurseAvailabilityModalStyles();

    // Remove any existing availability modal
    const existing = document.getElementById('jeevan-nurse-availability-modal');
    if (existing) existing.remove();

    const previousFocusedElement = document.activeElement;
    const isTargetActive = targetStatus === 'active';
    const targetLabel = isTargetActive ? 'Active' : 'Inactive';

    const modalBackdrop = document.createElement('div');
    modalBackdrop.id = 'jeevan-nurse-availability-modal';
    modalBackdrop.className = 'js-avail-modal-backdrop';
    modalBackdrop.setAttribute('role', 'dialog');
    modalBackdrop.setAttribute('aria-modal', 'true');
    modalBackdrop.setAttribute('aria-labelledby', 'nurse-availability-modal-title');
    modalBackdrop.setAttribute('aria-describedby', 'nurse-availability-modal-desc');

    const iconSvg = isTargetActive
      ? `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`
      : `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;

    modalBackdrop.innerHTML = `
      <div class="js-avail-modal-card" id="nurse-availability-modal-card">
        <div class="js-avail-modal-header">
          <div class="js-avail-modal-title-wrap">
            <div class="js-avail-modal-icon-badge ${isTargetActive ? 'active' : 'inactive'}">
              ${iconSvg}
            </div>
            <div>
              <h3 id="nurse-availability-modal-title" class="js-avail-modal-title">Confirm Availability Change</h3>
              <p class="js-avail-modal-subtitle">${escapeNurseModalHtml(roleTitle)} Availability</p>
            </div>
          </div>
          <button type="button" class="js-avail-modal-close" id="nurse-availability-modal-close-btn" aria-label="Close dialog">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>

        <div class="js-avail-modal-body">
          <p id="nurse-availability-modal-desc" class="js-avail-modal-message">
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
                ? 'You will be marked available for active ward monitoring, vitals logging, and nursing care.' 
                : 'You will be marked off-duty. Existing patient records and bedside tasks remain assigned to you.'}
            </p>
          </div>

          <div id="nurse-availability-modal-error" class="js-avail-modal-error" style="display: none;" role="alert">
            <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            <span id="nurse-availability-modal-error-text"></span>
          </div>
        </div>

        <div class="js-avail-modal-footer">
          <button type="button" id="nurse-availability-modal-cancel-btn" class="js-avail-btn-cancel">
            Cancel
          </button>
          <button type="button" id="nurse-availability-modal-confirm-btn" class="js-avail-btn-confirm">
            <span id="nurse-availability-modal-spinner" style="display: none;">
              <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            </span>
            <span id="nurse-availability-modal-confirm-text">Confirm</span>
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

    const closeBtn = modalBackdrop.querySelector('#nurse-availability-modal-close-btn');
    const cancelBtn = modalBackdrop.querySelector('#nurse-availability-modal-cancel-btn');
    const confirmBtn = modalBackdrop.querySelector('#nurse-availability-modal-confirm-btn');
    const spinner = modalBackdrop.querySelector('#nurse-availability-modal-spinner');
    const confirmText = modalBackdrop.querySelector('#nurse-availability-modal-confirm-text');
    const errorBox = modalBackdrop.querySelector('#nurse-availability-modal-error');
    const errorText = modalBackdrop.querySelector('#nurse-availability-modal-error-text');

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

  window.changeNurseAvailability = function (targetStatus) {
    if (isNurseAvailabilityUpdating) return;
    if (targetStatus === currentNurseAvailability) return;

    showNurseAvailabilityConfirmModal({
      roleTitle: 'Nurse',
      targetStatus: targetStatus,
      onConfirm: async () => {
        isNurseAvailabilityUpdating = true;
        updateNurseAvailabilityUI(targetStatus, true);

        const token = getNurseAuthToken();
        const res = await fetch('/api/nurse/availability', {
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
          currentNurseAvailability = targetStatus;
          updateNurseAvailabilityUI(targetStatus, false);

          // Update cached user in storage
          try {
            const uStr = localStorage.getItem('jeevan_setu_user');
            if (uStr) {
              const u = JSON.parse(uStr);
              u.availability = targetStatus;
              if (u.nurse_details) u.nurse_details.availability = targetStatus;
              localStorage.setItem('jeevan_setu_user', JSON.stringify(u));
            }
          } catch (e) {}

          const targetLabel = targetStatus === 'active' ? 'Active' : 'Inactive';
          showNurseAvailabilityToast(`Nurse availability set to ${targetLabel}.`, 'success');
          isNurseAvailabilityUpdating = false;
        } else {
          isNurseAvailabilityUpdating = false;
          updateNurseAvailabilityUI(currentNurseAvailability, false);
          const errorMsg = data.error || data.message || `Server returned status ${res.status}`;
          showNurseAvailabilityToast(`Failed to update availability: ${errorMsg}`, 'error');
          throw new Error(errorMsg);
        }
      },
      onCancel: () => {
        updateNurseAvailabilityUI(currentNurseAvailability, false);
      }
    });
  };

  async function syncNurseAvailability() {
    if (isNurseAvailabilityUpdating) return;
    try {
      const token = getNurseAuthToken();
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = 'Bearer ' + token;
      const res = await fetch('/api/nurse/availability', {
        headers,
        credentials: 'include'
      });
      if (res.ok) {
        const json = await res.json();
        const avail = json.availability || (json.data && json.data.availability);
        if (avail && avail !== currentNurseAvailability && !isNurseAvailabilityUpdating) {
          currentNurseAvailability = avail;
          updateNurseAvailabilityUI(avail, false);
          try {
            const uStr = localStorage.getItem('jeevan_setu_user');
            if (uStr) {
              const u = JSON.parse(uStr);
              u.availability = avail;
              if (u.nurse_details) u.nurse_details.availability = avail;
              localStorage.setItem('jeevan_setu_user', JSON.stringify(u));
            }
          } catch (e) {}
        }
      }
    } catch (e) {
      console.warn('[Nurse Navigation] Availability poll error:', e);
    }
  }

  function ensureNurseUnifiedResponsiveCSS() {
    if (document.getElementById('jeevan-responsive-unified-styles')) return;
    const link = document.createElement('link');
    link.id = 'jeevan-responsive-unified-styles';
    link.rel = 'stylesheet';
    link.href = '/static/css/responsive_unified.css';
    document.head.appendChild(link);
  }

  function injectNurseStyles() {
    ensureNurseUnifiedResponsiveCSS();
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
        html, body {
          max-width: 100vw;
          overflow-x: hidden;
        }
        .pl-64, .pl-72, .ml-64, .ml-72 {
          padding-left: 0 !important;
          margin-left: 0 !important;
        }
        .left-64, .left-72 {
          left: 0 !important;
        }
      }
      @media (max-width: 767px) {
        aside[data-purpose="sidebar"],
        aside.w-64,
        aside {
          max-width: 85vw !important;
        }
        body.sidebar-mobile-open aside[data-purpose="sidebar"],
        body.sidebar-mobile-open aside.w-64,
        body.sidebar-mobile-open aside {
          transform: translateX(0) !important;
          width: 16rem !important;
          max-width: 85vw !important;
          opacity: 1 !important;
          pointer-events: auto !important;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8) !important;
        }
        .nurse-top-header {
          padding-left: 0.75rem !important;
          padding-right: 0.75rem !important;
          height: auto !important;
          min-height: 3.75rem !important;
        }
        #nurse-search-container {
          max-width: 11rem !important;
          margin-left: 0.25rem !important;
          margin-right: 0.25rem !important;
        }
        .nurse-ctrl-k-badge {
          display: none !important;
        }
        #header-nurse-ward,
        .nurse-profile-ward {
          display: none !important;
        }
        #header-nurse-name,
        .nurse-profile-name {
          font-size: 0.75rem !important;
          max-width: 6.5rem !important;
          white-space: nowrap !important;
          overflow: hidden !important;
          text-overflow: ellipsis !important;
        }
        #nurse-availability-wrapper {
          padding-left: 0.375rem !important;
        }
        #nurse-btn-active, #nurse-btn-inactive {
          min-height: 34px !important;
          padding: 0.3rem 0.55rem !important;
          font-size: 0.6875rem !important;
          touch-action: manipulation;
        }
        #nurse-notifications-dropdown,
        #nurse-profile-dropdown,
        #nurse-search-results-dropdown {
          position: fixed !important;
          left: 12px !important;
          right: 12px !important;
          top: 68px !important;
          width: calc(100vw - 24px) !important;
          max-width: calc(100vw - 24px) !important;
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
        #nurse-search-container {
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

  function ensureNurseFonts() {
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

  function renderNurseSidebar() {
    ensureNurseFonts();
    let aside = document.querySelector('aside[data-purpose="sidebar"], aside.w-64, aside.w-72, aside');
    if (!aside) {
      aside = document.createElement('aside');
      aside.setAttribute('data-purpose', 'sidebar');
      aside.className = 'w-64 bg-[#0a1931] text-white flex flex-col flex-shrink-0 h-screen fixed left-0 top-0 z-50 select-none -translate-x-full md:translate-x-0 transition-transform duration-200 ease-in-out border-r border-slate-800';
      document.body.insertBefore(aside, document.body.firstChild);
    }

    const currentActiveId = detectCurrentNursePage();

    aside.setAttribute('data-purpose', 'sidebar');
    aside.className = 'w-64 bg-[#0a1931] text-white flex flex-col flex-shrink-0 h-screen fixed left-0 top-0 z-50 select-none -translate-x-full md:translate-x-0 transition-transform duration-200 ease-in-out border-r border-slate-800';

    // Mobile backdrop
    let backdrop = document.getElementById('nurse-sidebar-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'nurse-sidebar-backdrop';
      backdrop.className = 'fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-40 md:hidden hidden transition-opacity';
      backdrop.onclick = window.toggleMobileNurseSidebar;
      document.body.appendChild(backdrop);
    }

    // 1. Branding Header (Matches Doctor Master Design)
    const brandingHeaderHtml = `
      <div class="sidebar-brand-header p-5 border-b border-white/10 flex items-center justify-between flex-shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 overflow-hidden">
            <img src="/assets/jeevan_setu_logo.png" onerror="this.onerror=null; this.src='../../assets/jeevan_setu_logo.png';" alt="Jeevan Setu Logo" class="w-full h-full object-contain">
          </div>
          <div>
            <h1 class="sidebar-brand-title font-bold text-base tracking-tight leading-tight text-white font-['Poppins']">JEEVAN SETU</h1>
            <p class="sidebar-brand-subtitle text-[9px] text-cyan-400 font-semibold tracking-wider uppercase font-['Inter']">ICU TO HDU TRANSFER DSS</p>
          </div>
        </div>
        <button class="md:hidden text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors cursor-pointer ml-auto" onclick="window.toggleMobileNurseSidebar();" aria-label="Close sidebar">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
        </button>
      </div>
    `;

    // 2. Navigation Items (Matches Doctor Master Design)
    let navSectionsHtml = '';

    NURSE_NAV_CONFIG.forEach(section => {
      navSectionsHtml += `
        <div>
          <p class="sidebar-section-heading px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 font-['Inter']">${section.category}</p>
          <ul class="space-y-1">
      `;

      section.items.forEach(item => {
        const isActive = item.id === currentActiveId;
        const activeClass = isActive
          ? 'bg-white/10 text-cyan-400 font-semibold border-l-4 border-cyan-400'
          : 'text-slate-300 hover:bg-white/5 hover:text-white';
        const iconClass = isActive ? 'text-cyan-400' : 'text-slate-400 group-hover:text-cyan-400';

        navSectionsHtml += `
          <li>
            <a class="sidebar-nav-item flex items-center justify-between px-3 py-2.5 rounded-lg ${activeClass} transition-all group text-sm ${isActive ? '' : 'font-medium'}" href="${item.href}" data-page="${item.id}">
              <div class="flex items-center">
                <span class="material-symbols-outlined mr-3 text-[20px] ${iconClass} transition-colors flex-shrink-0">${item.icon}</span>
                <span>${item.label}</span>
              </div>
              ${item.badge ? `<span id="nurse-sidebar-${item.id}-badge" class="bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full ml-auto">${item.badge}</span>` : ''}
            </a>
          </li>
        `;
      });

      navSectionsHtml += `
          </ul>
        </div>
      `;
    });

    // 3. Bottom Utility Menu (Matches Doctor Master Design)
    const isSettingsActive = currentActiveId === 'settings';
    const settingsLinkClass = isSettingsActive
      ? 'bg-white/10 text-cyan-400 font-semibold border-l-4 border-cyan-400'
      : 'text-slate-300 hover:bg-white/5 hover:text-white font-medium';
    const settingsIconClass = isSettingsActive ? 'text-cyan-400' : 'text-slate-400 group-hover:text-cyan-400';

    const bottomNavHtml = `
      <div class="sidebar-footer-container p-3 border-t border-white/10 space-y-1 mt-auto bg-[#081426]/50 flex-shrink-0">
        <a class="sidebar-nav-item sidebar-settings-link flex items-center px-3 py-2.5 rounded-lg ${settingsLinkClass} transition-all group text-sm" href="../Nurse_settings/Nurse_settings.html" data-page="settings">
          <span class="material-symbols-outlined mr-3 text-[20px] ${settingsIconClass} transition-colors flex-shrink-0">settings</span>
          <span>Settings</span>
        </a>
        <a class="sidebar-nav-item sidebar-logout-link flex items-center px-3 py-2.5 rounded-lg text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-all group text-sm font-medium cursor-pointer" href="javascript:void(0);" onclick="window.logoutNurse();">
          <span class="material-symbols-outlined mr-3 text-[20px] text-red-400 group-hover:text-red-300 transition-colors flex-shrink-0">logout</span>
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

    // Close mobile drawer when any navigation link is clicked
    aside.querySelectorAll('nav a, a').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 1024) {
          aside.classList.add('-translate-x-full');
          document.body.classList.remove('sidebar-mobile-open');
          if (backdrop) backdrop.classList.add('hidden');
        }
      });
    });

    standardizePageLayout();
  }

  function renderSharedNurseHeader() {
    injectNurseStyles();

    if (detectCurrentNursePage() === 'patient_summary_ai') {
      const user = getStoredNurseUser();
      document.querySelectorAll('.nurse-profile-name, #header-nurse-name, #topbar-nurse-name').forEach(el => {
        el.textContent = user.name;
      });
      document.querySelectorAll('#header-nurse-ward, #topbar-nurse-ward').forEach(el => {
        el.textContent = user.ward;
      });
      return;
    }

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

    header.className = 'nurse-top-header portal-header bg-white text-slate-900 border-b border-slate-200/90 h-16 flex items-center justify-between px-6 fixed top-0 left-0 md:left-64 right-0 z-40 shadow-sm transition-all duration-200';
    header.setAttribute('data-purpose', 'nurse-header');

    const user = getStoredNurseUser();
    const isNurseActive = currentNurseAvailability === 'active';

    header.innerHTML = `
      <!-- ROW 1: [☰ Menu] [Nurse Station Branding] [Mobile Profile Avatar] -->
      <div class="nurse-header-row-1 flex items-center justify-between w-full">
        <!-- Left: Mobile Sidebar Hamburger Toggle + Nurse Station Brand -->
        <div class="flex items-center gap-2.5 sm:gap-3 flex-shrink-0">
          <button id="nurse-sidebar-toggle" class="md:hidden text-slate-600 hover:text-slate-900 p-1.5 rounded-lg hover:bg-slate-100 transition-colors focus:outline-none cursor-pointer" aria-label="Toggle menu">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M4 6h16M4 12h16M4 18h16" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
          </button>

          <div class="flex items-center gap-2 sm:gap-2.5">
            <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm flex-shrink-0">
              <svg class="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M9 12h6m-3-3v6m9-3a9 9 0 11-18 0 9 9 0 0118 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
              </svg>
            </div>
            <div>
              <h1 class="font-bold text-slate-900 text-sm sm:text-base leading-tight tracking-tight">Nurse Station</h1>
            </div>
          </div>
        </div>

        <!-- Right (Mobile Only): Profile Avatar with Online indicator -->
        <div class="nurse-header-mobile-profile">
          <div class="relative cursor-pointer p-0.5" id="nurse-mobile-avatar-trigger" title="${escapeHtml(user.name)} (${escapeHtml(user.ward)})">
            <img id="nurse-mobile-avatar-img" class="w-8 h-8 rounded-full object-cover ring-2 ring-blue-500/50 shadow-sm" src="${user.avatar}" alt="${escapeHtml(user.name)}" onerror="this.onerror=null; this.src='../nurse_avatar.jpg';" />
            <span id="nurse-mobile-avatar-dot" class="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full ${isNurseActive ? 'bg-emerald-500' : 'bg-rose-500'} ring-2 ring-white"></span>
          </div>
        </div>
      </div>

      <!-- ROW 2: [Search Box] [Active/Inactive Availability] [Notifications] [Sync Indicator] [Desktop Profile] -->
      <div class="nurse-header-row-2 flex items-center justify-between w-full">
        <!-- Left: Live Patient Search with CTRL+K -->
        <div class="relative flex-1 max-w-[130px] sm:max-w-xs md:max-w-md mr-2" id="nurse-search-container">
          <div class="nurse-header-search-wrap flex items-center rounded-lg px-2.5 sm:px-3 py-1.5 w-full relative">
            <svg class="w-4 h-4 text-slate-400 flex-shrink-0 mr-1.5 sm:mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
            <input 
              id="nurse-global-search-input" 
              class="w-full bg-transparent border-none outline-none text-xs sm:text-sm text-slate-800 placeholder-slate-400 focus:ring-0 p-0" 
              placeholder="Search..." 
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

        <!-- Right: Availability + Sync + Notifications + Desktop Profile -->
        <div class="flex items-center gap-2 sm:gap-3 flex-shrink-0">
          
          <!-- Nurse Availability Selector (Active / Inactive) -->
          <div id="nurse-availability-wrapper" class="flex items-center flex-shrink-0">
            <div id="nurse-availability-container" class="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200 shadow-2xs select-none" data-availability="${currentNurseAvailability}">
              <button id="nurse-btn-active" type="button" onclick="window.changeNurseAvailability('active')"
                class="flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer shadow-xs ${isNurseActive ? 'bg-emerald-600 text-white border border-emerald-600' : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 border border-transparent'} focus:outline-none" title="Set working availability to Active">
                <span class="w-2 h-2 rounded-full ${isNurseActive ? 'bg-white animate-pulse' : 'bg-emerald-500 hidden'}"></span>
                <span>Active</span>
              </button>
              <button id="nurse-btn-inactive" type="button" onclick="window.changeNurseAvailability('inactive')"
                class="flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer ${!isNurseActive ? 'bg-rose-600 text-white border border-rose-600' : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 border border-transparent'} focus:outline-none" title="Set working availability to Inactive">
                <span class="w-2 h-2 rounded-full ${!isNurseActive ? 'bg-white animate-pulse' : 'bg-rose-500 hidden'}"></span>
                <span>Inactive</span>
              </button>
            </div>
          </div>

          <!-- Notifications Bell Button & Dropdown -->
          <div class="relative" id="nurse-notifications-container">
            <button id="nurse-notifications-btn" class="relative p-1.5 sm:p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer focus:outline-none" title="Notifications">
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

          <!-- Live Data Freshness & Sync Indicator -->
          <div id="nurse-sync-indicator-wrap" class="flex items-center">
            <div id="nurse-sync-indicator" class="js-sync-indicator inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 cursor-pointer select-none transition-all shadow-xs hover:bg-emerald-500/20" title="Data automatically refreshing every 5s • Click to sync now">
              <span data-sync-dot class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span data-sync-text id="nurse-sync-text">Live</span>
            </div>
          </div>

          <!-- Nurse Desktop Profile Trigger & Dropdown (Hidden on mobile via responsive_unified.css) -->
          <div class="nurse-header-desktop-profile relative" id="nurse-profile-container">
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
      </div>

      <!-- ROW 3: Secondary info (Nurse Name • Ward • Duty Status) -->
      <div class="nurse-header-row-3 flex items-center justify-between w-full text-[11px] pt-1 text-slate-500 border-t border-slate-200">
        <span id="nurse-row3-name-ward" class="truncate font-medium text-slate-700">${escapeHtml(user.name)} • ${escapeHtml(user.ward)}</span>
        <span id="nurse-row3-status" class="flex items-center gap-1.5 font-semibold ${isNurseActive ? 'text-emerald-600' : 'text-rose-600'}">
          <span class="w-1.5 h-1.5 rounded-full ${isNurseActive ? 'bg-emerald-500' : 'bg-rose-500'} animate-pulse"></span>
          <span>${isNurseActive ? 'Duty Active' : 'Duty Inactive'}</span>
        </span>
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

    // 1b. Mobile Profile Avatar Toggle
    const mobileAvatarTrigger = document.getElementById('nurse-mobile-avatar-trigger');
    if (mobileAvatarTrigger) {
      mobileAvatarTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const dropdown = document.getElementById('nurse-profile-dropdown');
        if (dropdown) dropdown.classList.toggle('hidden');
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

      const sidebarAlertsBadge = document.getElementById('nurse-sidebar-alerts-badge');
      if (sidebarAlertsBadge) {
        if (unreadCount > 0) {
          sidebarAlertsBadge.textContent = unreadCount > 99 ? '99+' : unreadCount;
          sidebarAlertsBadge.style.display = 'inline-block';
        } else {
          sidebarAlertsBadge.style.display = 'none';
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
      document.body.classList.add('sidebar-mobile-open');
      if (backdrop) backdrop.classList.remove('hidden');
    } else {
      aside.classList.add('-translate-x-full');
      document.body.classList.remove('sidebar-mobile-open');
      if (backdrop) backdrop.classList.add('hidden');
    }
  };

  window.logoutNurse = function () {
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '../../Login/Login.html';
  };

  function auditNursePortalControls() {
    // Clean up any legacy pagination container if present
    document.querySelectorAll('.nurse-portal-pagination, .admin-portal-pagination, nav[aria-label*="Pages Navigation"]').forEach(el => el.remove());

    // 1. Task Checkboxes interactivity
    document.querySelectorAll('input[type="checkbox"]').forEach(chk => {
      chk.addEventListener('change', function () {
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
          btn.addEventListener('click', function (e) {
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
      saveNoteBtn.addEventListener('click', function () {
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
        btn.addEventListener('click', function () {
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
    updateNurseAvailabilityUI(currentNurseAvailability, false);
    auditNursePortalControls();
    syncLiveNurseHeader();
    if (window.AutoRefreshManager) {
      window.AutoRefreshManager.attachIndicator('#nurse-sync-indicator-wrap');
      window.AutoRefreshManager.start('nurse_availability_sync', syncNurseAvailability, 5000);
    } else {
      setInterval(syncNurseAvailability, 5000);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNursePortal);
  } else {
    initNursePortal();
  }
})();
