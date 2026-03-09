import re, subprocess

with open('templates/courses/video_detail.html', 'r', encoding='utf-8') as f:
    text = f.read()

scripts = re.findall(r'<script.*?>([\s\S]*?)</script>', text)
for i, code in enumerate(scripts):
    code = re.sub(r'\{%[^%]*%\}', '/* django */', code)
    code = re.sub(r'\{\{[^\}]*\}\}', '\"django\"', code)
    with open('tmp_script.js', 'w', encoding='utf-8') as js:
        js.write(code)
    res = subprocess.run(['node', '-c', 'tmp_script.js'], capture_output=True, text=True)
    if res.returncode != 0:
        print(f'Syntax error in script tag {i}:', res.stderr)
    else:

        print(f'Script tag {i} OK')
