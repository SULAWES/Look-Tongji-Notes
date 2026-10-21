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

只在用户明确选择必剪时配置 `ASR_ENGINE=bcut`。任何 Fun-ASR 错误都不会触发 Bcut、豆包或本地模型回退。遵循本次会话已经给出的云端上传授权，不要重复询问已授权的同一范围。

## 官方接口

- [临时文件上传](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)
- [Fun-ASR 录音文件识别 HTTP API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api)
