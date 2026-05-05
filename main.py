import akshare as ak
import os
import json
import requests
from datetime import datetime
from openai import OpenAI

# ==============================================
# 环境变量
# ==============================================
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_BOT_ID = os.getenv("WECOM_BOT_ID")
WECOM_BOT_SECRET = os.getenv("WECOM_BOT_SECRET")

client = OpenAI(
    api_key=DOUBAO_API_KEY,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)

# ==============================================
# 企业微信推送
# ==============================================
def send_wechat(text):
    if not WECOM_BOT_ID or not WECOM_BOT_SECRET:
        print("未配置微信推送")
        return
    try:
        token_url = "https://qyapi.weixin.qq.com/cgi-bin/service/get_suite_token"
        token_resp = requests.post(token_url, json={"bot_id": WECOM_BOT_ID, "secret": WECOM_BOT_SECRET}).json()
        access_token = token_resp.get("access_token")

        send_url = f"https://qyapi.weixin.qq.com/cgi-bin/bot/send?access_token={access_token}"
        requests.post(send_url, json={
            "bot_id": WECOM_BOT_ID,
            "msgtype": "text",
            "text": {"content": text[:2000]}
        })
    except Exception as e:
        print("推送失败:", e)

# ==============================================
# 【终极修复】股票数据获取，兼容所有 akshare 版本
# ==============================================
def get_stock_base():
    df = ak.stock_zh_a_spot_em()

    # 自动兼容字段名（永久修复）
    rename_map = {}
    for c in df.columns:
        if '最新' in c or '现价' in c: rename_map[c] = 'price'
        if '市盈率' in c: rename_map[c] = 'pe'
        if '代码' in c: rename_map[c] = 'code'
        if '名称' in c: rename_map[c] = 'name'
        if '涨跌幅' in c: rename_map[c] = 'change'
        if '总市值' in c: rename_map[c] = 'market_cap'

    df = df.rename(columns=rename_map)
    df = df[[c for c in ['code','name','change','price','pe','market_cap'] if c in df.columns]]

    # 过滤
    df = df[~df['name'].str.contains('ST|退', na=False)]
    df = df[df['price'] > 2]
    df = df[df['pe'] > 0]
    df = df[df['pe'] < 30]
    return df

# ==============================================
# 技术指标：均线、MACD、KDJ
# ==============================================
def calc_tech(code):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
        if len(df) < 30: return None

        df['ma5'] = df['收盘'].rolling(5).mean()
        df['ma10'] = df['收盘'].rolling(10).mean()
        df['ma20'] = df['收盘'].rolling(20).mean()

        ema12 = df['收盘'].ewm(span=12, adjust=False).mean()
        ema26 = df['收盘'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        low9 = df['最低'].rolling(9).min()
        high9 = df['最高'].rolling(9).max()
        df['rsv'] = (df['收盘'] - low9) / (high9 - low9) * 100
        df['k'] = df['rsv'].rolling(3).mean()
        df['d'] = df['k'].rolling(3).mean()

        last = df.iloc[-1]
        return {
            'close': round(last['收盘'],2),
            'ma5': round(last['ma5'],2),
            'ma10': round(last['ma10'],2),
            'ma20': round(last['ma20'],2),
            'macd': round(last['macd'],2),
            'signal': round(last['signal'],2),
            'k': round(last['k'],2),
            'd': round(last['d'],2),
        }
    except:
        return None

# ==============================================
# 选股核心
# ==============================================
def filter_all_stocks():
    df = get_stock_base()
    res = []
    for _, row in df.iterrows():
        code = row['code']
        tech = calc_tech(code)
        if not tech: continue

        # 技术筛选
        ma_ok = tech['close'] > tech['ma5'] > tech['ma10'] > tech['ma20']
        macd_ok = tech['macd'] > tech['signal']
        kdj_ok = tech['k'] > tech['d'] and tech['k'] < 50
        market_ok = float(row['market_cap']) > 1000000000

        if ma_ok and macd_ok and kdj_ok and market_ok:
            res.append({**row, **tech})
        if len(res) >= 10: break
    return res

# ==============================================
# AI 分析
# ==============================================
def ai_analysis(stocks):
    prompt = f"""
你是专业A股量化分析师，从以下股票精选最优5只。
条件：均线多头、MACD金叉、KDJ低位、市值健康。

输出格式：
1. 代码 名称 | 价格
2. 技术逻辑
3. 投资看点
4. 风险

股票：
{json.dumps(stocks, ensure_ascii=False)}
"""
    resp = client.chat.completions.create(
        model="doubao-1.5-pro",
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content

# ==============================================
# 保存报告
# ==============================================
def save_report(content):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("report", exist_ok=True)
    with open(f"report/{today}.md", "w", encoding="utf-8") as f:
        f.write(f"# A股每日精选 {today}\n\n{content}")

# ==============================================
# 主程序
# ==============================================
if __name__ == "__main__":
    print("开始选股...")
    stocks = filter_all_stocks()
    print(f"符合条件：{len(stocks)} 只")

    print("AI 分析...")
    report = ai_analysis(stocks)

    save_report(report)
    send_wechat(f"【A股智能选股】\n{report}")
    print("完成！")
