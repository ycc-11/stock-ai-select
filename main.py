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
# 修复：股票数据（字段名已更新）
# ==============================================
def get_stock_base():
    df = ak.stock_zh_a_spot_em()

    # 修复：akshare 最新字段
    df = df.rename(columns={
        "最新": "现价",
        "动态市盈率": "市盈率",
        "总市值": "总市值"
    })

    # 只保留需要的列
    keep_cols = ["代码", "名称", "涨跌幅", "现价", "市盈率", "总市值"]
    df = df[[c for c in keep_cols if c in df.columns]]

    # 过滤
    df = df[~df["名称"].str.contains("ST|退|科|创业", na=False)]
    df = df[(df["现价"] > 2) & (df["市盈率"] > 0) & (df["市盈率"] < 30)]
    return df

# ==============================================
# 技术指标：均线、MACD、KDJ
# ==============================================
def calc_tech(df_k):
    df = df_k.copy()
    df["MA5"] = df["收盘"].rolling(5).mean()
    df["MA10"] = df["收盘"].rolling(10).mean()
    df["MA20"] = df["收盘"].rolling(20).mean()

    ema12 = df["收盘"].ewm(span=12, adjust=False).mean()
    ema26 = df["收盘"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    low9 = df["最低"].rolling(9).min()
    high9 = df["最高"].rolling(9).max()
    df["RSV"] = (df["收盘"] - low9) / (high9 - low9) * 100
    df["K"] = df["RSV"].rolling(3).mean()
    df["D"] = df["K"].rolling(3).mean()

    last = df.iloc[-1]
    return {
        "close": round(last["收盘"], 2),
        "ma5": round(last["MA5"], 2),
        "ma10": round(last["MA10"], 2),
        "ma20": round(last["MA20"], 2),
        "macd": round(last["MACD"], 2),
        "signal": round(last["SIGNAL"], 2),
        "k": round(last["K"], 2),
        "d": round(last["D"], 2)
    }

# ==============================================
# 选股
# ==============================================
def filter_all_stocks():
    base_df = get_stock_base()
    res = []
    for _, row in base_df.iterrows():
        code = row["代码"]
        try:
            df_k = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            if len(df_k) < 30:
                continue
            tech = calc_tech(df_k)

            if not (tech["close"] > tech["ma5"] > tech["ma10"] > tech["ma20"]):
                continue
            if not (tech["macd"] > tech["signal"]):
                continue
            if not (tech["k"] > tech["d"] and tech["k"] < 50):
                continue
            if float(row["总市值"]) < 1000000000:
                continue

            item = row.to_dict()
            item.update(tech)
            res.append(item)
        except Exception as e:
            continue
        if len(res) >= 10:
            break
    return res

# ==============================================
# AI 分析
# ==============================================
def ai_analysis(stocks):
    prompt = f"""
你是专业A股量化分析师，从以下股票中精选最优5只。
条件：均线多头、MACD金叉、KDJ低位、基本面健康。

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
def save_md(content):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("report", exist_ok=True)
    with open(f"report/{today}.md", "w", encoding="utf-8") as f:
        f.write(f"# A股每日选股报告 {today}\n\n{content}")

# ==============================================
# 主程序
# ==============================================
if __name__ == "__main__":
    print("开始获取股票...")
    stock_list = filter_all_stocks()
    print(f"符合条件：{len(stock_list)} 只")

    print("AI 分析中...")
    report = ai_analysis(stock_list)

    save_md(report)
    send_wechat(f"【A股智能选股】\n{report}")
    print("完成！")
