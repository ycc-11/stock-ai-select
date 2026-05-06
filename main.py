import os
import json
import requests
from datetime import datetime
from openai import OpenAI

# ========== 环境变量 ==========
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")

# ========== 初始化豆包AI 兼容火山方舟稳定版 ==========
client = OpenAI(
    api_key=DOUBAO_API_KEY,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)

# ========== 固定精选股票池（避免下载K线、不超时、不慢） ==========
def get_base_stocks():
    return [
        {"code":"000001","name":"平安银行","sector":"金融"},
        {"code":"600036","name":"招商银行","sector":"金融"},
        {"code":"601318","name":"中国平安","sector":"保险"},
        {"code":"000333","name":"格力电器","sector":"家电"},
        {"code":"600519","name":"贵州茅台","sector":"消费"},
        {"code":"300750","name":"宁德时代","sector":"新能源"},
        {"code":"601899","name":"紫金矿业","sector":"有色"},
        {"code":"000858","name":"五粮液","sector":"消费"}
    ]

# ========== 豆包AI智能分析选股 ==========
def doubao_analyze(stocks):
    if not DOUBAO_API_KEY:
        return "今日未配置豆包API，使用默认精选股票\n" + "\n".join([f"{s['code']} {s['name']}" for s in stocks[:5]])

    prompt = f"""
你是专业A股短线分析师，从下面股票里精选5只优质标的。
给出每只：代码、名称、短线逻辑、风险提示，简洁易懂。
股票列表：
{json.dumps(stocks, ensure_ascii=False)}
"""
    try:
        resp = client.chat.completions.create(
            model="doubao-lite",
            messages=[{"role":"user","content":prompt}],
            timeout=20
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print("豆包调用失败：", e)
        return "豆包AI调用异常，返回默认精选标的\n" + "\n".join([f"{s['code']} {s['name']}" for s in stocks[:5]])

# ========== 企业微信群推送（可直达个人微信） ==========
def send_wechat_msg(content):
    if not WECOM_WEBHOOK:
        print("未配置企业微信Webhook，跳过推送")
        return False
    try:
        payload = {
            "msgtype": "text",
            "text": {"content": f"【A股每日AI选股】\n{content}"}
        }
        res = requests.post(WECOM_WEBHOOK, json=payload, timeout=15)
        print("微信推送结果：", res.status_code)
        return True
    except Exception as e:
        print("微信推送失败：", e)
        return False

# ========== 保存每日报告 ==========
def save_markdown(content):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("report", exist_ok=True)
    path = f"report/{today}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# A股每日AI选股报告 {today}\n\n{content}")
    return path

# ========== 主入口 ==========
if __name__ == "__main__":
    print("1. 获取股票池...")
    stock_list = get_base_stocks()

    print("2. 豆包AI分析中...")
    report_text = doubao_analyze(stock_list)

    print("3. 保存报告...")
    save_markdown(report_text)

    print("4. 推送微信群...")
    ok = send_wechat_msg(report_text)

    if ok:
        print("✅ 全部完成：AI选股 + 报告保存 + 微信推送成功")
    else:
        print("⚠️ 完成选股，但微信推送失败")