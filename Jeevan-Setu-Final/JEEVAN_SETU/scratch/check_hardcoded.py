import os

def check_hardcoding(folder, names):
    print(f'=== Checking {folder} ===')
    for root, dirs, files in os.walk(folder):
        for f in files:
            if f.endswith('.html') or f.endswith('.js'):
                fp = os.path.join(root, f)
                with open(fp, 'r', encoding='utf-8') as file:
                    c = file.read()
                    for name in names:
                        if name.lower() in c.lower():
                            cnt = c.lower().count(name.lower())
                            print(f'  {f}: contains {name} ({cnt} times)')

check_hardcoding(r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Nurse', ['nurse_priya', 'nurse_meera', 'nurse_arun', 'priya', 'meera', 'arun'])
check_hardcoding(r'd:/Major_Project/JSF/Jeevan-Setu-Final/Jeevan_setu_frontend/Doctor', ['dr_sharma', 'dr_patel', 'dr_gupta', 'rajesh', 'kavita', 'ananya'])
