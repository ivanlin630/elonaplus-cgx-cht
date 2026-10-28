"""Fill zh in strings.tsv for rows whose whole jp text is a glossary term."""
import sys, csv
sys.stdout.reconfigure(encoding='utf-8'); csv.field_size_limit(10 ** 9)
G = {g[1]: g[5] for g in list(csv.reader(open('work/glossary.tsv', encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))[1:] if g[5]}
rows = list(csv.reader(open('work/strings.tsv', encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
n = 0
for r in rows[1:]:
    if not r[8] and r[7] == '[]' and r[5].strip() in G:
        lead = r[5][:len(r[5]) - len(r[5].lstrip())]; trail = r[5][len(r[5].rstrip()):]
        r[8] = lead + G[r[5].strip()] + trail; n += 1
with open('work/strings.tsv', 'w', encoding='utf-8', newline='\n') as w:
    for r in rows: w.write('\t'.join(r) + '\n')
done = sum(1 for r in rows[1:] if r[8])
print(f'filled {n}; total translated rows {done}/{len(rows)-1}')
