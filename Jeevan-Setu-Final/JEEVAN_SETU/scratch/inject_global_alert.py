import os
import glob

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Jeevan_setu_frontend'))
doc_files = glob.glob(os.path.join(frontend_dir, 'Doctor', '**', '*.html'), recursive=True)
nurse_files = glob.glob(os.path.join(frontend_dir, 'Nurse', '**', '*.html'), recursive=True)

script_tag = '<script src="../global_alert_manager.js"></script>'
updated = 0

for f in doc_files + nurse_files:
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()
    if 'global_alert_manager.js' not in content:
        if '</body>' in content:
            new_content = content.replace('</body>', f'  {script_tag}\n</body>')
        else:
            new_content = content + f'\n{script_tag}\n'
        with open(f, 'w', encoding='utf-8') as fp:
            fp.write(new_content)
        updated += 1
        print(f"Added script to: {os.path.basename(os.path.dirname(f))}/{os.path.basename(f)}")
    else:
        print(f"Already present in: {os.path.basename(os.path.dirname(f))}/{os.path.basename(f)}")

print(f"\nCompleted: {updated} files updated, total checked: {len(doc_files) + len(nurse_files)}")
