import os
import json
import requests
from datetime import datetime

# ========== 配置 ==========
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")
ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
ENDPOINT_ID = "ep-20260506125835-cc6j5"

# ========== 1. 获取股票列表 ==========
def get_all_stocks():
    stocks = []
    for prefix in ["600", "601", "603", "605"]:
        for i in range(0, 1000):
            code = f"{prefix}{i:03d}"
            stocks.append(("sh", code))
    for prefix in ["000", "001", "002", "003"]:
        for i in range(0, 1000):
            code = f"{prefix}{i:03d}"
            stocks.append(("sz", code))
    return stocks

# ========== 2. 获取单只股票信息 ==========
def get_stock_info(market, code):
    try:
        url = f"http://hq.sinajs.cn/list={market}{code}"
        resp = requests.get(url, timeout=4, headers={"Referer": "https://finance.sina.com.cn/"})
        if "var hq_str_" not in resp.text:
            return None

        parts = resp.text.split('"')[1].split(",")
        if len(parts) < 32:
            return None

        name = parts[0]
        price = float(parts[3])

        if "ST" in name or "退" in name:
            return None

        return {
            "code": code,
            "name": name,
            "price": round(price, 2)
        }
    except:
        return None

# ========== 3. 筛选符合形态的股票 ==========
def get_stock_pool():
    print("\n=== 开始获取并筛选符合技术形态的股票 ===")
    all_stocks = get_all_stocks()
    valid = []

    for market, code in all_stocks[:150]:
        info = get_stock_info(market, code)
        if info:
            valid.append(info)
            if len(valid) >= 6:
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

# ========== 【通用】调用豆包AI（打印返回值） ==========
def ask_doubao(prompt):
    print("\n=== 开始调用豆包AI ===")
    if not DOUBAO_API_KEY:
        return "未配置API Key"

    print(f"✅ API Key：{DOUBAO_API_KEY[:10]}...")

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
        resp = requests.post(ARK_API_URL, headers=headers, json=payload, timeout=30)
        print(f"✅ 状态码：{resp.status_code}")
        res = resp.json()

        # ======================
        # 1. 打印豆包完整返回值
        # ======================
        print("\n======================")
        print("📝 豆包原始返回值：")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        print("======================\n")

        text = ""
        if "response" in res:
            output = res["response"]["output"][0]
            if output["type"] == "message":
                text = output["content"][0]["text"]

        return text.strip() if text else "无返回内容"

    except Exception as e:
        print(f"❌ 调用失败：{str(e)}")
        return "AI调用失败"

# ========== 分析股票 ==========
def analyze_stocks(stocks):
    prompt = """严格按以下格式输出，每条都不能少：

【股票代码+名称】
📊 所属板块：
💡 推荐理由：
📌 投资逻辑：

分析列表：
""" + json.dumps(stocks, ensure_ascii=False)
    return ask_doubao(prompt)

# ========== 2. 获取热门板块、资金流向、热门事件 ==========
def get_market_hot_info():
    prompt = """请输出今日A股：
1. 热门板块
2. 资金流向
3. 热门市场事件

格式简洁清晰，适合微信阅读。
"""
    return ask_doubao(prompt)

# ========== 微信推送 ==========
def send_wechat(content):
    print("\n=== 推送微信 ===")
    if not WECOM_WEBHOOK:
        print("❌ 未配置微信Webhook")
        return

    try:
        requests.post(WECOM_WEBHOOK, json={
            "msgtype": "text",
            "text": {"content": content}
        }, timeout=10)
        print("✅ 微信推送成功！")
    except:
        print("❌ 微信推送失败")

# ========== 保存报告（年月日_小时分钟） ==========
def save_report(content):
    filename = datetime.now().strftime("%Y-%m-%d_%H%M")
    os.makedirs("report", exist_ok=True)
    with open(f"report/{filename}.md", "w", encoding="utf-8") as f:
        f.write(f"# A股AI选股报告 {filename}\n\n{content}")
    print(f"✅ 报告已保存：report/{filename}.md")

# ========== 主程序 ==========
if __name__ == "__main__":
    print("=== A股AI智能选股系统 ===")

    # 1. 获取股票池
    stocks = get_stock_pool()

    # 2. 分析股票
    stock_analysis = analyze_stocks(stocks)

    # 3. 获取市场热点（新增）
    market_info = get_market_hot_info()

    # 4. 合并最终内容
    final_content = "【📊 A股AI智能选股报告】\n\n"
    final_content += "=== 精选股票分析 ===\n"
    final_content += stock_analysis + "\n\n"
    final_content += "=== 今日市场热点 ===\n"
    final_content += market_info

    # 5. 保存 + 推送
    save_report(final_content)
    send_wechat(final_content)

    print("\n=== ✅ 全部完成 ===")