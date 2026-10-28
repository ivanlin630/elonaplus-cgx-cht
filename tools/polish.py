"""Second pass: a general instruction model (Qwen2.5-14B-Instruct via
llama-server) smooths the machine translations without changing meaning.

Only rows whose translation came from Sakura are polished (glossary terms,
tone tables and hand fixes are left alone). A polished line is accepted only
if markers survive, its length stays within 0.5-2x of the old line, and every
glossary term present before is still present; otherwise the old line stays.
Results append to work/mt/polish.tsv (jp<TAB>zh_old<TAB>zh_new) for resuming.

Usage: python -I polish.py [--url http://127.0.0.1:8080] [--limit N] [--workers 4]
"""
import sys, os, re, csv, json, time, argparse, threading, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding='utf-8'); csv.field_size_limit(10 ** 9)
sys.path.insert(0, os.path.dirname(__file__))
from mt_sakura import ESC, MARK, enc_ph, dec_ph, marks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
OUT = os.path.join(W, 'mt', 'polish.tsv')
SYSTEM = ('你是遊戲中文在地化的潤稿編輯。工作是把已經翻好的中文句子改得通順自然，'
          '使用台灣繁體中文的用字與說法，口吻符合角色與奇幻遊戲氛圍。'
          '絕對不可改變原意，不可增加或刪除資訊，不可解釋。')


def load_glossary():
    g = []
    for r in list(csv.reader(open(os.path.join(W, 'glossary.tsv'), encoding='utf-8'),
                             delimiter='\t', quoting=csv.QUOTE_NONE))[1:]:
        if r[5] and len(r[1]) >= 2 and len(r[5]) >= 2:
            g.append((r[1], r[5]))
    g.sort(key=lambda x: -len(x[0]))
    return g


def ask(url, jp, zh, terms):
    t = '\n'.join(f'{a} → {b}' for a, b in terms) or '（無）'
    user = (f'術語表（必須照用）：\n{t}\n\n日文原文：{jp}\n目前譯文：{zh}\n\n'
            '如果目前譯文已經通順正確，就原樣輸出，不要為了改而改、不要換同義詞。'
            '只修正不通順、語序生硬或明顯譯錯的地方。保留所有 X1、X2 這類代號和 <...> 標籤，'
            '代號位置可以依中文語序調整。只輸出一行譯文。')
    body = {'model': 'qwen', 'temperature': 0.05, 'top_p': 0.5, 'max_tokens': 512,
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]}
    req = urllib.request.Request(url + '/v1/chat/completions', json.dumps(body).encode('utf-8'),
                                 {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)['choices'][0]['message']['content'].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default='http://127.0.0.1:8080')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    import opencc
    s2t = opencc.OpenCC('s2tw')
    gloss = load_glossary()
    sak = {}
    for line in open(os.path.join(W, 'mt', 'sakura.tsv'), encoding='utf-8'):
        k, _, v = line.rstrip('\n').partition('\t')
        if v: sak[k] = v
    rows = list(csv.reader(open(os.path.join(W, 'strings.tsv'), encoding='utf-8'),
                           delimiter='\t', quoting=csv.QUOTE_NONE))[1:]
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding='utf-8'):
            done.add(line.split('\t', 1)[0])
    todo, seen = [], set()
    for r in rows:
        jp, zh = r[5], r[8]
        if not zh or sak.get(jp) != zh or jp in done or jp in seen:
            continue                      # only untouched machine translations
        seen.add(jp); todo.append((jp, zh))
    if a.limit:
        todo = todo[:a.limit]
    print(f'todo {len(todo)} lines ({len(done)} already in {OUT})', flush=True)
    lock = threading.Lock(); out = open(OUT, 'a', encoding='utf-8', newline='\n')
    st = {'changed': 0, 'same': 0, 'rejected': 0}

    def polish_piece(jp, zh):
        terms = [(j, z) for j, z in gloss if j in jp and z in zh][:15]
        new = s2t.convert(dec_ph(ask(a.url, enc_ph(jp), enc_ph(zh), terms)))
        new = new.strip()
        # drop an outer pair of quotes only if the model added it
        for a_, b_ in (('「', '」'), ('"', '"'), ('“', '”')):
            if new.startswith(a_) and new.endswith(b_) and not (zh.startswith(a_) and zh.endswith(b_)):
                new = new[1:-1].strip()
        if '\n' in new or marks(new) != marks(zh):
            return None
        if not (0.5 <= len(new) / max(len(zh), 1) <= 2.0):
            return None
        if any(z not in new for _, z in terms):
            return None
        return new

    def one(item):
        jp, zh = item
        try:
            pj, pz = ESC.split(jp), ESC.split(zh)
            if len(pj) != len(pz):
                res = None
            elif len(pj) == 1:
                res = polish_piece(jp, zh)
            else:
                parts = []
                for i, (x, y) in enumerate(zip(pj, pz)):
                    if i % 2 == 1 or not y.strip():
                        parts.append(y); continue
                    p = polish_piece(x, y)
                    if p is None:
                        parts = None; break
                    parts.append(p)
                res = ''.join(parts) if parts else None
        except Exception:
            res = None
        with lock:
            if res is None:
                st['rejected'] += 1; res = zh
            elif res == zh:
                st['same'] += 1
            else:
                st['changed'] += 1
            out.write(f'{jp}\t{zh}\t{res}\n'); out.flush()

    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        for i, _ in enumerate(ex.map(one, todo), 1):
            if i % 200 == 0 or i == len(todo):
                rate = i / max(time.time() - t0, 1)
                print(f'{i}/{len(todo)} changed {st["changed"]} same {st["same"]} rejected {st["rejected"]}'
                      f'  {rate:.1f}/s  eta {(len(todo) - i) / max(rate, .01) / 60:.0f} min', flush=True)
    out.close(); print('done', st)


if __name__ == '__main__':
    main()
