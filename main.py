import os
import json
import requests
import re
import time
from datetime import datetime

# ========== 1. 配置中心 ==========
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")
ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
ENDPOINT_ID = "ep-20260506125835-cc6j5"

HEADERS = {
    "Referer": "https://finance.sina.com.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ========== 2. 核心清洗函数 (新增) ==========

def extract_codes(text):
    """
    从任何文本中提取 A 股代码。
    支持格式：sh600000, 000001.sz, 600519 (带前缀或纯数字)
    """
    found = []
    seen = set()
    
    # 1. 匹配带前缀的格式 (sh600000, sz000001)
    prefix_matches = re.findall(r'(sh|sz)(\d{6})', text.lower())
    for m, c in prefix_matches:
        if c not in seen:
            found.append((m, c))
            seen.add(c)
            
    # 2. 匹配纯 6 位数字 (兜底：如果 AI 没给前缀)
    # 排除掉已经是 sh/sz 匹配过的数字
    digit_matches = re.findall(r'\b(\d{6})\b', text)
    for c in digit_matches:
        if c not in seen:
            # A股规律：60/68开头是沪市，00/30开头是深市
            if c.startswith(('60', '68', '90')):
                m = "sh"
            else:
                m = "sz"
            found.append((m, c))
            seen.add(c)
            
    return found

# ========== 3. AI 调用模块 ==========

def ask_doubao(prompt, log_title="AI调用"):
    if not DOUBAO_API_KEY:
        print("   [!] 错误: 未配置 API KEY")
        return ""

    headers = {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": ENDPOINT_ID,
        "messages": [
            {"role": "system", "content": "你是一个金融数据接口。请严格执行指令，直接输出数据，不要输出任何开场白或解释。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2 # 极低随机性，防止 AI 话多
    }

    try:
        resp = requests.post(ARK_API_URL, headers=headers, json=payload, timeout=60)
        res = resp.json()
        
        # 兼容不同版本的返回结构
        if "choices" in res:
            return res["choices"][0]["message"]["content"].strip()
        elif "output" in res:
            return res["output"][0]["content"][0].get("text", "").strip()
        return ""
    except Exception as e:
        print(f"   [!] {log_title} 异常: {e}")
        return ""

def get_hot_stock_pool():
    """改进版：分层 Prompt 确保代码产出"""
    print("\n>>> 正在抓取今日 A 股热点标的...")
    
    # 极其直白的指令，防止 AI 产生安全顾虑而拒绝回答
    prompt = """
    当前时间：2026年5月。
    请列出目前A股市场中成交量最大、最热门的30只股票代码。
    要求：直接列出代码即可，用逗号隔开。
    例如：sh600519, sz002594, sh601318...
    """
    
    raw_text = ask_doubao(prompt, "获取AI预选池")
    
    # 打印部分 AI 返回内容以便调试
    print(f"   [AI 回复片段]: {raw_text[:60].replace(chr(10), ' ')}...")
    
    unique_pool = extract_codes(raw_text)
    print(f"--- 成功识别 {len(unique_pool)} 个有效代码 ---")
    return unique_pool

# ========== 4. 行情与分析模块 ==========

def get_stock_info(market, code):
    try:
        url = f"http://hq.sinajs.cn/list={market}{code}"
        resp = requests.get(url, timeout=5, headers=HEADERS)
        content = resp.content.decode('gbk')
        
        if "var hq_str_" not in content: return None
        data = content.split('"')[1]
        if not data: return None
        
        p = data.split(",")
        name, y_close, now = p[0], float(p[2]), float(p[3])
        
        if y_close == 0: return None
        pct = round(((now - y_close) / y_close) * 100, 2)
        
        print(f"   [行情] {code} {name: <8} | {now: >8.2f} | {pct: >6}%")
        return {"code": code, "name": name, "price": now, "change": pct, "market": market}
    except:
        return None

def run_main():
    start_time = time.time()
    
    # 1. 选股
    pool = get_hot_stock_pool()
    if not pool:
        # 如果还是没有，硬编码几个热门股作为系统演示，防止程序中止
        print("   [!] AI 未能提供数据，使用系统默认热点库...")
        pool = [("sh", "600519"), ("sz", "002594"), ("sh", "601318"), ("sz", "000858"), ("sz", "000651")]

    # 2. 实时校验
    print("\n>>> 穿透行情接口校验中...")
    valid_list = []
    for m, c in pool:
        info = get_stock_info(m, c)
        if info:
            valid_list.append(info)
        if len(valid_list) >= 12: break
        time.sleep(0.1)

    # 3. 深度分析
    print("\n>>> 生成深度分析报告...")
    stocks_str = "\n".join([f"{s['name']}({s['code']}):现价{s['price']}, 涨幅{s['change']}%" for s in valid_list])
    analysis_prompt = f"请针对以下个股行情给出简短的投资逻辑和今日操作建议：\n{stocks_str}"
    report_body = ask_doubao(analysis_prompt, "生成报告")

    # 4. 保存与推送
    final_report = f"# 📊 A股 AI 选股研报\n生成日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{report_body}"
    
    os.makedirs("report", exist_ok=True)
    with open(f"report/Analysis_{datetime.now().strftime('%H%M')}.md", "w", encoding="utf-8") as f:
        f.write(final_report)
    
    if WECOM_WEBHOOK:
        requests.post(WECOM_WEBHOOK, json={"msgtype": "markdown", "markdown": {"content": final_report}})
        print("\n✅ 推送完成！")

    print(f"\n[完成] 全耗时: {int(time.time() - start_time)}s")

if __name__ == "__main__":
    print("="*50)
    print("      A股 AI 智能选股系统 v3.1 (稳定版)")
    print("="*50)
    run_main()