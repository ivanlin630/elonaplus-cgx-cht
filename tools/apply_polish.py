"""Apply work/mt/polish.tsv: replace a row's zh only if it still equals the
machine translation that was polished (hand fixes made later win)."""
import sys, os, csv
sys.stdout.reconfigure(encoding='utf-8'); csv.field_size_limit(10 ** 9)
W = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work')
EDGE = '「」『』*（）()【】[]〈〉<>…♪'
pol, dropped = {}, 0
for line in open(os.path.join(W, 'mt', 'polish.tsv'), encoding='utf-8'):
    p = line.rstrip('\n').split('\t')
    if len(p) == 3 and p[2] and p[2] != p[1]:
        old, new = p[1], p[2]
        if (old[:1] in EDGE and new[:1] != old[:1]) or (old[-1:] in EDGE and new[-1:] != old[-1:]) \
                or old.count('|') != new.count('|'):
            dropped += 1
            continue                      # the polish lost an opening/closing mark or a separator
        pol[p[0]] = (old, new)
print('polish candidates', len(pol), 'dropped', dropped)
p = os.path.join(W, 'strings.tsv')
rows = list(csv.reader(open(p, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
n = 0
for r in rows[1:]:
    if r[5] in pol and r[8] == pol[r[5]][0]:
        r[8] = pol[r[5]][1]; n += 1
with open(p, 'w', encoding='utf-8', newline='\n') as w:
    for r in rows: w.write('\t'.join(r) + '\n')
print('polished rows applied:', n)
