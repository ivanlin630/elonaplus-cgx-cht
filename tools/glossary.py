"""Build glossary.tsv (proper nouns) from strings.tsv, grouped by category."""
import sys, csv, re, collections
sys.stdout.reconfigure(encoding='utf-8'); csv.field_size_limit(10 ** 9)
CATS = [  # (category, ctx regex)
    ('怪物', r'^(cdatan\(CDATAN_NAME,rc\)|evname|evold|cardrefn|mon|hito)$'),
    ('物品', r'^(ioriginalnameref|iknownnameref|ialphanameref|fishdatan|rfnameorg)\(|^locvar_itemowner_s$'),
    ('材料', r'^(matname|mtname)\('),
    ('技能', r'^(skillname|buffname|rpdatan)\(|^traitrefn2$'),
    ('地名', r'^mdatan\('),
    ('種族職業', r'^(racename|classname)$'),
    ('稱號', r'^rankn\('),
]
rows = list(csv.reader(open(sys.argv[1], encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))[1:]
seen = collections.OrderedDict()
for r in rows:
    if r[7] != '[]':
        continue
    for cat, rx in CATS:
        if re.search(rx, r[4]):
            jp = r[5].strip()
            if jp and len(jp) <= 30:
                k = (cat, jp)
                if k not in seen:
                    seen[k] = [cat, jp, r[6], 0, r[1] + ':' + r[2]]
                seen[k][3] += 1
            break
with open(sys.argv[2], 'w', encoding='utf-8', newline='\n') as w:
    w.write('category\tjp\ten\tcount\twhere\tzh\n')
    for v in seen.values():
        w.write('\t'.join(map(str, v)) + '\t\n')
print(collections.Counter(v[0] for v in seen.values()), 'total', len(seen))
