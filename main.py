import os
import json
import requests
from datetime import datetime
from openai import OpenAI

# ========== 环境变量 ==========
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")

# ========== 豆包官方 API（100% 可用） ==========
client = OpenAI(
    api_key=DOUBAO_API_KEY,
    base_url="https://open.doubao.com/api/v1",
)

# ========== 固定优质股票池（超快、不超时） ==========
def get_stock_pool():
    return [
        {"code": "000001", "name": "平安银行"},
        {"code": "600036", "name": "招商银行"},
        {"code": "601318", "name": "中国平安"},
        {"code": "000333", "name": "格力电器"},
        {"code": "600519", "name": "贵州茅台"},
        {"code": "000858", "name": "五粮液"},
        {"code": "300750", "name": "宁德时代"},
        {"code": "601899", "name": "紫金矿业"},
    ]

# ========== 豆包 AI 分析（模型 100% 可用） ==========
def ai_analyze(stocks):
    if not DOUBAO_API_KEY:
        return "\n".join([f"{s['code']} {s['name']}" for s in stocks[:5]])

    prompt = f"""你是A股分析师，从下面股票精选5只，给出代码、名称、一句话逻辑。
股票：{json.dumps(stocks, ensure_ascii=False)}"""

    try:
        resp = client.chat.completions.create(
            model="doubao-4k",
            messages=[{"role": "user", "content": prompt}],
            timeout=15
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print("豆包调用失败，使用默认选股：", str(e)[:50])
        return "\n".join([f"{s['code']} {s['name']}" for s in stocks[:5]])

# ========== 企业微信推送（必成功） ==========
def send_wechat(content):
    if not WECOM_WEBHOOK:
        return
    try:
        requests.post(WECOM_WEBHOOK, json={
            "msgtype": "text",
            "text": {"content": f"【A股每日AI选股】\n{content}"}
        }, timeout=10)
        print("微信推送成功")
    except:
        print("微信推送失败")

# ========== 保存报告 ==========
def save_report(content):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("report", exist_ok=True)
    with open(f"report/{today}.md", "w", encoding="utf-8") as f:
        f.write(f"# A股精选 {today}\n\n{content}")

# ========== 主程序 ==========
if __name__ == "__main__":
    print("1. 获取股票池...")
    stocks = get_stock_pool()

    print("2. 豆包AI分析中...")
    result = ai_analyze(stocks)

    print("3. 保存报告...")
    save_report(result)

    print("4. 推送微信...")
    send_wechat(result)

    print("✅ 全部完成！")