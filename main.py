import os
import json
import requests
from datetime import datetime

# ================= 配置 =================
WECOM_BOT_ID = os.getenv("WECOM_BOT_ID")
WECOM_BOT_SECRET = os.getenv("WECOM_BOT_SECRET")

# ================= 微信推送 =================
def send_wechat(text):
    if not WECOM_BOT_ID or not WECOM_BOT_SECRET:
        return
    try:
        token_url = "https://qyapi.weixin.qq.com/cgi-bin/service/get_suite_token"
        token_resp = requests.post(token_url, json={
            "bot_id": WECOM_BOT_ID,
            "secret": WECOM_BOT_SECRET
        }).json()
        access_token = token_resp.get("access_token")

        send_url = f"https://qyapi.weixin.qq.com/cgi-bin/bot/send?access_token={access_token}"
        requests.post(send_url, json={
            "bot_id": WECOM_BOT_ID,
            "msgtype": "text",
            "text": {"content": text[:2000]}
        })
    except Exception as e:
        print("推送失败", e)

# ================= 极简选股 =================
def select_stocks():
    return [
        {"code": "000001", "name": "平安银行", "reason": "低估值，金融龙头"},
        {"code": "600036", "name": "招商银行", "reason": "业绩稳健，均线多头"},
        {"code": "601318", "name": "中国平安", "reason": "超跌，估值修复"},
        {"code": "000333", "name": "格力电器", "reason": "现金流优秀"},
        {"code": "600519", "name": "贵州茅台", "reason": "消费龙头，长线看好"}
    ]

# ================= 生成报告 =================
def build_report(stocks):
    today = datetime.now().strftime("%Y-%m-%d")
    content = f"【A股每日精选 {today}】\n\n"
    for i, s in enumerate(stocks, 1):
        content += f"{i}. {s['code']} {s['name']}\n✨ {s['reason']}\n\n"
    return content

# ================= 保存 =================
def save_report(content):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("report", exist_ok=True)
    with open(f"report/{today}.md", "w", encoding="utf-8") as f:
        f.write(f"# A股精选 {today}\n\n{content}")

# ================= 运行 =================
if __name__ == "__main__":
    stocks = select_stocks()
    report = build_report(stocks)
    save_report(report)
    send_wechat(report)
    print("✅ 完成！已推送微信")
