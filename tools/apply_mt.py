"""Fill empty zh cells in strings.tsv from work/mt/sakura.tsv (jp<TAB>zh)."""
import sys, os, csv
sys.stdout.reconfigure(encoding='utf-8'); csv.field_size_limit(10 ** 9)
W = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work')
mt = {}
for line in open(os.path.join(W, 'mt', 'sakura.tsv'), encoding='utf-8'):
    k, _, v = line.rstrip('\n').partition('\t')
    if v:
        mt[k] = v
rows = list(csv.reader(open(os.path.join(W, 'strings.tsv'), encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
n = 0
for r in rows[1:]:
    if not r[8] and r[5] in mt:
        r[8] = mt[r[5]]; n += 1
with open(os.path.join(W, 'strings.tsv'), 'w', encoding='utf-8', newline='\n') as w:
    for r in rows: w.write('\t'.join(r) + '\n')
print(f'filled {n}; translated {sum(1 for r in rows[1:] if r[8])}/{len(rows) - 1}')
