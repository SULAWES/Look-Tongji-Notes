---
name: ralphtrans
description: "Batch transcribe ALL playable lectures for a course in a persistent loop. Uses a JSON state file for checkpoint/resume. Runs until every lecture is transcribed or marked failed."
license: MIT
metadata:
  author: WALKERKILLER
  version: "1.1"
---

# Ralph Batch Transcribe

Batch transcribe all playable lectures for a course with checkpoint/resume.

## When to Use

- User says `/ralphtrans` or "batch transcribe this course".
- User wants to transcribe an entire course in one go.

## Default ASR

Use Alibaba Cloud **Fun-ASR** (`ASR_ENGINE=fun-asr`) with `DASHSCOPE_API_KEY` from the skill root `.env`. Setup accepts the key via hidden terminal input; never request it in chat. Audio is uploaded to private temporary storage automatically, without a user OSS bucket. This is a paid cloud service; honor the user's existing upload authorization. Never silently fall back to another provider or local model.

Follow [Fun-ASR configuration and recovery](../../references/fun-asr.md). Reuse saved task IDs and results. A `submitting` or `failed` checkpoint needs inspection; batch retries must not delete it or create a replacement paid task automatically.

## Workflow

1. Start batch transcription:

```bash
python "<SKILL_DIR>/../../scripts/look_tongji.py" batch-transcribe --course-id "<ID>"
```

2. The CLI:
   - Loads all playable lectures for the course.
   - Creates/reads `batch_state.json` in the workspace to track progress.
   - Transcribes lectures one by one, updating state after each.
   - Retries failed lectures up to `--max-retries` times.
   - Prints a summary when all lectures are done or failed.

3. **Interrupt & Resume:**
   - Press Ctrl+C to safely stop. State is saved.
   - Re-run the same command to resume from pending lectures.

## State File

`batch_state.json` structure:
```json
{
  "course_id": "xxx",
  "started_at": "ISO8601",
  "updated_at": "ISO8601",
  "lectures": [
    {"sub_id": "xxx", "sub_title": "xxx", "status": "pending|done|failed", "attempts": 0, "error": null}
  ]
}
```

## After Completion

- Run `/note` for each transcribed lecture to generate study notes.
- Run `/wiki` to rebuild and serve the course site.

## Where `<SKILL_DIR>` Points

`<SKILL_DIR>` is the directory containing this `SKILL.md`. Shared scripts (`look_tongji.py`, `timeline_tools.py`, `tongji_backend/`) and references live two levels up in the repository root (`<SKILL_DIR>/../../scripts/` and `<SKILL_DIR>/../../references/`).
