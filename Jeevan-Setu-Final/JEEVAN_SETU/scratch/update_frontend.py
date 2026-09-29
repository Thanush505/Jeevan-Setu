import os

# 1. UPDATE LOGIN.HTML
login_path = r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Login/Login.html'
with open(login_path, 'r', encoding='utf-8') as file:
    login_html = file.read()

# Fix demo button admin_jslogin_html = login_html.replace("fillDemo('admin', 'Admin@123', 'admin')", "fillDemo('admin_js', 'Admin@123', 'admin')")

position = login_html.find('<script id="auth-routing">')
if position != -1:
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

function showLoginAlert(msg, type) {
  type = type || 'error';
  var box = document.getElementById('login-alert-box');
  if (!box) {
    box = document.createElement('div');
    box.id = 'login-alert-box';
    var form = document.getElementById('login-form');
    if (form && form.parentNode) {
      form.parentNode.insertBefore(box, form);
    }
  }
  var bgClass = type === 'error' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200';
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

      var uInput = document.getElementById('username');
      var pInput = document.getElementById('password');
      var usernameVal = (uInput ? uInput.value : '').trim();
      var passwordVal = (pInput ? pInput.value : '');

      if (!usernameVal || !passwordVal) {
        if (ov) ov.classList.add('hidden');
        showLoginAlert('Please enter both username and password.');
        return;
      }

      try {
        var res = await fetch('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: usernameVal, password: passwordVal })
        });
        var json = await res.json();

        if (!res.ok || !json.success || !json.data) {
          if (ov) ov.classList.add('hidden');
          showLoginAlert(json.error || 'Invalid username or password. Please try again.');
          return;
        }

        // Clear all previous tokens/user data to prevent cross-account leakage
        localStorage.clear();
        sessionStorage.clear();

        var token = json.data.token;
        var user = json.data.user;

        localStorage.setItem('jeevan_setu_token', token);
        localStorage.setItem('token', token);
        localStorage.setItem('jeevan_setu_user', JSON.stringify(user));
        localStorage.setItem('user', JSON.stringify(user));
        localStorage.setItem('user_id', String(user.id));
        localStorage.setItem('role', user.role);
        localStorage.setItem('userName', user.full_name || user.username);

        sessionStorage.setItem('jeevan_setu_token', token);
        sessionStorage.setItem('jeevan_setu_user', JSON.stringify(user));

        // Sync session cookie with Flask-Login
        var fd = new FormData();
        fd.append('username', usernameVal);
        fd.append('password', passwordVal);
        await fetch('/auth/login', { method: 'POST', body: fd }).catch(function(){});

        var role = (user.role || '').toLowerCase();
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
        console.error('Login error:', err);
      }
    });
  }
})();
</script>
</body></html>"""
    login_html = login_html[:position] + new_script
    with open(login_path, 'w', encoding='utf-8') as file:
        file.write(login_html)
    print('[1/FINISHED] Login.html updated')

# 2. CLEAN NURSE TEMPLATES - Replace hardcoded 'Nurse Priya' markup with 'Nurse'
for nf in [
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_dashboard/Nurse_dashboard.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_settings/Nurse_settings.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_i_o_chart/Nurse_i_o_chart.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_medication_log/Nurse_medication_log.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_nursing_notes/Nurse_nursing_notes.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/nurse_patient_monitoring/nurse_patient_monitoring.html',
    r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/Nurse_enter_vitals/Nurse_enter_vitals.html'
]:
    if os.path.exists(nf):
        with open(nf, 'r', encoding='utf-8') as file:
            ctx = file.read()
        ctx = ctx.replace('Nurse Priya', 'Nurse')
        ctx = ctx.replace('alt="Nurse Priya"', 'alt="Nurse Profile"')
        with open(nf, 'w', encoding='utf-8') as file:
            file.write(ctx)
        print(f'[2/FINISHED] Cleaned {nf}')

# 3. UPDATE NURSE NAVIGATION JS
nurse_nav_path = r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse/nurse_navigation.js'%
with open(nurse_nav_path, 'r', encoding='utf-8') as file:
    n = file.read()

# Update logoutNurse in nurse_navigation.js
new_nlogout = """  window.logutNurse = function () {
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '../../Login/Login.html';
  };"""

if 'window.logoutNurse = function' in n:
    s1 = n.find(Z¯indow.logoutNurse = function')
    s2 = n.find('function auditNursePortalControls', s1)
    if s1 != -1 and s2 != -1:
        n = n[:s1] + new_nlogout + '\n\n  ' + n[s2:d

with open(nurse_nav_path, 'w', encoding='utf-8') as file:
    file.write(n9
print('[3/FINISHED] nurse_navigation.js updated')

# 4. UPDATE DOCTOR SIDEBAR JS
doc_sidebar_path = r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Doctor/doctor_sidebar.js'
with open(doc_sidebar_path, 'r', encoding='utf-8') as file:
    d = file.read()

d = d.replace(
    "const token = localStorage.getItem('token') || sessionStorage.getItem('token') || '';",
    "const token = localStorage.getItem('jeevan_setu_token') || localStorage.getItem('token') || sessionStorage.getItem('token') || '';"
)

d = d.replace(
    "window.handleDoctorLogout = function (event) {
    if (event) event.preventDefault();
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('user_id');
    localStorage.removeItem('userName');
    sessionStorage.clear();
    window.location.href = '../../Login/Login.html';
  };",
    """window.handleDoctorLogout = function (event) {
    if (event) event.preventDefault();
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '../../Login/Login.html';
  };"""
)

with open(doc_sidebar_path, 'w', encoding='utf-8') as file:
    file.write(d)
print('[4/FINISHED] doctor_sidebar.js updated')

print('ALL UPDATES SUCCESSFULLY APPLIED!')
