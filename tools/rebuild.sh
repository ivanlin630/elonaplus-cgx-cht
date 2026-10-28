#!/usr/bin/env bash
# Rebuild the translated game from src/ and the translation tables.
#   bash tools/rebuild.sh [game data dir]
# Steps: extract -> fill (glossary, MT, polish, tone, fixes) -> report what is still
# untranslated -> write the zh table + patched source -> story script -> data files
# -> structure check -> compile (32-bit PowerShell).
# Machine translation is NOT run here; run tools/mt_sakura.py first if the report
# lists untranslated lines (it only sends the empty ones).
set -euo pipefail
cd "$(dirname "$0")/.."
DATA="${1:-}"
py() { python -I "$@"; }

py tools/extract.py src work
py tools/apply_gloss.py
py tools/apply_mt.py
[ -f work/mt/polish.tsv ] && py tools/apply_polish.py
py tools/apply_tone.py
py tools/fixes.py
py tools/glossary.py work/strings.tsv work/glossary.new.tsv >/dev/null || true
py - <<'EOF'
import csv; csv.field_size_limit(10**9)
R = list(csv.reader(open('work/strings.tsv', encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))[1:]
todo = sum(1 for r in R if not r[8])
print(f'untranslated rows: {todo} / {len(R)}  (run tools/mt_sakura.py to fill them)')
EOF

py tools/inject.py src work/strings.tsv work/src_tbl --table work/zh_text
py tools/patch_src.py work/src_tbl
py tools/scene.py extract
py tools/scene.py build work/src_tbl
py tools/check_structure.py src work/src_tbl
if [ -n "$DATA" ]; then
  py tools/data_tr.py collect "$DATA"
  py tools/data_tr.py build "$DATA" work/data_zh
fi

printf 'work\\src_tbl\n' > build-src.txt
/c/Windows/SysWOW64/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "$PWD/build.ps1")"
echo
echo "copy to the game folder:"
echo "  work/src_tbl/elonapluscgx.exe  ->  <game>/"
echo "  work/zh_text.bin, work/zh_text.idx  ->  <game>/data/"
[ -n "$DATA" ] && echo "  work/data_zh/*  ->  <game>/data/"
