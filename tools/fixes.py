"""Hand corrections applied after machine translation (re-run safe).
Each rule: (jp text, file or None, ctx prefix or None, zh)."""
import sys, os, csv
sys.stdout.reconfigure(encoding='utf-8'); csv.field_size_limit(10 ** 9)
RULES = [
    ('ああ', None, 'chatList', '好的。'),
    ('ああ', 'text.hsp', 'stryes', '好的。'),
    ('する', 'config.hsp', None, '是'),
    ('しない', 'config.hsp', None, '否'),
    ('する', 'chat.hsp', 'chatList', '要'),
    ('しない', 'chat.hsp', 'chatList', '不要'),
    ('{0}がある。', None, None, '這裡有{0}。'),
    ('と', None, None, '和'),
    ('調合', 'text.hsp', 'invtitle', '調合'),
]
p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'strings.tsv')
rows = list(csv.reader(open(p, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
n = 0
for r in rows[1:]:
    for jp, f, ctx, zh in RULES:
        if r[5].strip() == jp and (f is None or r[1] == f) and (ctx is None or r[4].startswith(ctx)):
            r[8] = zh; n += 1; break
with open(p, 'w', encoding='utf-8', newline='\n') as w:
    for r in rows: w.write('\t'.join(r) + '\n')
print('hand fixes applied to', n, 'rows')
