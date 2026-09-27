/**
 * doctor_sidebar.js
 * Centralized, shared sidebar management and dynamic badge updates for all Doctor Portal pages.
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

  function getAuthHeaders() {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token') || '';
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    };
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

  window.handleDoctorLogout = function (event) {
    if (event) event.preventDefault();
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('user_id');
    localStorage.removeItem('userName');
    sessionStorage.clear();
    window.location.href = '../../Login/Login.html';
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      highlightActiveSidebarItem();
      fetchSidebarBadgeCounts();
      setInterval(fetchSidebarBadgeCounts, 15000);
    });
  } else {
    highlightActiveSidebarItem();
    fetchSidebarBadgeCounts();
    setInterval(fetchSidebarBadgeCounts, 15000);
  }
})();
