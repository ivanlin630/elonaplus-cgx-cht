"""Machine-translate untranslated rows of strings.tsv with a local SakuraLLM
served by llama.cpp (llama-server, OpenAI-compatible /v1/chat/completions).

- unique Japanese templates only (rows sharing text are translated once)
- per-line glossary from glossary.tsv (Sakura "GPT dict" prompt)
- batches of lines; a batch whose line count differs is retried line by line
- markers ({0}, <tags>, \\n escapes) must survive or the line is retried, then left blank
- Sakura writes Simplified Chinese -> OpenCC s2tw, then glossary terms are re-imposed
- results append to work/mt/sakura.tsv (jp<TAB>zh) so the run can resume

Usage: python -I mt_sakura.py [--url http://127.0.0.1:8080] [--limit N] [--files a.hsp,b.hsp]
"""
import sys, os, re, csv, json, time, argparse, threading, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')
csv.field_size_limit(10 ** 9)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
OUT = os.path.join(W, 'mt', 'sakura.tsv')

SYSTEM = ('你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，'
          '并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。')
# runs of backslash escapes as they appear in the TSV (HSP "\n" is stored as "\\n")
ESC = re.compile(r'((?:\\+[ntr"]?)+)')
MARK = re.compile(r'\{\d+\}|<[a-z0-9_]+>|\\[nt"\\]|%[a-zA-Z]')
JP = re.compile('[぀-ヿ一-鿿]')


def load_glossary():
    import opencc
    t2s = opencc.OpenCC('t2s')
    g = []
    for r in list(csv.reader(open(os.path.join(W, 'glossary.tsv'), encoding='utf-8'),
                             delimiter='\t', quoting=csv.QUOTE_NONE))[1:]:
        if r[5] and len(r[1]) >= 2:
            g.append((r[1], t2s.convert(r[5]), r[5]))
    g.sort(key=lambda x: -len(x[0]))
    return g


def terms_for(text, gloss, cap=20):
    hit, used = [], text
    for jp, zs, zt in gloss:
        if jp in used:
            hit.append((jp, zs, zt))
            used = used.replace(jp, '\0')
            if len(hit) >= cap:
                break
    return hit


def ask(url, text, terms, temperature=0.1):
    if terms:
        d = '\n'.join(f'{a}->{b}' for a, b, _ in terms)
        user = '根据以下术语表（可以为空）：\n' + d + '\n将下面的日文文本根据对应关系和备注翻译成中文：' + text
    else:
        user = '将下面的日文文本翻译成中文：' + text
    body = {'model': 'sakura', 'temperature': temperature, 'top_p': 0.3, 'max_tokens': 1024,
            'frequency_penalty': 0.05,
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]}
    req = urllib.request.Request(url + '/v1/chat/completions', json.dumps(body).encode('utf-8'),
                                 {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)['choices'][0]['message']['content']


def marks(s):
    return sorted(MARK.findall(s))


# Sakura drops "{0}" but keeps name-like tokens: {0} -> X1, {1} -> X2 ...
def enc_ph(s):
    return re.sub(r'\{(\d+)\}', lambda m: 'X%d' % (int(m.group(1)) + 1), s)


def dec_ph(s):
    return re.sub(r'[XＸ](\d+)', lambda m: '{%d}' % (int(m.group(1)) - 1), s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default='http://127.0.0.1:8080')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--files', default='')
    ap.add_argument('--batch', type=int, default=8)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--lines', default='', help='translate these lines (one per line) instead of strings.tsv')
    a = ap.parse_args()

    import opencc
    s2t = opencc.OpenCC('s2tw')
    gloss = load_glossary()
    rows = list(csv.reader(open(os.path.join(W, 'strings.tsv'), encoding='utf-8'),
                           delimiter='\t', quoting=csv.QUOTE_NONE))[1:]
    files = set(a.files.split(',')) if a.files else None
    done = {}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if os.path.exists(OUT):
        for line in open(OUT, encoding='utf-8'):
            k, _, v = line.rstrip('\n').partition('\t')
            if v:                       # blank = failed earlier: try again
                done[k] = v
    todo, seen = [], set()
    if a.lines:
        rows = [[''] * 5 + [l.rstrip('\n'), '', '[]', ''] for l in open(a.lines, encoding='utf-8')]
    for r in rows:
        jp = r[5]
        if r[8] or not JP.search(jp) or jp in done or jp in seen:
            continue
        if files and r[1] not in files:
            continue
        seen.add(jp)
        todo.append(jp)
    if a.limit:
        todo = todo[:a.limit]
    print(f'todo {len(todo)} unique lines ({len(done)} already in {OUT})', flush=True)

    lock = threading.Lock()
    out = open(OUT, 'a', encoding='utf-8', newline='\n')
    stats = {'ok': 0, 'blank': 0, 'retry': 0}

    def finish(jp, zh_s):
        zh = s2t.convert(zh_s) if zh_s else ''
        for src, zs, zt in terms_for(jp, gloss):         # re-impose glossary spelling
            conv = s2t.convert(zs)
            if conv != zt and conv in zh:
                zh = zh.replace(conv, zt)
        with lock:
            out.write(jp + '\t' + zh + '\n')
            out.flush()
            stats['ok' if zh else 'blank'] += 1

    def one(jp):
        # control codes (\t \n \" as stored in the TSV) never go to the model:
        # translate the text between them and glue the codes back in place
        parts = ESC.split(jp)
        if len(parts) > 1:
            out_parts = []
            for i, p in enumerate(parts):
                if i % 2 == 1 or not JP.search(p):
                    out_parts.append(p); continue
                z = ''
                for temp in (0.1, 0.4):
                    try:
                        z = dec_ph(ask(a.url, enc_ph(p), terms_for(p, gloss), temp).strip())
                    except Exception:
                        time.sleep(2); continue
                    if marks(z) == marks(p) and '\n' not in z:
                        break
                    stats['retry'] += 1; z = ''
                if not z:
                    return finish(jp, '')
                out_parts.append(z)
            return finish(jp, ''.join(out_parts))
        for temp in (0.1, 0.4):
            try:
                zh = dec_ph(ask(a.url, enc_ph(jp), terms_for(jp, gloss), temp).strip())
            except Exception as ex:
                time.sleep(2)
                continue
            if marks(zh) == marks(jp) and '\n' not in zh:
                return finish(jp, zh)
            stats['retry'] += 1
        finish(jp, '')

    def batch(lines):
        if len(lines) > 1 and not any('\\n' in x for x in lines):
            text = '\n'.join(lines)
            terms = terms_for(text, gloss)
            try:
                res = dec_ph(ask(a.url, enc_ph(text), terms).strip()).split('\n')
            except Exception:
                res = []
            if len(res) == len(lines):
                bad = []
                for jp, zh in zip(lines, res):
                    zh = zh.strip()
                    if zh and marks(zh) == marks(jp):
                        finish(jp, zh)
                    else:
                        bad.append(jp)
                for jp in bad:
                    one(jp)
                return
        for jp in lines:
            one(jp)

    groups = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        for i, _ in enumerate(ex.map(batch, groups), 1):
            if i % 20 == 0 or i == len(groups):
                n = stats['ok'] + stats['blank']
                rate = n / max(time.time() - t0, 1)
                eta = (len(todo) - n) / max(rate, 0.01) / 60
                print(f'{n}/{len(todo)}  ok {stats["ok"]} blank {stats["blank"]} retry {stats["retry"]}'
                      f'  {rate:.1f} lines/s  eta {eta:.0f} min', flush=True)
    out.close()
    print('done', stats)


if __name__ == '__main__':
    main()
