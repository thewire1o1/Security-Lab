#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY="${REPOSITORY:-thewire1o1/Security-Lab}"
ISSUE_NUMBER="${1:-${ISSUE_NUMBER:-}}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-45}"
MARKER='<!-- apotheon-deployment-feedback -->'

if [[ -z "${ISSUE_NUMBER}" ]]; then
  printf 'usage: %s ISSUE_NUMBER\n' "$0" >&2
  exit 2
fi

for command in gh jq; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'missing required command: %s\n' "$command" >&2
    exit 3
  fi
done

gh auth status >/dev/null 2>&1 || {
  printf '%s\n' 'GitHub CLI is not authenticated.' >&2
  exit 4
}

issue_json="$(gh api "repos/${REPOSITORY}/issues/${ISSUE_NUMBER}")"
issue_title="$(jq -r '.title' <<<"$issue_json")"
issue_created="$(jq -r '.created_at' <<<"$issue_json")"

find_feedback_comment() {
  gh api "repos/${REPOSITORY}/issues/${ISSUE_NUMBER}/comments?per_page=100" \
    | jq -r --arg marker "$MARKER" '[.[] | select(.body | contains($marker))] | last | .id // empty'
}

publish_feedback() {
  local body="$1"
  local comment_id
  comment_id="$(find_feedback_comment)"

  if [[ -n "$comment_id" ]]; then
    gh api --method PATCH "repos/${REPOSITORY}/issues/comments/${comment_id}" \
      -f body="$body" >/dev/null
  else
    gh api --method POST "repos/${REPOSITORY}/issues/${ISSUE_NUMBER}/comments" \
      -f body="$body" >/dev/null
  fi
}

extract_links() {
  local comments="$1"
  local console codespace mcp

  console="$(jq -r '[.[].body | scan("https://[A-Za-z0-9-]+-8765\\.app\\.github\\.dev")] | last // empty' <<<"$comments")"
  codespace="$(jq -r '[.[].body | scan("https://[A-Za-z0-9-]+\\.github\\.dev")] | last // empty' <<<"$comments")"
  mcp="$(jq -r '[.[].body | scan("https://[A-Za-z0-9-]+-8766\\.app\\.github\\.dev/mcp")] | last // empty' <<<"$comments")"

  printf '%s\n%s\n%s\n' "$console" "$codespace" "$mcp"
}

while :; do
  now="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  runs_json="$(gh api "repos/${REPOSITORY}/actions/workflows/wake-codespace.yml/runs?event=issues&per_page=50")"
  run_json="$(jq -c \
    --arg title "$issue_title" \
    --arg created "$issue_created" \
    '[.workflow_runs[] | select(.display_title == $title and .created_at >= $created)] | sort_by(.created_at) | last // empty' \
    <<<"$runs_json")"

  run_status='waiting'
  run_conclusion=''
  run_id=''
  head_sha=''
  active_step='Waiting for Wake Controller run'

  if [[ -n "$run_json" ]]; then
    run_id="$(jq -r '.id' <<<"$run_json")"
    run_status="$(jq -r '.status // "unknown"' <<<"$run_json")"
    run_conclusion="$(jq -r '.conclusion // empty' <<<"$run_json")"
    head_sha="$(jq -r '.head_sha // empty' <<<"$run_json")"

    jobs_json="$(gh api "repos/${REPOSITORY}/actions/runs/${run_id}/jobs?per_page=100")"
    active_step="$(jq -r '[.jobs[].steps[]? | select(.status == "in_progress") | .name] | first // empty' <<<"$jobs_json")"

    if [[ -z "$active_step" ]]; then
      if [[ "$run_status" == 'completed' && "$run_conclusion" == 'success' ]]; then
        active_step='Wake Controller completed successfully'
      elif [[ "$run_status" == 'completed' ]]; then
        active_step="Wake Controller completed: ${run_conclusion:-unknown}"
      else
        active_step="Workflow status: ${run_status}"
      fi
    fi
  fi

  comments_json="$(gh api "repos/${REPOSITORY}/issues/${ISSUE_NUMBER}/comments?per_page=100")"
  mapfile -t links < <(extract_links "$comments_json")
  console_url="${links[0]:-}"
  codespace_url="${links[1]:-}"
  mcp_url="${links[2]:-}"

  body=$(cat <<EOF
${MARKER}
### APOTHEON deployment feedback

Updated: \`${now}\`  
Workflow: \`${run_status}${run_conclusion:+ / ${run_conclusion}}\`  
Step: \`${active_step}\`  
Head: \`${head_sha:-pending}\`

APOTHEON ONE console: ${console_url:-pending}  
Codespace: ${codespace_url:-pending}  
MCP: ${mcp_url:-pending}

Watcher interval: \`${INTERVAL_SECONDS}s\`
EOF
)

  publish_feedback "$body"
  printf '[%s] %s | %s\n' "$now" "$run_status" "$active_step"

  if [[ "$run_status" == 'completed' ]]; then
    if [[ "$run_conclusion" != 'success' ]]; then
      exit 1
    fi
    if [[ -n "$console_url" && -n "$codespace_url" && -n "$mcp_url" ]]; then
      exit 0
    fi
  fi

  sleep "$INTERVAL_SECONDS"
done
