#!/usr/bin/env bash
set -u

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  printf 'Paste your OpenAI API key (hidden): '
  IFS= read -r -s OPENAI_API_KEY
  printf '\n'
fi

if [[ -z "${OPENAI_API_KEY}" ]]; then
  echo 'No API key entered.'
  exit 1
fi

export OPENAI_API_KEY

models=(
  "gpt-daybreak-blue"
  "gpt-5.6-sol"
  "gpt-daybreak-red"
  "gpt-5.6-cyber"
  "gpt-daybreak-red-latest"
)

echo
echo 'Testing OpenAI Responses API with this project key...'
echo 'The key is kept only in this shell process and is not written to disk.'
echo

for model in "${models[@]}"; do
  safe_name=$(printf '%s' "$model" | tr '/:' '__')
  outfile="/tmp/daybreak-${safe_name}.json"

  payload=$(printf '{"model":"%s","input":"Reply exactly: ACCESS_OK","max_output_tokens":16}' "$model")

  http_code=$(curl -sS \
    -o "$outfile" \
    -w '%{http_code}' \
    https://api.openai.com/v1/responses \
    -H "Authorization: Bearer ${OPENAI_API_KEY}" \
    -H 'Content-Type: application/json' \
    -d "$payload" || true)

  printf '%-28s HTTP %s  ' "$model" "$http_code"

  MODEL_FILE="$outfile" node <<'NODE'
const fs = require('fs');
const p = process.env.MODEL_FILE;
let j;
try { j = JSON.parse(fs.readFileSync(p, 'utf8')); }
catch { console.log('Could not parse response'); process.exit(0); }

if (j.error) {
  const code = j.error.code ? ` [${j.error.code}]` : '';
  console.log(`${j.error.message || j.error.type || 'API error'}${code}`);
  process.exit(0);
}

let text = '';
for (const out of (j.output || [])) {
  for (const c of (out.content || [])) {
    if (typeof c.text === 'string') text += c.text;
  }
}
console.log(text ? `SUCCESS: ${text.trim()}` : 'SUCCESS');
NODE

done

unset OPENAI_API_KEY
echo
echo 'Done. API key removed from this shell variable.'
