"""Optional, read-only Alibaba Cloud balance lookup through a named CLI profile."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import subprocess


class BillingError(RuntimeError):
    pass


def amount(value: object) -> Decimal:
    """Parse API decimal strings without losing monetary precision."""
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError):
        raise BillingError("金额必须是有限十进制数。") from None


def query_balance(profile: str, threshold: str = "", threshold_currency: str = "CNY") -> dict:
    if not profile.strip():
        raise BillingError("未配置余额查询：请设置 ALIYUN_BILLING_PROFILE 或 --profile。")
    limit = amount(threshold) if threshold != "" else None
    if limit is not None and limit < 0:
        raise BillingError("低余额提醒阈值不能为负数。")
    try:
        response = subprocess.run(
            ["aliyun", "bssopenapi", "QueryAccountBalance", "--profile", profile,
             "--region", "cn-hangzhou", "--endpoint", "business.aliyuncs.com"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except FileNotFoundError:
        raise BillingError("未安装阿里云 CLI：请先安装 aliyun 并配置专用 profile。") from None
    except subprocess.TimeoutExpired:
        raise BillingError("余额查询超时（20 秒），余额未知。") from None
    except (OSError, UnicodeError):
        raise BillingError("无法运行阿里云 CLI，余额未知。") from None
    # Never echo CLI stdout/stderr: diagnostic output may contain credentials.
    if response.returncode:
        raise BillingError("阿里云 CLI 查询失败，请检查 profile、RAM 权限和网络；余额未知。")
    try:
        payload = json.loads(response.stdout)
        if not isinstance(payload, dict) or payload.get("Success") is not True:
            raise ValueError
        data = payload["Data"]
        cash = amount(data["AvailableCashAmount"])
        available = amount(data["AvailableAmount"])
        currency = data["Currency"]
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError
    except (ValueError, KeyError, TypeError, BillingError):
        raise BillingError("余额接口返回失败或无效数据，余额未知。") from None
    comparable = limit is not None and currency == threshold_currency
    return {
        "profile": profile,
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "currency": currency,
        "available_cash_amount": str(cash),
        "available_amount": str(available),
        "low_balance_threshold": str(limit) if limit is not None else None,
        "threshold_currency": threshold_currency,
        "threshold_comparable": comparable,
        "low_balance": cash < limit if comparable else None,
    }


def format_balance(result: dict) -> str:
    lines = [f"[Balance] 现金余额 {result['available_cash_amount']} {result['currency']}；"
             f"可用额度 {result['available_amount']} {result['currency']}",
             f"[Balance] profile={result['profile']}；查询时间={result['queried_at']}"]
    if result["low_balance"]:
        lines.append(f"[Warning] 现金余额低于提醒阈值 {result['low_balance_threshold']} "
                     f"{result['threshold_currency']}；仅提醒，继续执行。")
    elif result["low_balance_threshold"] is not None and not result["threshold_comparable"]:
        lines.append("[Warning] 余额与阈值币种不同，未进行低余额比较。")
    return "\n".join(lines)
