"""Story script scene1.hsp (packed into the exe, read at runtime).

  extract : write work/scene_lines.txt  (dialogue/narration lines + actor names)
  build   : write <tree>/scene1.hsp in Shift-JIS using work/mt/sakura.tsv and the glossary

Actor lines look like  {actor_1}<TAB>"name,54"  - only the name is translated,
the portrait number after the comma is kept. Every translated line gets a
trailing space before CR LF: HSP's line reader assumes Shift-JIS and could
otherwise swallow the CR after some Big5 characters.

Usage: python -I scene.py extract | build <tree>
"""
import sys, os, re, csv
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
SRC = os.path.join(ROOT, 'src', 'scene1.hsp')
JP = re.compile('[぀-ヿ一-鿿]')
ACTOR = re.compile(r'^(\{actor_\d+\}\s*")([^",]*)(,.*"\s*)$')


def lines():
    return open(SRC, 'rb').read().decode('cp932').split('\r\n')


def kind(l):
    s = l.lstrip()
    if not JP.search(l) or s.startswith(';'):
        return None
    if s.startswith('{'):
        return 'actor' if ACTOR.match(s) else None
    return 'text'


def extract():
    out, seen = [], set()
    for l in lines():
        k = kind(l)
        if k == 'text':
            t = l.strip()
        elif k == 'actor':
            t = ACTOR.match(l.lstrip()).group(2)
        else:
            continue
        if t and t not in seen:
            seen.add(t); out.append(t)
    open(os.path.join(W, 'scene_lines.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    print(f'{len(out)} unique lines -> work/scene_lines.txt')


def build(tree):
    from sjis_map import sjis_safe
    g = {r[1]: r[5] for r in list(csv.reader(open(os.path.join(W, 'glossary.tsv'), encoding='utf-8'),
                                              delimiter='\t', quoting=csv.QUOTE_NONE))[1:] if r[5]}
    mt = {}
    for line in open(os.path.join(W, 'mt', 'sakura.tsv'), encoding='utf-8'):
        k, _, v = line.rstrip('\n').partition('\t')
        if v: mt[k] = v
    out, lost, n, miss = [], {}, 0, 0
    for l in lines():
        k = kind(l)
        if k == 'text':
            t = l.strip()
            z = mt.get(t)
            if z:
                lead = l[:len(l) - len(l.lstrip())]
                l = lead + z; n += 1
            else:
                miss += 1
        elif k == 'actor':
            m = ACTOR.match(l.lstrip())
            z = g.get(m.group(2)) or mt.get(m.group(2))
            if z:
                l = l[:len(l) - len(l.lstrip())] + m.group(1) + z + m.group(3); n += 1
            else:
                miss += 1
        out.append(sjis_safe(l, lost) if k else l)
    data = '\r\n'.join(out)
    open(os.path.join(tree, 'scene1.hsp'), 'wb').write(data.encode('cp932', errors='replace'))
    print(f'scene1.hsp: translated {n}, untranslated {miss}')
    if lost: print('substituted:', ' '.join(f'{a}->{b}' for a, b in sorted(lost.items())))


if __name__ == '__main__':
    extract() if sys.argv[1] == 'extract' else build(sys.argv[2])
