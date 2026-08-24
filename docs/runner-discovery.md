# Delayed workflow run discovery

GitHub may accept a `workflow_dispatch` request before the new run becomes visible to `gh run list`.

DPSR persists the external job immediately. If the initial dispatch cannot resolve a run ID, `job refresh` performs bounded discovery using the recorded repository, workflow, branch, and dispatch timestamp. Runs older than the dispatch window or already claimed by another DPSR job are ignored.
