# Security notes

## Credentials

- Credentials are stored in `<SKILL_DIR>/.env`.
- Do not commit `.env` to git. This skill includes `.gitignore` for it.
- Avoid pasting passwords into chat. Prefer interactive terminal input.

## Auth cache

- `<SKILL_DIR>/state/auth_session.json` may contain a JWT token.
- Treat JWT tokens like passwords. Keep the `state/` folder private.

## Output artifacts

- By default, the CLI writes transcripts, subtitles, slides, imported materials, and the generated site to the configured course wiki workspace.
- The workspace config is stored outside the skill folder so skill updates do not overwrite it.
- `LOOK_TONGJI_CONFIG_PATH` can override the config file location.
- `LOOK_TONGJI_WORKSPACE_ROOT` can override the workspace root for non-interactive runs.
- Transcripts may include personal information. Be careful before sharing them.
- Supplementary materials are copied into `raw/<course>/<session>/原始数据/materials/`.
  Only import files you are allowed to process locally.
- Do not commit `.env`, `state/`, JWT cache files, or private course materials to a public repository.

## Fun-ASR

`DASHSCOPE_API_KEY` belongs only in the ignored `.env` or environment. Never print it, pass it in chat, or include it in published artifacts. The default cloud transcription uploads audio directly to Alibaba private temporary storage (48 hours); honor existing user authorization. Keep `state/fun-asr/` private: it includes raw transcripts, task IDs and potentially signed resource URLs. Do not publish the cache or copy it into the course wiki. See [Fun-ASR](fun-asr.md).
