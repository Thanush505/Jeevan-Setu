import os

# 1. UPDATE LOGIN.HTML
login_path = r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Login/Login.html'
with open(login_path, 'r', encoding='utf-8') as f:
    login_html = f.read()

# Fix demo button admin_js
login_html = login_html.replace("fillDemo('admin', 'Admin@123', 'admin')", "fillDemoFix()")

# Replace auth-routing script
old_script_start = login_html.find('<script id="auth-routing">')
if old_script_start != -1:
    new_script = """<script id="auth-routing">
function fillDemo(username, password, role) {
  var u = document.getElementById('username');
  var p = document.getElementById('password');
  if (u) u.value = username;
  if (p) p.value = password;

  var tabClinical = document.getElementById('tab-clinical');
  var tabAdmin = document.getElementById('tab-admin');
  var roleSection = document.getElementById('clinical-role-container');

  if (role === 'admin') {
    if (tabAdmin) {
      tabAdmin.classList.add('bg-surface-container-lowest','shadow-sm','text-primary');
      tabAdmin.classList.remove('text-on-surface-variant');
    }
    if (tabClinical) {
      tabClinical.classList.remove('bg-surface-container-lowest','shadow-sm','text-primary');
      tabClinical.classList.add('text-on-surface-variant');
    }
    if (roleSection) roleSection.style.display = 'none';
  } else {
    if (tabClinical) {
      tabClinical.classList.add('bg-surface-container-lowest','shadow-sm','text-primary');
      tabClinical.classList.remove('text-on-surface-variant');
    }
    if (tabAdmin) {
      tabAdmin.classList.remove('bg-surface-container-lowest','shadow-sm','text-primary');
      tabAdmin.classList.add('text-on-surface-variant');
    }
    if (roleSection) roleSection.style.display = '';
    var radio = document.querySelector('input[name="clinical-role"][value="' + role + '"]');
    if (radio) radio.checked = true;
  }
}

function showLoginAlert(msg, type = 'error') {
  let box = document.getElementById('login-alert-box');
  if (!box) {
    box = document.createElement('div');
    box.id = 'login-alert-box';
    const form = document.getElementById('login-form');
    if (form && form.parentNode) {
      form.parentNode.insertBefore(box, form);
    }
  }
  const bgClass = type === 'error' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200';
  box.className = 'p-3 rounded-lg text-xs font-semibold border mb-3 ' + bgClass;
  box.textContent = msg;
}

(function(){
  var tabClinical = document.getElementById('tab-clinical');
  var tabAdmin = document.getElementById('tab-admin');
  var roleSection = document.getElementById('clinical-role-container');

  if (tabClinical && tabAdmin) {
    tabClinical.addEventListener('click', function(e){
      e.preventDefault();
      tabClinical.classList.add('bg-surface-container-lowest','shadow-sm','text-primary');
      tabClinical.classList.remove('text-on-surface-variant');
      tabAdmin.classList.remove('bg-surface-container-lowest','shadow-sm','text-primary');
      tabAdmin.classList.add('text-on-surface-variant');
      if (roleSection) roleSection.style.display = '';
    });
    tabAdmin.addEventListener('click', function(e){
      e.preventDefault();
      tabAdmin.classList.add('fg-surface-container-lowest','shadow-sm','text-primary');
      tabAdmin.classList.remove('text-on-surface-variant');
      tabClinical.classList.remove('bg-surface-container-lowest','shadow-sm','text-primary');
      tabClinical.classList.add('text-on-surface-variant');
      if (roleSection) roleSection.style.display = 'none';
    });
  }

  var form = document.getElementById('login-form');
  if (form) {
    form.addEventListener('submit', async function(e){
      e.preventDefault();
      var ov = document.getElementById('loading-overlay');
      if (ov) ov.classList.remove('hidden');

      const usernameVal = (document.getElementById('username')?.value || '').trim();
      const passwordVal = document.getElementById('password')?.value || '';

      if (!usernameVal || !passwordVal) {
        if (ov) ov.classList.add('hidden');
        showLoginAlert('Please enter both username and password.');
        return;
      }

      try {
        const res = await fetch('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: usernameVal, password: passwordVal })
        });
        const json = await res.json();
        
        if (!res.ok || !json.success || !json.data) {
          if (ov) ov.classList.add('hidden');
          showLoginAlert(json.error || 'Invalid username or password. Please try again.');
          return;
        }

        // 1. Purge ALL stale auth/user keys to prevent identity leakage across accounts
        localStorage.clear();
        sessionStorage.clear();

        const token = json.data.token;
        const user = json.data.user;

        // 2. Set newly authenticated credentials
        localStorage.setItem('jeevan_setu_token', token);
        localStorage.setItem('token', token);
        localStorage.setItem('jeevan_setu_user', JSON.stringify(user));
        localStorage.setItem('user', JSON.stringify(user));
        localStorage.setItem('user_id', String(user.id));
        localStorage.setItem('role', user.role);
        localStorage.setItem('userName', user.full_name || user.username);

        sessionStorage.setItem('jeevan_setu_token', token);
        sessionStorage.setItem('jeevan_setu_user', JSON.stringify(user));

        // 3. Sync session cookie with Flask-Login in background
        const fd = new FormData();
        fd.append('username', usernameVal);
        fd.append('password', passwordVal);
        await fetch('/auth/login', { method: 'POST', body: fd }).catch(function(){});

        // 4. Role-based redirect to exact portal
        const role = (user.role || '').toLowerCase();
        if (role === 'admin') {
          window.location.href = '../Admin/Administrator_dashboard_/Administrator_dashboard_.html';
        } else if (role === 'doctor') {
          window.location.href = '../Doctor/Doctor_dashboard_/Doctor_dashboard_.html';
        } else if (role === 'nurse') {
          window.location.href = '../Nurse/Nurse_dashboard/Nurse_dashboard.html';
        } else if (role === 'attendant') {
          window.location.href = '../Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html';
        } else {
          window.location.href = '../Doctor/Doctor_dashboard_/Doctor_dashboard_.html';
        }
      } catch (err) {
        if (ov) ov.classList.add('hidden');
        showLoginAlert('Network error during authentication. Please verify your connection.');
        console.error('Login error', err);
      }
    });
  }
})();
</script>
\n</body></html>"""
    login_html = login_html[:old_script_start] + new_script
    with open(login_path, 'w', encoding='utf-8') as f:
        f.write(login_html)
    print('[1/FINISHED] Login.html updated')


# 2. REMOVE AUTO-AUTH IN Doctor_patient_reports.html AND Admin_clinical_reports.html
report_paths = [
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Doctor/Doctor_patient_reports/Doctor_patient_reports.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Admin/Admin_clinical_reports/Admin_clinical_reports.html'
]
for rp in report_paths:
    if os.path.exists(rp):
        with open(rp, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace ensureAuthToken with safe reader
        if 'async function ensureAuthToken()' in content:
            safe_ensure = """async function ensureAuthToken() {
      let token = localStorage.getItem('jeevan_setu_token') || localStorage.getItem('token') || sessionStorage.getItem('jeevan_setu_token');
      return token || '';
    }"""
            # Find start and end of old ensureAuthToken
            s1 = content.find('async function ensureAuthToken(')
            s2 = content.find(function logoutDoctor(' if 'Doctor' in rp else content.find(function logoutAdmin())
            if s1 != -1 and s2 != -1 and s2 > s1:
                content = content[:s1] + safe_ensure + "\n\n    " + content[s2:]
                with open(rp, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f'[2/FINISHED] Auto-auth removed from {rp}')


# 3. CLEAN NURSE TEMPLATES - Replace hardcoded 'Nurse Priya' markup with 'Nurse'
nurse_files = [
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_dashboard/Nurse_dashboard.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_settings/Nurse_settings.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_i_o_chart/Nurse_i_o_chart.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_medication_log/Nurse_medication_log.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_nursing_notes/Nurse_nursing_notes.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/nurse_patient_monitoring/nurse_patient_monitoring.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_enter_vitals/Nurse_enter_vitals.html'
]
for nf in nurse_files:
    if os.path.exists(nf):
        with open(nf, 'r', encoding='utf-8') as f:
            c = f.read()
        c = c.replace('Nurse Priya', 'Nurse')
        c = c.replace('alt="Nurse Priya"', 'alt="Nurse Profile")
        with open(nf, 'w', encoding='utf-8') as fw:
            fw.write(c)
        print(f'[3/FINISHED] Cleaned hardcoding in {nf}')


# 4. UPDATE NURSE NEGIATION JS
back_nurse_nav = r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/nurse_navigation.js'
with open(back_nurse_nav, 'r', encoding='utf-8') as f:
    n = f.read()

# Make sure logout clears all keys
old_logout = """window.logutNurse = function () {"""
new_logout = """window.logoutNurse = function () {
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '../../Login/Login.html';
  };"""

if old_logout in n:
    n = n.replace(old_logout, new_logout)

    with open(back_nurse_nav, 'w', encoding='utf-8') as f:
        f.write(n)
    print('[4/FINISHED] nurse_navigation.js updated')

print('ALL AUTH MIX-UP FIXES APPLIED SUCCESSFULLY!')
