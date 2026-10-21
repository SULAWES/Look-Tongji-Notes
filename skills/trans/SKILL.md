---
name: trans
description: "Transcribe a single Tongji Look lecture video to SRT + TXT, optionally download slide snapshots in parallel."
license: MIT
metadata:
  author: WALKERKILLER
  version: "1.1"
---

# Transcribe

Transcribe one lecture video from look.tongji.edu.cn and optionally download slide snapshots.

## When to Use

- User says `/trans` or "transcribe this lecture".
- User provides a lecture URL or course_id + sub_id.

## Default ASR

Use Alibaba Cloud **Fun-ASR** (`ASR_ENGINE=fun-asr`) with `DASHSCOPE_API_KEY` from the skill root `.env`. Setup accepts the key via hidden terminal input; never request it in chat. Audio is uploaded to private temporary storage automatically, without a user OSS bucket. This is a paid cloud service; honor the user's existing upload authorization. If Fun-ASR fails, offer BcutASR as an optional fallback. Before any Bcut upload, ask the user to approve the affected lecture(s) and explain that audio will go to Bilibili. Wait for explicit consent for this fallback and scope; silence or historical general upload consent is not approval. Use a process-scoped `ASR_ENGINE=bcut` only after consent, preserve Fun-ASR checkpoints, and keep `.env` set to Fun-ASR. If declined or unanswered, report the failure and leave the affected work pending. No Doubao or local-model fallback. See the fallback procedure below.

Follow [Fun-ASR configuration and recovery](../../references/fun-asr.md). Reuse saved task IDs and results. A `submitting` or `failed` checkpoint needs inspection; batch retries must not delete it or create a replacement paid task automatically.

## Workflow

1. Resolve lecture with URL or IDs:

```bash
python "<SKILL_DIR>/../../scripts/look_tongji.py" transcribe --lecture-url "<LECTURE_URL>"
```

```bash
python "<SKILL_DIR>/../../scripts/look_tongji.py" transcribe --course-id "<ID>" --sub-id "<ID>"
```

2. Transcribe + download slides in one run:

```bash
python "<SKILL_DIR>/../../scripts/look_tongji.py" transcribe --course-id "<ID>" --sub-id "<ID>" --slide
```

3. The CLI prints real-time progress. Stdout contains result paths.

## Non-Interactive / Batch Usage

When running from an automated pipeline, avoid `input()` prompts with these flags:

| Flag | Description |
|------|-------------|
| `--sub-id` | Specify lecture sub_id directly (skips interactive lecture picker) |
| `--course-id` | Specify course ID directly (skips interactive course selection) |
| `--slide` | Download slides after transcription |
| `--concurrency N` | Slide download concurrency (default 4) |
| `--retries N` | Slide download retries (default 3) |

## manifest.json — Required for Wiki Build

**transcribe does NOT automatically create `manifest.json`.** After transcription, you MUST create it manually so the wiki indexer can find this lecture.

Create `manifest.json` in the session's `原始数据/` directory with this structure:

```json
{
  "course_id": "COURSE_ID",
  "sub_id": "SUB_ID",
  "course_title": "课程名称（真实中文名）",
  "session_title": "YYYY-M-D 第X节",
  "base_name": "COURSE_ID_SUB_ID",
  "artifacts": {
    "srt": "F:\\workspace\\raw\\课程名称\\YYYY-M-D 第X节\\原始数据\\COURSE_ID_SUB_ID.srt",
    "txt": "F:\\workspace\\raw\\课程名称\\...\\COURSE_ID_SUB_ID.txt",
    "notes": "",
    "timeline": "",
    "slides": "F:\\workspace\\raw\\课程名称\\...\\slides\\index.json"
  },
  "duration_seconds": 5580
}
```

**Critical path rules:**
- Use **absolute paths** for all artifact paths (relative paths break on Windows)
- `duration_seconds`: must be ≥ 3600 (1 hour); if < 3600, the lecture is marked不合格 and wiki shows it as 缺失
- If no slides were downloaded, leave `slides` field empty (`""`)
- Fields `notes` and `timeline` are filled by `/note` command later

## Artifacts

- `<course_id>_<sub_id>.srt` — subtitle with timestamps
- `<course_id>_<sub_id>.txt` — plain text transcript
- `<course_id>_<sub_id>.json` — metadata
- `slides/` — slide images + index.json (if --slide)
- **`manifest.json` — MUST create manually after transcription**

## One Session Per Call

For batch transcribing, use `/ralphtrans`.

## Where \`<SKILL_DIR>\` Points

\`<SKILL_DIR>\` is the directory containing this \`SKILL.md\`. Shared scripts (\`look_tongji.py\`, \`timeline_tools.py\`, \`tongji_backend/\`) and references live two levels up in the repository root (\`<SKILL_DIR>/../../scripts/\` and \`<SKILL_DIR>/../../references/\`).
