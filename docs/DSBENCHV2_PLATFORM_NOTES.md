# DSBenchV2 platform constraints used by this project

Offline notes distilled on 2026-08-15 from the authenticated
`DSBenchV2平台使用教程`. These notes paraphrase the operational requirements;
they are not a copy of the tutorial or a source for task code.

## Construction and snapshot

- Build an original agent task with deterministic code verification.
- Upload the workspace and install its toolchain inside a SnapCode collection
  container.
- After uploading files, send a harmless confirmation message in Claude Code
  so the environment snapshot is recorded. Install dependencies and trigger a
  second snapshot before sending the task prompt.
- The rollout sees only the selected prompt and the snapshot immediately before
  it. The prompt therefore must be standalone and cannot refer to prior turns.
- Do not require an LLM API or another unavailable internal API.
- Collection containers save files, dependencies, and state, but not memory.
  They expire after roughly two hours; a resumed container needs a new session
  for new snapshots.

## Code Grade contract

- Paste one Python script named `test_by_code.py` into the Code Grade editor.
- At grading time it can read the rollout workspace at `/workspace/` and
  read-only attachments at `/test_files/`.
- Extra grading attachments are uploaded separately and each file must be
  smaller than 1 MB.
- The script must write `/eval/code_result.json` containing exactly:

```json
{"resolved": true, "score": 1.0, "reason": "all tests passed"}
```

- `score` is continuous in `[0, 1]`; `resolved` is the important pass threshold
  used to compare rollout pass rates and does not have to mean `score == 1`.
- Code Grade is preferred over an LLM judge. Grading may be changed and rerun
  without rerunning a rollout.
- Rollout and grading are separate CIS-container executions.

## Rollout and submission

- Models currently run in a Claude Code-style framework with no conversation
  context. Network access is optional and discouraged.
- Recommended batch size is 3-6 per model.
- Every new rollout must be graded before submission and every model must have
  at least one batch of size 3 or more.
- Submission metadata includes a unique English task ID, summary, type,
  technology stack, capability tags, and optional author notes.

## Mapping to this repository

- `dist/workspace.zip` is expanded/uploaded into `/workspace` before the
  snapshot.
- `dist/task_prompt.md` is the standalone rollout prompt.
- `dist/test_by_code.py` is pasted into Code Grade.
- All files in `dist/test_files/` are uploaded as read-only grading
  attachments; the package command rejects files at or above 1 MB.

