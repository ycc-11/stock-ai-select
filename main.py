import akshare as ak
import os
import json
import requests
from datetime import datetime
from openai import OpenAI

DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")

client = OpenAI(
    api_key=DOUBAO_API_KEY,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)

def get_stock_base():
    df = ak.stock_zh_a_spot_em()
    df = df[["代码", "名称", "涨跌幅", "现价", "市盈率", "总市值"]]
    df = df[~df["名称"].str.contains("ST|退", na=False)]
    df = df[(df["现价"] > 2) & (df["市盈率"] > 0) & (df["市盈率"] < 30)]
    return df

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
        "close": round(last["收盘"],2),
        "ma5": round(last["MA5"],2),
        "ma10": round(last["MA10"],2),
        "ma20": round(last["MA20"],2),
        "macd": round(last["MACD"],2),
        "signal": round(last["SIGNAL"],2),
        "k": round(last["K"],2),
        "d": round(last["D"],2)
    }

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
            # 均线多头
            if not (tech["close"] > tech["ma5"] > tech["ma10"] > tech["ma20"]):
                continue
            # MACD金叉
            if not (tech["macd"] > tech["signal"]):
                continue
            # KDJ低位
            if not (tech["k"] > tech["d"] and tech["k"] < 50):
                continue
            # 市值百亿以上
            if float(row["总市值"]) < 10000000000:
                continue

            item = row.to_dict()
            item.update(tech)
            res.append(item)
        except:
            continue
        if len(res) >= 10:
            break
    return res

def ai_analysis(stocks):
    prompt = f"""
你是专业A股量化分析师，请从下面股票里精选最优5只。
筛选逻辑：
1. 5/10/20日均线多头排列
2. MACD金叉向上
3. KDJ低位向好
4. 市盈率合理，市值百亿以上

输出每只：代码、名称、现价、逻辑简述、短线看点、风险提示。
股票数据：
{json.dumps(stocks, ensure_ascii=False)}
"""
    resp = client.chat.completions.create(
        model="doubao-1.5-pro",
        messages=[{"role":"user","content":prompt}]
    )
    return resp.choices[0].message.content

def send_wechat_msg(text):
    if not WECOM_WEBHOOK:
        return
    payload = {"msgtype":"text","text":{"content":text[:2000]}}
    try:
        requests.post(WECOM_WEBHOOK, json=payload, timeout=10)
    except Exception as e:
        print("微信推送失败",e)

def save_md(content):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("report", exist_ok=True)
    with open(f"report/{today}.md","w",encoding="utf-8") as f:
        f.write(f"# A股每日选股报告 {today}\n\n{content}")

if __name__ == "__main__":
    print("开始筛选股票...")
    stock_list = filter_all_stocks()
    print(f"技术筛选完毕，符合条件数量：{len(stock_list)}")

    print("豆包AI分析中...")
    report = ai_analysis(stock_list)

    save_md(report)
    send_wechat_msg(f"【A股每日选股推送】\n{report}")
    print("全部完成，已保存报告并推送微信")
