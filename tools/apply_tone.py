"""Fill zh for the speech-tone table literals in text.hsp (see tone_map.py)."""
import sys, os, re, csv
sys.stdout.reconfigure(encoding='utf-8'); csv.field_size_limit(10 ** 9)
sys.path.insert(0, os.path.dirname(__file__))
from tone_map import tone_zh
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, 'src', 'text.hsp'), 'rb').read().decode('cp932').splitlines()
func_at, cur = [], None
for l in src:
    m = re.match(r'#defcfunc (_\w+)', l)
    if m: cur = m.group(1)
    func_at.append(cur)
p = os.path.join(ROOT, 'work', 'strings.tsv')
rows = list(csv.reader(open(p, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
n = miss = 0
for r in rows[1:]:
    if r[1] == 'text.hsp' and r[3] == 'lit' and r[4] == 'locvar__yoro__tone':
        z = tone_zh(func_at[int(r[2]) - 1], r[5])
        if z is None:
            miss += 1; print('  no mapping:', func_at[int(r[2]) - 1], r[5]); continue
        r[8] = z if z else '∅'; n += 1
with open(p, 'w', encoding='utf-8', newline='\n') as w:
    for r in rows: w.write('\t'.join(r) + '\n')
print(f'tone rows filled {n}, unmapped {miss}')
