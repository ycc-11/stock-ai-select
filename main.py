import os
import json
import requests
import re
import time
from datetime import datetime

# ========== 1. 环境配置 ==========
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")
ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
ENDPOINT_ID = "ep-20260506125835-cc6j5"

# 浏览器伪装头
HEADERS = {
    "Referer": "https://finance.sina.com.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

# ========== 2. 工具函数 ==========

def ask_doubao(prompt, log_title="AI调用"):
    """底层调用豆包AI接口"""
    if not DOUBAO_API_KEY:
        print(f"   [!] 错误: 未配置 API KEY")
        return ""

    headers = {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": ENDPOINT_ID,
        "messages": [
            {"role": "system", "content": "你是一个专业的金融数据分析师，严谨且专业。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4  # 较低随机性保证代码输出稳定
    }

    try:
        resp = requests.post(ARK_API_URL, headers=headers, json=payload, timeout=60)
        res = resp.json()
        if "choices" in res:
            return res["choices"][0]["message"]["content"].strip()
        return ""
    except Exception as e:
        print(f"   [!] {log_title} 请求异常: {e}")
        return ""

def get_stock_info(market, code):
    """实时抓取新浪财经行情"""
    try:
        url = f"http://hq.sinajs.cn/list={market}{code}"
        resp = requests.get(url, timeout=5, headers=HEADERS)
        # 必须使用 gbk 解码，否则中文名会乱码
        content = resp.content.decode('gbk')
        
        if "var hq_str_" not in content:
            return None

        raw_data = content.split('"')[1]
        if not raw_data: return None
        
        parts = raw_data.split(",")
        if len(parts) < 30: return None

        name = parts[0]
        y_close = float(parts[2]) # 昨收
        now_price = float(parts[3]) # 现价
        
        if y_close == 0: return None
        pct_chg = ((now_price - y_close) / y_close) * 100

        # 打印行情日志
        print(f"   [数据同步] {code} {name: <8} | 价格: {now_price: >8.2f} | 涨幅: {pct_chg: >6.2f}%")
        
        return {
            "code": code, "name": name, 
            "price": round(now_price, 2), 
            "change": round(pct_chg, 2),
            "market": market
        }
    except:
        return None

# ========== 3. 核心业务逻辑 ==========

def get_hot_stock_pool():
    """让AI根据当前市场热点生成个股代码池"""
    print("\n>>> 正在分析市场热点板块并筛选领涨个股...")
    
    prompt = """
    请分析今日A股市场，先列出当前最热门的3-5个板块。
    然后，针对每个板块列出3-5只代表性的龙头股或强势股。
    
    最后，请【只汇总】所有股票代码，要求：
    1. 格式为：前缀+代码（如 sh600519, sz000001）。
    2. 使用逗号分隔，不要有任何中文解释。
    3. 总数不少于 20 只。
    """
    
    raw_text = ask_doubao(prompt, "获取AI代码池")
    
    # 提取 sh/sz + 6位数字
    matches = re.findall(r'(sh|sz)(\d{6})', raw_text.lower())
    
    unique_pool = []
    seen = set()
    for m, c in matches:
        if c not in seen:
            unique_pool.append((m, c))
            seen.add(c)
    
    # 兜底逻辑：如果 AI 没加前缀，强行提取纯 6 位数字
    if len(unique_pool) < 5:
        num_matches = re.findall(r'\b(\d{6})\b', raw_text)
        for c in num_matches:
            if c not in seen:
                m = "sh" if c.startswith(('60', '68')) else "sz"
                unique_pool.append((m, c))
                seen.add(c)

    print(f"--- AI 推荐池扫描完毕，共获取 {len(unique_pool)} 个有效标的 ---")
    return unique_pool

def generate_report():
    """主流程：选股 -> 过滤 -> 分析 -> 推送"""
    start_time = time.time()
    
    # 1. AI 预选
    raw_pool = get_hot_stock_pool()
    if not raw_pool:
        print("!!! 未能获取个股池，程序中止")
        return

    # 2. 实时行情过滤（只保留有成交、未停牌的）
    print("\n>>> 正在穿透新浪行情接口进行实时校验...")
    valid_stocks = []
    for market, code in raw_pool:
        info = get_stock_info(market, code)
        if info:
            valid_stocks.append(info)
        if len(valid_stocks) >= 12: # 限制分析数量，保证 AI 回复质量
            break
        time.sleep(0.1)

    # 3. 针对过滤后的个股进行深度研判
    if not valid_stocks:
        print("!!! 实时行情校验失败，无可分析标的")
        return

    print("\n>>> 正在调用 AI 进行深度策略研判...")
    stock_list_str = json.dumps(valid_stocks, ensure_ascii=False)
    analysis_prompt = f"""
    请作为资深策略师，分析以下个股的实时行情数据：
    {stock_list_str}
    
    输出要求：
    1. 简要评价今日大盘情绪。
    2. 对上述个股逐一分析：给出【所属板块】、【操作建议】（短线参与、分批低吸、暂时观望）和【核心逻辑】。
    3. 排版整洁，使用 Markdown 格式。
    """
    
    final_analysis = ask_doubao(analysis_prompt, "深度分析")

    # 4. 组装与输出
    report_content = f"""# 📊 A股AI智能选股研报
**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
{final_analysis}

---
*温馨提示：本报告由AI自动生成，不构成投资建议，股市有风险，入市需谨慎。*
"""

    # 保存本地
    os.makedirs("report", exist_ok=True)
    file_path = f"report/Analysis_{datetime.now().strftime('%H%M')}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    # 微信推送
    if WECOM_WEBHOOK:
        try:
            requests.post(WECOM_WEBHOOK, json={
                "msgtype": "markdown",
                "markdown": {"content": report_content}
            })
            print("\n✅ 微信推送成功！")
        except:
            print("\n❌ 微信推送失败")

    print(f"\n=== 全流程完成，总耗时: {int(time.time() - start_time)}s ===")
    print(f"📄 报告已保存至: {file_path}")

# ========== 4. 执行入口 ==========
if __name__ == "__main__":
    print("="*50)
    print("      A股 AI 智能选股系统 v3.0 (行情驱动型)")
    print("="*50)
    generate_report()