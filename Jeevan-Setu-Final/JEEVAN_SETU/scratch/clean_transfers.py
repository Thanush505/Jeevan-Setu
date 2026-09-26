import glob
import re
import os

files = glob.glob(r'd:\Major_Project\JSA-1\Jeevan_setu_frontend\Admin\**\*.html', recursive=True)
pattern = re.compile(r'\s*<li[^>]*>\s*<a[^>]*href=[\'"][^\'"]*Admin_transfers_management[^\'"]*[\'"][^>]*>.*?</li>', re.DOTALL | re.IGNORECASE)

updated = []
for f in files:
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()
    if 'Admin_transfers_management' in content:
        new_content = pattern.sub('', content)
        new_content = re.sub(r'<a[^>]*href=[\'"][^\'"]*Admin_transfers_management[^\'"]*[\'"][^>]*>.*?</a>', '', new_content, flags=re.DOTALL | re.IGNORECASE)
        with open(f, 'w', encoding='utf-8') as fp:
            fp.write(new_content)
        updated.append(f)

print(f"Cleaned {len(updated)} files:")
for u in updated:
    print("-", u)
