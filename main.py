import os
import json
import requests
from datetime import datetime
from openai import OpenAI

# ================= 配置 =================
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_BOT_ID = os.getenv("WECOM_BOT_ID")
WECOM_BOT_SECRET = os.getenv("WECOM_BOT_SECRET")

client = OpenAI(api_key=DOUBAO_API_KEY, base_url="https://open.doubao.com/api/v1")

# ================= 微信推送 =================
def send_wechat(text):
    if not WECOM_BOT_ID or not WECOM_BOT_SECRET:
        return
    try:
        token_url = "https://qyapi.weixin.qq.com/cgi-bin/service/get_suite_token"
        token_resp = requests.post(token_url, json={"bot_id": WECOM_BOT_ID, "secret": WECOM_BOT_SECRET}).json()
        access_token = token_resp.get("access_token")
        send_url = f"https://qyapi.weixin.qq.com/cgi-bin/bot/send?access_token={access_token}"
        requests.post(send_url, json={"bot_id": WECOM_BOT_ID, "msgtype": "text", "text": {"content": text[:2000]}})
    except:
        pass

# ================= 超轻量选股（不下载K线！） =================
def get_stocks():
    url = "https://60.28.76.175/js/api/stockList.js"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        res = []
        for item in data[:30]:  # 只取30只
            code = item.get("code")
            name = item.get("name")
            price = float(item.get("price", 0))
            pe = float(item.get("pe", 0))
            if price < 3 or pe < 1 or pe > 30:
                continue
            if "ST" in name or "退" in name:
                continue
            res.append({"code": code, "name": name, "price": price, "pe": pe})
            if len(res) >= 6:
                break
        return res
    except:
        return [{"code": "000001", "name": "平安银行", "price": 10.11, "pe": 8.2}]

# ================= AI 分析 =================
def ai_analysis(stocks):
    prompt = f"""你是A股分析师，精选股票：
{json.dumps(stocks, ensure_ascii=False)}
输出：代码、名称、价格、简要逻辑。"""
    resp = client.chat.completions.create(model="doubao-pro", messages=[{"role":"user","content":prompt}])
    return resp.choices[0].message.content

# ================= 保存报告 =================
def save_report(content):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("report", exist_ok=True)
    with open(f"report/{today}.md", "w", encoding="utf-8") as f:
        f.write(f"# A股精选 {today}\n\n{content}")

# ================= 主程序 =================
if __name__ == "__main__":
    stocks = get_stocks()
    report = ai_analysis(stocks)
    save_report(report)
    send_wechat(f"【A股选股】\n{report}")
    print("完成！")
