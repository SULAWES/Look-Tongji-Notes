---
name: setup
description: "Configure Tongji Look credentials, check system dependencies (Python, Node.js, ffmpeg, vision-support, XeLaTeX), and set up the persistent course-wiki workspace."
license: MIT
metadata:
  author: WALKERKILLER
  version: "1.1"
---

# Setup

Configure credentials, dependencies, and workspace for Look Tongji Notes.

## When to Use

- User says `/setup` or asks to configure the skill.
- First-time setup before transcribing lectures.
- User wants to change or migrate the course knowledge-base path.

## Default ASR

Use Alibaba Cloud **Fun-ASR** (`ASR_ENGINE=fun-asr`) with `DASHSCOPE_API_KEY` from the skill root `.env`. Setup accepts the key via hidden terminal input; never request it in chat. Audio is uploaded to private temporary storage automatically, without a user OSS bucket. This is a paid cloud service; honor the user's existing upload authorization. If Fun-ASR fails, offer BcutASR as an optional fallback. Before any Bcut upload, ask the user to approve the affected lecture(s) and explain that audio will go to Bilibili. Wait for explicit consent for this fallback and scope; silence or historical general upload consent is not approval. Use a process-scoped `ASR_ENGINE=bcut` only after consent, preserve Fun-ASR checkpoints, and keep `.env` set to Fun-ASR. If declined or unanswered, report the failure and leave the affected work pending. No Doubao or local-model fallback. See the fallback procedure below.

Follow [Fun-ASR configuration and recovery](../../references/fun-asr.md). Reuse saved task IDs and results. A `submitting` or `failed` checkpoint needs inspection; batch retries must not delete it or create a replacement paid task automatically.

## Workflow

1. Run setup:

```bash
python "<SKILL_DIR>/../../scripts/look_tongji.py" setup
```

2. Non-interactive workspace options:

```bash
python "<SKILL_DIR>/../../scripts/look_tongji.py" setup \
  --workspace-root "<COURSE_WIKI_ROOT>" \
  --owner-name "<OWNER_NAME>" \
  --site-name "<OWNER_NAME>的课程知识库"
```

3. The CLI checks: Python deps (requests, playwright, python-dotenv, markdown, markitdown), ffmpeg, Node.js, vision-support config, and optionally XeLaTeX.

4. **Vision Support setup:** If `vision-support/config.json` does not exist, the CLI prints the init command. The embedded vision-support is at `<SKILL_DIR>/../../vision-support/`. Help the user configure a vision provider (OpenAI, Google, Anthropic, deepseek, dashscope, zhipuai, ollama, or custom).

5. **Verify vision-support:** After configuration, test with:
   ```bash
   node "<SKILL_DIR>/../../vision-support/scripts/vision.mjs" "<SKILL_DIR>/../../komari.jpg"
   ```
   The agent should correctly identify image content (should mention "red-haired girl" or equivalent).

6. Never ask for passwords in chat. Use interactive terminal input or environment variables.

## Where `<SKILL_DIR>` Points

`<SKILL_DIR>` is the directory containing this `SKILL.md`. Shared scripts (`look_tongji.py`, `timeline_tools.py`, `tongji_backend/`) and references live two levels up in the repository root (`<SKILL_DIR>/../../scripts/` and `<SKILL_DIR>/../../references/`).
