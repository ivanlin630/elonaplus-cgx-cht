"""Fill glossary.tsv zh column from work/gloss/*.txt (lines: jp<TAB>zh). Reports coverage."""
import sys, csv, glob, collections
sys.stdout.reconfigure(encoding='utf-8')
m = {}
for f in sorted(glob.glob('work/gloss/*.txt')):
    for line in open(f, encoding='utf-8'):
        line = line.rstrip('\n')
        if '\t' in line:
            jp, zh = line.split('\t', 1)
            m[jp.strip()] = zh.strip()
rows = list(csv.reader(open('work/glossary.tsv', encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
hdr, body = rows[0], rows[1:]
miss = collections.Counter(); have = collections.Counter()
for r in body:
    if r[1] in m: r[5] = m[r[1]]
    (have if r[5] else miss)[r[0]] += 1
with open('work/glossary.tsv', 'w', encoding='utf-8', newline='\n') as w:
    for r in [hdr] + body: w.write('\t'.join(r) + '\n')
print('done', dict(have), ' todo', dict(miss))
