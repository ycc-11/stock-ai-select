import os
import json
import requests
import time
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta, timezone

# ========== 1. 配置与时区校准 ==========
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")
ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
ENDPOINT_ID = "ep-20260506125835-cc6j5"

# 获取北京时间 (UTC+8)
def get_beijing_time():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz)

# ========== 2. 增强型数据接口 ==========

def get_zt_data_robust():
    """多级兜底获取涨停数据"""
    bj_now = get_beijing_time()
    print(f"\n>>> 正在检索涨停数据 [北京时间: {bj_now.strftime('%Y-%m-%d %H:%M:%S')}]")
    
    df = None
    
    # 策略 A: 尝试实时涨停池
    try:
        print("   [尝试1] 访问实时涨停池 (EM Realtime)...")
        df = ak.stock_zt_pool_em()
    except:
        pass

    # 策略 B: 如果 A 失败，尝试历史涨停总结 (处理盘后清算期)
    if df is None or df.empty:
        try:
            print("   [尝试2] 实时池为空，访问涨停板分析 (EM Previous)...")
            df = ak.stock_zt_pool_previous_em()
        except:
            pass

    # 策略 C: 终极兜底 - 抓取“昨日涨停个股” (这些是个股在今天的表现)
    if df is None or df.empty:
        try:
            print("   [尝试3] 访问昨日涨停表现池 (EM Yesterday)...")
            df = ak.stock_zt_pool_sub_zbgc_em()
        except:
            pass

    if df is None or df.empty:
        print("   [!] 所有涨停接口均未返回数据，可能非交易日或接口限流。")
        return []

    # 统一字段映射逻辑
    column_map = {
        '代码': 'code', '证券代码': 'code',
        '名称': 'name', '证券名称': 'name',
        '连板数': 'links', '连续涨停天数': 'links',
        '所属行业': 'industry', '板块': 'industry',
        '换手率': 'turnover',
        '最后封板时间': 'time'
    }
    
    existing_cols = {k: v for k, v in column_map.items() if k in df.columns}
    df = df[existing_cols.keys()].rename(columns=existing_cols)
    
    # 数据清洗：确保连板数有效
    if 'links' in df.columns:
        df['links'] = pd.to_numeric(df['links'], errors='coerce').fillna(1)
    else:
        df['links'] = 1
        
    df = df.sort_values(by='links', ascending=False)
    data = df.head(15).to_dict(orient='records')
    print(f"   [成功] 提取到 {len(data)} 只目标个股。")
    return data

# ========== 3. AI 调用分析 (保持逻辑) ==========

def analyze_by_ai(stock_data):
    if not DOUBAO_API_KEY: return "未配置 API KEY"
    
    stock_summary = ""
    for s in stock_data:
        stock_summary += f"- {s.get('name')}({s.get('code')}): {int(s.get('links'))}板, 行业:{s.get('industry')}\n"

    prompt = f"你是实战派游资，分析以下最新连板数据，指出核心热点、龙头妖股潜质及明日策略：\n{stock_summary}"

    payload = {
        "model": ENDPOINT_ID,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    headers = {"Authorization": f"Bearer {DOUBAO_API_KEY}", "Content-Type": "application/json"}

    try:
        resp = requests.post(ARK_API_URL, headers=headers, json=payload, timeout=60)
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI 研判异常: {e}"

# ========== 4. 执行流程 ==========

if __name__ == "__main__":
    bj_time = get_beijing_time()
    print("="*50)
    print(f"   🚀 A股强势股 AI 分析系统 V4.1 (时区校准版)")
    print(f"   北京时间: {bj_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)

    stocks = get_zt_data_robust()
    
    if stocks:
        analysis_report = analyze_by_ai(stocks)
        
        report_md = f"""# 📊 A股强势股 AI 研报
**数据基准：** 涨停连板池 (TOP 15)
**报告时间：** 北京时间 {bj_time.strftime('%H:%M')}

---
{analysis_report}

---
*风险提示：数据仅供参考，不构成投资建议。*
"""
        # 保存本地
        os.makedirs("report", exist_ok=True)
        f_name = f"report/ZT_Report_{bj_time.strftime('%H%M')}.md"
        with open(f_name, "w", encoding="utf-8") as f:
            f.write(report_md)

        # 微信推送
        if WECOM_WEBHOOK:
            requests.post(WECOM_WEBHOOK, json={"msgtype": "markdown", "markdown": {"content": report_md}})
            print("\n✅ 推送报告成功！")
    else:
        print("\n[!] 今日无有效数据可分析。")