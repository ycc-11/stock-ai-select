import os
import re
import json
import requests
from datetime import datetime

# ========== 配置 ==========
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")
ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
ENDPOINT_ID = "ep-20260506125835-cc6j5"

# ========== 1. 获取A股列表（新浪） ==========
def get_all_stocks():
    stocks = []
    # 沪市 600/601/603/605
    for prefix in ["600", "601", "603", "605"]:
        for i in range(0, 1000):
            code = f"{prefix}{i:03d}"
            stocks.append(("sh", code))
    # 深市 000/001/002/003
    for prefix in ["000", "001", "002", "003"]:
        for i in range(0, 1000):
            code = f"{prefix}{i:03d}"
            stocks.append(("sz", code))
    return stocks

# ========== 2. 单只股票行情+简单指标（新浪） ==========
def get_stock_info(market, code):
    try:
        url = f"http://hq.sinajs.cn/list={market}{code}"
        resp = requests.get(url, timeout=5, headers={"Referer": "https://finance.sina.com.cn/"})
        resp.raise_for_status()
        text = resp.text
        if "var hq_str_" not in text:
            return None

        # 解析字段
        parts = text.split('"')[1].split(",")
        if len(parts) < 32:
            return None

        name = parts[0]
        price = float(parts[3])
        open_ = float(parts[1])
        high = float(parts[4])
        low = float(parts[5])
        pre_close = float(parts[2])
        volume = float(parts[8])

        # 过滤ST/退市
        if "ST" in name or "*ST" in name or "退" in name:
            return None

        # 简单均线多头判断（今日 > 昨日）
        ma5_ok = price > pre_close
        # 简单MACD金叉近似（上涨+量能）
        macd_gold = (price - pre_close) / pre_close > 0.01 and volume > 0

        return {
            "code": code,
            "name": name,
            "price": round(price, 2),
            "ma5_ok": ma5_ok,
            "macd_gold": macd_gold
        }
    except:
        return None

# ========== 3. 选股：符合规律（多头+金叉+价格区间） ==========
def get_stock_pool():
    print("\n=== 开始获取并筛选符合技术形态的股票 ===")
    all_stocks = get_all_stocks()
    valid = []

    # 抽样前 200 只，保证速度
    for market, code in all_stocks[:200]:
        info = get_stock_info(market, code)
        if not info:
            continue

        # 选股条件（你要的“符合规律”）
        if (
            info["price"] >= 3
            and info["price"] <= 50
            and info["ma5_ok"]
            and info["macd_gold"]
        ):
            valid.append(info)
            if len(valid) >= 8:
                break

    print(f"✅ 筛选完成，符合条件股票：{len(valid)} 只")
    return valid if valid else get_default_stocks()

# ========== 兜底股票 ==========
def get_default_stocks():
    return [
        {"code": "000001", "name": "平安银行", "price": 10.12},
        {"code": "600036", "name": "招商银行", "price": 34.56},
        {"code": "601318", "name": "中国平安", "price": 42.33},
        {"code": "000858", "name": "五粮液", "price": 168.88},
    ]

# ========== 豆包AI 分析 ==========
def doubao_analyze(stocks):
    print("\n=== 开始调用豆包AI ===")
    if not DOUBAO_API_KEY:
        print("❌ 未配置豆包API Key")
        return "未配置豆包AI"

    print(f"✅ API Key：{DOUBAO_API_KEY[:10]}...")
    print(f"✅ 接入点：{ENDPOINT_ID}")

    prompt = f"""你是A股专业分析师，从以下均线多头、MACD金叉的股票中精选5只，给出：
代码、名称、一句话投资逻辑，简洁、专业、易懂。

股票列表：
{json.dumps(stocks, ensure_ascii=False)}
"""

    headers = {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": ENDPOINT_ID,
        "stream": False,
        "input": [{"role": "user", "content": prompt}]
    }

    try:
        print("✅ 请求豆包AI中...")
        resp = requests.post(ARK_API_URL, headers=headers, json=payload, timeout=25)
        print(f"✅ 状态码：{resp.status_code}")

        if resp.status_code != 200:
            raise Exception(f"返回异常：{resp.text[:100]}")

        res = resp.json()
        text = res["response"]["output"][0]["content"][0]["text"]
        print("✅ 豆包AI分析完成！")
        return text.strip()

    except Exception as e:
        print(f"❌ 调用失败：{str(e)[:150]}")
        return "AI分析暂时不可用，今日精选优质股票：\n" + "\n".join([f"{s['code']} {s['name']}" for s in stocks[:5]])

# ========== 微信推送 ==========
def send_wechat(content):
    print("\n=== 推送微信 ===")
    if not WECOM_WEBHOOK:
        print("❌ 未配置微信Webhook")
        return

    try:
        requests.post(WECOM_WEBHOOK, json={
            "msgtype": "text",
            "text": {"content": f"【A股AI智能选股】\n{content}"}
        }, timeout=10)
        print("✅ 微信推送成功！")
    except:
        print("❌ 微信推送失败")

# ========== 保存报告 ==========
def save_report(content):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("report", exist_ok=True)
    with open(f"report/{today}.md", "w", encoding="utf-8") as f:
        f.write(f"# A股AI选股报告 {today}\n\n{content}")
    print("✅ 报告已保存")

# ========== 主程序 ==========
if __name__ == "__main__":
    print("=== A股AI智能选股系统 ===")
    stocks = get_stock_pool()
    result = doubao_analyze(stocks)
    save_report(result)
    send_wechat(result)
    print("\n=== ✅ 全部完成 ===")