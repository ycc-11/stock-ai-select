import os
import json
import requests
import time
import pandas as pd
import akshare as ak
from datetime import datetime

# ========== 1. 配置中心 ==========
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")
ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
ENDPOINT_ID = "ep-20260506125835-cc6j5"

# ========== 2. 核心行情接口 ==========

def get_zt_data():
    """获取涨停板数据，若实时池为空则尝试回溯"""
    print("\n>>> 正在检索涨停板数据池...")
    try:
        # 优先获取实时涨停池
        df = ak.stock_zt_pool_em()
        
        if df is None or df.empty:
            print("   [!] 实时涨停池为空（处于非交易时段），正在尝试获取历史涨停总结...")
            # 获取最近一个交易日的涨停分析 (可能会有几秒延迟)
            # 注意：此接口返回字段与实时池略有不同
            df = ak.stock_zt_pool_previous_em()
        
        if df is None or df.empty:
            print("   [!] 无法获取任何涨停数据，请检查网络或接口权限。")
            return []

        # 统一清洗字段名 (由于不同接口列名不一，这里做个映射)
        column_map = {
            '代码': 'code', '证券代码': 'code',
            '名称': 'name', '证券名称': 'name',
            '连板数': 'links', '连续涨停天数': 'links',
            '所属行业': 'industry', '板块': 'industry',
            '换手率': 'turnover',
            '最后封板时间': 'time', '最终封板时间': 'time'
        }
        
        # 找出存在的列并重命名
        existing_cols = {k: v for k, v in column_map.items() if k in df.columns}
        df = df[existing_cols.keys()].rename(columns=existing_cols)
        
        # 确保连板数是数值型并排序
        df['links'] = pd.to_numeric(df['links'], errors='coerce').fillna(1)
        df = df.sort_values(by='links', ascending=False)
        
        data = df.head(15).to_dict(orient='records')
        print(f"   [成功] 提取到 {len(data)} 只强势个股。")
        return data

    except Exception as e:
        print(f"   [错误] 数据接口调用失败: {e}")
        return []

# ========== 3. AI 调用分析 ==========

def analyze_by_ai(stock_data):
    """交给豆包进行深度分析"""
    print(f"\n>>> 正在调用 AI (Endpoint: {ENDPOINT_ID}) 进行研判...")
    
    # 格式化输入数据
    stock_summary = ""
    for s in stock_data:
        stock_summary += (f"- {s.get('name')}({s.get('code')}): {s.get('links')}连板, "
                          f"行业:{s.get('industry')}, 换手:{s.get('turnover')}%\n")

    prompt = f"""
    你是资深A股短线策略专家。请基于以下最新的涨停板强势股数据进行分析：
    
    {stock_summary}

    分析要求：
    1. 【核心题材】概括当前最火的2-3个概念板块。
    2. 【龙头点睛】选出你认为最具备“妖股”潜质的1-2只标的并说明理由。
    3. 【情绪打分】给今日的市场赚钱效应打分(0-10分)。
    4. 【操作策略】针对上述连板股，给出明早竞价阶段的观察建议。
    
    回复要求：专业、干脆，使用 Markdown 格式。
    """

    headers = {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": ENDPOINT_ID,
        "messages": [
            {"role": "system", "content": "你是一个实战派游资，只讲盘面逻辑，不讲空话。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    try:
        resp = requests.post(ARK_API_URL, headers=headers, json=payload, timeout=60)
        res = resp.json()
        if "choices" in res:
            return res["choices"][0]["message"]["content"]
        return "AI 分析结果异常"
    except Exception as e:
        return f"AI 连接失败: {e}"

# ========== 4. 主程序 ==========

def main():
    start_time = time.time()
    print("="*50)
    print(f"   🚀 A股强势股 AI 自动分析系统 V4.0")
    print(f"   执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)

    # 1. 抓取硬核数据
    stocks = get_zt_data()
    
    if not stocks:
        print("\n[!] 流程中断：未能获取到任何涨停数据。")
        return

    # 2. 喂给 AI
    analysis_report = analyze_by_ai(stocks)

    # 3. 组装结果
    report_md = f"""# 📊 A股连板强势股 AI 研报
**分析基准：** 最近交易日涨停池 (TOP 15 连板)
**报告生成：** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
{analysis_report}

---
*风险提示：连板股波动剧烈，AI分析仅供参考。*
"""

    # 4. 保存与推送
    os.makedirs("report", exist_ok=True)
    f_path = f"report/ZT_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    with open(f_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    
    if WECOM_WEBHOOK:
        requests.post(WECOM_WEBHOOK, json={
            "msgtype": "markdown",
            "markdown": {"content": report_md}
        })
        print("\n✅ 微信推送报告成功！")

    print(f"\n[完成] 全流程耗时: {int(time.time() - start_time)}s")

if __name__ == "__main__":
    main()