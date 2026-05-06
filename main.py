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

# ========== 2. 行情数据接口 (基于AkShare) ==========

def get_today_zt_pool():
    """获取今日涨停板数据池"""
    print("\n>>> 正在从数据接口获取最新交易日涨停榜...")
    try:
        # 获取涨停池数据 (东财接口)
        df = ak.stock_zt_pool_em()
        if df.empty:
            print("   [!] 未获取到涨停数据（可能是非交易时段）")
            return []
        
        # 筛选核心字段：代码, 名称, 最新价, 涨幅, 成交额, 换手率, 连板数, 所属行业
        # 字段名转换（AkShare版本不同字段名可能微调）
        df = df[['代码', '名称', '最后封板时间', '换手率', '连板数', '所属行业']]
        
        # 排序：优先按连板数降序
        df = df.sort_values(by='连板数', ascending=False)
        
        print(f"   [成功] 获取到 {len(df)} 只涨停个股，正在提取强势标的...")
        return df.head(20).to_dict(orient='records')
    except Exception as e:
        print(f"   [错误] 获取行情失败: {e}")
        return []

# ========== 3. AI 调用模块 ==========

def ask_doubao_analyst(stock_data):
    """将数据发送给豆包进行量化分析"""
    print("\n>>> 正在将实时榜单发送至 AI 进行策略分析...")
    
    # 构建结构化的分析上下文
    context = ""
    for s in stock_data:
        context += (f"股票: {s['名称']}({s['代码']}) | 连板数: {s['连板数']} | "
                    f"换手率: {s['换手率']}% | 所属行业: {s['所属行业']} | 封板时间: {s['最后封板时间']}\n")

    prompt = f"""
    你是一名顶级A股短线游资操盘手。以下是今日市场表现最强劲的连板股票数据：
    {context}

    请执行以下任务：
    1. 归纳当前市场最热门的【核心主线板块】。
    2. 对每只股票进行打分（1-10分，10分为极度推荐）。
    3. 给出【买入/观望/卖出】的具体操作建议。
    4. 识别哪些股票存在“龙回头”机会或“接力”风险。

    要求：排版清晰，专业且毒辣，不讲废话。
    """

    headers = {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": ENDPOINT_ID,
        "messages": [
            {"role": "system", "content": "你是一个只看数据和逻辑的短线交易专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4
    }

    try:
        resp = requests.post(ARK_API_URL, headers=headers, json=payload, timeout=60)
        res = resp.json()
        return res["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"AI 分析失败: {e}"

# ========== 4. 执行流程 ==========

def main():
    start_time = time.time()
    print("="*50)
    print(f"   🚀 A股强势股数据驱动分析系统 - {datetime.now().strftime('%Y-%m-%d')}")
    print("="*50)

    # 1. 获取最真实、最新的涨停榜数据
    zt_stocks = get_today_zt_pool()
    
    if not zt_stocks:
        print("\n[!] 无法获取实时数据，程序退出。请确保在交易时段或确认AkShare接口正常。")
        return

    # 2. 交给 AI 进行多维度研判
    analysis_report = ask_doubao_analyst(zt_stocks)

    # 3. 结果汇总
    final_content = f"""# 📈 A股强势股 AI 动态分析报告
**数据时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**数据来源：** 实时行情涨停池 (连板优先)

---
{analysis_report}

---
*注：数据取自今日涨停最强势的 Top 20 标的。*
"""

    # 4. 保存与推送
    os.makedirs("report", exist_ok=True)
    filename = f"report/ZT_Analysis_{datetime.now().strftime('%H%M')}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_content)
    
    if WECOM_WEBHOOK:
        requests.post(WECOM_WEBHOOK, json={
            "msgtype": "markdown",
            "markdown": {"content": final_content}
        })
        print("\n✅ 推送微信成功！")

    print(f"\n[完成] 全流程执行完毕，耗时 {int(time.time() - start_time)}s")

if __name__ == "__main__":
    main()