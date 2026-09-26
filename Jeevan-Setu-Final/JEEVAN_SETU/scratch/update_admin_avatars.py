import glob
import re

files = glob.glob(r'd:\Major_Project\JSA-1\Jeevan_setu_frontend\Admin\**\*.html', recursive=True)
count = 0
for f in files:
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()
    updated = re.sub(r'https://lh3\.googleusercontent\.com/aida-public/AB6AXuC[^\"]+', '../admin_avatar.jpg', content)
    if updated != content:
        with open(f, 'w', encoding='utf-8') as fp:
            fp.write(updated)
        count += 1
        print('Updated:', f)

print(f'Done! Updated {count} files.')
