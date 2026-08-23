#!/usr/bin/env bash
set -euo pipefail

read -rsp "Paste your OpenAI API key (hidden): " OPENAI_API_KEY
echo

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"; unset OPENAI_API_KEY' EXIT

http_code=$(curl -sS -o "$tmpfile" -w "%{http_code}" \
  https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY")

echo "HTTP $http_code"

if [ "$http_code" != "200" ]; then
  cat "$tmpfile"
  exit 1
fi

python3 - "$tmpfile" <<'PY'
import json, sys
p = sys.argv[1]
with open(p) as f:
    data = json.load(f)
ids = sorted(x.get('id','') for x in data.get('data',[]) if x.get('id'))
print(f"Total visible models: {len(ids)}")
print("\nRelevant visible models:")
needles = ('daybreak','cyber','5.6','sol','terra','luna')
rel = [m for m in ids if any(n in m.lower() for n in needles)]
if rel:
    for m in rel:
        print(m)
else:
    print('(none)')
print("\nAll visible GPT models:")
for m in ids:
    if m.lower().startswith('gpt'):
        print(m)
PY
