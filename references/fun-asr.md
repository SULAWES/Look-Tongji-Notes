# Fun-ASR 默认转录

所有转录入口默认使用阿里云北京地域 `fun-asr`。本机只负责下载、ffmpeg 提取音频和上传，不加载本地识别模型。Fun-ASR 为付费服务，价格以[阿里云定价](https://help.aliyun.com/zh/model-studio/model-pricing)为准。

## 配置

在 skill 根目录 `.env` 中配置（不要发到聊天或提交 Git）：

```dotenv
ASR_ENGINE="fun-asr"
DASHSCOPE_API_KEY="你的北京地域百炼 API Key"
```

也可运行 `python scripts/look_tongji.py setup` 隐藏输入；已有 `.env` 可直接编辑以保留同济凭据。环境变量优先于 `.env`。`LOOK_TONGJI_ENV_PATH` 可指定其他配置文件。缺少 key 时仍可列课，但转录在下载音频前报错。

[API Key 获取说明](https://help.aliyun.com/zh/model-studio/get-api-key)。不要将阿里云 AccessKey ID/Secret 当作百炼 API Key。

## 上传与输出

脚本获取临时上传凭证，将本地音频直接上传至阿里云提供的私有临时存储，再提交 `oss://` 资源给 Fun-ASR。**不需要自行开通 OSS、填写存储桶或提供 OSS AccessKey，也不使用必剪中转。** 文件有效期 48 小时，仅用于同账号相应模型调用。上传使用磁盘临时文件，避免整段音频占用内存；上限取上传凭证限制与 1 GiB 中的较小值，超限需分段。

输出保留 TXT、带真实句级时间戳的 SRT 和 utterances JSON；课时元数据增加 `asr_engine`、`asr_model`。原始识别结果和任务 ID 保存在 skill 根目录 `state/fun-asr/`，不发布到课程 wiki。

## 恢复与避免重复计费

- 缓存以音频字节、模型参数、API endpoint 和 API Key 的组合哈希标识，不保存 key。同一音频复用任务或结果；更换 key 或音频内容会产生新的缓存身份，可能重新计费。
- 下载音频后才能计算身份；再次运行仍会下载和提取音频。缓存命中后不会再次上传或提交识别。
- `queued`：已有 task ID。网络失败或轮询超时后，重新执行原命令继续查询。
- `done`：优先读取 `result.json`，无需网络识别。
- `submitting`：请求可能已被服务端接收，但本地未可靠保存 task ID。**不要自动删除状态或重新提交**。先核查服务端任务/账单，若找回对应 task ID，可将该 `task.json` 的 `task_id` 填回并将 `phase` 改为 `queued`。确认没有已受理任务后，才由用户决定是否移走这个任务目录并重新提交。
- `failed`：任务或子任务失败。检查服务端原因，再决定是否付费重试；批处理不能清空检查点绕过保护。
- 结果下载链接有有效期；及时恢复并保存结果。若链接失效且无法再次查询取回，报告错误并由用户决定是否新建任务。
- 不主动重试创建任务的 POST。进程锁防止同一缓存任务并发提交。轮询 HTTP 错误会保留状态并退出，可再次运行恢复。
- `FUN_ASR_STATE_DIR` 可指定持久私有目录。清空缓存、换 key 或改变音频会失去复用能力。迁移 skill 时可保留此目录。

## 可选 BcutASR fallback：使用前询问

Fun-ASR 仍是默认引擎。失败时可以向用户提出使用 BcutASR（必剪）作为备用，但不能自动切换。

1. 说明 Fun-ASR 失败原因、受影响的课时，以及音频将上传到哔哩哔哩云端识别。询问：“是否同意这次改用 BcutASR 识别这些课时？”批处理应列明或描述授权范围，可一次询问整组失败课时。
2. 等待用户明确同意本次 fallback 及其范围。此前笼统的 Bcut 上传授权、未回复或超时不代表同意本次切换。若用户已经明确同意了本次 fallback 的同一范围，不重复询问。
3. 同意后仅在获准的命令进程设置 `ASR_ENGINE=bcut`；不要修改 `.env` 的默认值。跨平台调用可使用 Python 子进程：

```python
import os
import subprocess
import sys

# Only execute after explicit user approval for this lecture/fallback.
env = dict(os.environ, ASR_ENGINE="bcut")
subprocess.run([
    sys.executable, "<skill_root>/scripts/look_tongji.py", "transcribe",
    "--course-id", "<course_id>", "--sub-id", "<sub_id>",
], env=env, check=True)
```

4. 保留 Fun-ASR 的任务与缓存。若任务提交状态不明或仍在运行，告知用户原任务可能继续计费；切换 Bcut 不会取消阿里云任务。Bcut 输出元数据会标注 `asr_engine=bcut`，生成笔记时如需记录来源，应如实注明。
5. 拒绝或未回复时不上传至 Bcut，保留待处理状态并报告失败。仅授权部分课时时，其余仍使用 Fun-ASR；批处理不得扩大 fallback 范围。CLI 本身不自动交互切换，由调用 skill 的 agent 执行询问和范围控制。

豆包和本地模型不作为 fallback。

## 官方接口

- [临时文件上传](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)
- [Fun-ASR 录音文件识别 HTTP API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api)

## 可选余额查询

通过独立的阿里云 CLI profile 查询账号余额，并在批量转录前展示。支持可配置的低现金余额提醒；不阻止处理、不改变 ASR 引擎。百炼 API Key 不能用于余额查询。详见[余额配置](billing.md)。
