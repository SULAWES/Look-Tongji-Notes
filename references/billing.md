# 阿里云余额查询（可选）

余额查询通过已安装的阿里云 CLI `aliyun` 调用 `BssOpenApi/2017-12-14` 的 `QueryAccountBalance`，不需要增加 Python SDK。它使用独立的 CLI 身份，不能使用 `DASHSCOPE_API_KEY`。

## 配置

1. 安装阿里云 CLI，为专用 RAM 身份授予查询余额权限 `bss:DescribeAcccount`（按官方拼写，三个连续的 c）。不需要完整账务管理权限。
2. 在终端运行 `aliyun configure --profile tongji-billing` 配置身份。不要把 AccessKey 发到聊天、写入仓库或放进命令行参数。
3. 在 skill 根目录 `.env` 配置：

```dotenv
ALIYUN_BILLING_PROFILE="tongji-billing"
ALIYUN_LOW_BALANCE_THRESHOLD="10.00"
ALIYUN_BALANCE_CURRENCY="CNY"
```

环境变量优先于 `.env`；也支持 `LOOK_TONGJI_ENV_PATH`。CLI 参数优先于环境配置。未配置 profile 时，批处理提示跳过查询；独立查询返回错误。不隐式使用默认身份。未设置阈值时仅显示余额，不进行低余额提醒。

## 使用

```bash
python scripts/look_tongji.py balance
python scripts/look_tongji.py balance --json
python scripts/look_tongji.py balance --profile tongji-billing --low-balance-threshold 20 --threshold-currency CNY
python scripts/look_tongji.py batch-transcribe --course-id "<ID>"
```

`batch-transcribe` 同样接受这三个配置参数。Fun-ASR 批次在处理课时前查询一次；Bcut 批次跳过。Agent 手动循环逐课转录时，在循环开始前调用一次 `balance`，不要每课查询。

文本和 JSON 输出包括 profile、UTC 查询时间、现金余额、可用额度、币种和阈值比较结果。金额以十进制字符串输出。`low_balance` 在现金余额严格低于阈值时为 true；未设置阈值或币种不同为 null。不同币种不换算，文本输出说明跳过比较。

余额偏低仅提醒，不阻止转录。缺少 CLI、权限不足、超时或接口异常时余额为“未知”；独立命令退出码为 1（`--json` 输出 `success: false`），批处理提醒后继续。查询最多等待 20 秒，不自动重试。CLI 原始诊断不回显，避免泄露凭证。

返回的是阿里云账号级余额，请确认 profile 与百炼 API Key 对应同一付费账号。余额不能反映专属模型免费额度，也不能把余额差当作本批课程费用。此功能不修改付费任务检查点，不充值、不自动切换 ASR 引擎。查询结果不写入课程材料或公开 wiki。

## 官方参考

- [余额接口及字段](https://help.aliyun.com/zh/user-center/developer-reference/api-bssopenapi-2017-12-14-queryaccountbalance)
- [API 授权与余额权限映射](https://help.aliyun.com/en/user-center/developer-reference/api-calling-authorization)
- [CLI 参数](https://help.aliyun.com/zh/cli/command-line-options)
