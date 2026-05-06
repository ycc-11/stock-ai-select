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

# 模拟浏览器请求头
HEADERS = {
    "Referer": "https://finance.sina.com.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# ========== 2. 行情获取模块 ==========
def get_stock_info(market, code):
    """获取单只股票实时行情并打印明细"""
    try:
        url = f"http://hq.sinajs.cn/list={market}{code}"
        resp = requests.get(url, timeout=5, headers=HEADERS)
        
        # 处理编码问题
        content = resp.text
        if "var hq_str_" not in content:
            print(f"   [跳过] 代码 {market}{code}: 无效或未上市")
            return None

        # 解析新浪数据字符串
        data_str = content.split('"')[1]
        if not data_str:
            print(f"   [警告] 代码 {market}{code}: 停牌或数据为空")
            return None

        parts = data_str.split(",")
        name = parts[0]
        yesterday_close = float(parts[2])
        current_price = float(parts[3])
        
        # 计算涨幅
        pct_change = 0
        if yesterday_close > 0:
            pct_change = ((current_price - yesterday_close) / yesterday_close) * 100

        # 过滤垃圾股
        if "ST" in name or "退" in name:
            print(f"   [过滤] {code} {name}: 属于风险股，自动剔除")
            return None

        print(f"   [成功] {code} {name: <8} | 现价: {current_price: >7} | 涨幅: {pct_change: >6.2f}%")
        
        return {
            "code": code,
            "name": name,
            "price": round(current_price, 2),
            "change": round(pct_change, 2),
            "market": market
        }
    except Exception as e:
        print(f"   [错误] 获取 {code} 异常: {str(e)}")
        return None

# ========== 3. AI 逻辑驱动模块 ==========
def ask_doubao(prompt, log_title="AI调用"):
    """通用豆包接口调用"""
    print(f"\n>>> 正在启动 {log_title}...")
    if not DOUBAO_API_KEY:
        return "未配置API Key"

    headers = {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": ENDPOINT_ID,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}]  # 适配标准API格式
    }

    try:
        resp = requests.post(ARK_API_URL, headers=headers, json=payload, timeout=45)
        res = resp.json()
        
        # 兼容不同返回格式
        content = ""
        if "choices" in res:
            content = res["choices"][0]["message"]["content"]
        elif "output" in res:
            content = res["output"][0]["content"][0].get("text", "")
            
        return content.strip()
    except Exception as e:
        print(f"   [异常] {log_title}失败: {str(e)}")
        return ""

def get_hot_stock_list():
    """第一步：让AI列出当前的热门备选股"""
    prompt = """请列出当前A股市场中最热门的50只领涨板块个股，以及近期连续涨停的30只强势股。
    要求：
    1. 只输出代码列表，格式如：sh600000, sz000001
    2. 不要输出任何中文说明，用逗号分隔。
    3. 尽量覆盖半导体、低空经济、AI、机器人等近期风口。"""
    
    raw_response = ask_doubao(prompt, "获取AI预选池")
    # 正则提取
    codes = re.findall(r'(sh|sz)\d{6}', raw_response.lower())
    # 去重
    unique_codes = list(set(re.findall(r'(sh|sz)(\d{6})', raw_response.lower())))
    print(f"--- AI 推荐了 {len(unique_codes)} 只潜在关注个股 ---")
    return unique_codes

# ========== 4. 核心执行流程 ==========
def get_final_stock_pool():
    """第二步：结合行情筛选真正值得分析的股票"""
    raw_list = get_hot_stock_list()
    if not raw_list:
        print("!!! 无法获取AI推荐列表，启用备选库")
        return [
            {"code": "600519", "name": "贵州茅台", "price": 1700.0, "change": 0.5},
            {"code": "002594", "name": "比亚迪", "price": 280.0, "change": 1.2}
        ]

    print("\n>>> 开始进行实时行情校验（筛选值得买入/卖出的标的）...")
    valid_stocks = []
    for market, code in raw_list:
        info = get_stock_info(market, code)
        if info:
            # 筛选逻辑：排除涨幅过大（如>9%）防止追高，排除跌幅过大（如<-7%）防止踩雷
            if -7 <= info['change'] <= 9:
                valid_stocks.append(info)
        
        # 限制单次分析数量，保证报告质量
        if len(valid_stocks) >= 15:
            break
        # 稍微延迟防止触发接口频率限制
        time.sleep(0.1)

    print(f"--- 筛选完成：共 {len(valid_stocks)} 只个股进入最终分析环节 ---")
    return valid_stocks

# ========== 5. 报告生成与发送 ==========
def generate_final_report(stocks):
    """最终汇总分析"""
    # 1. 深度分析个股
    stock_context = json.dumps(stocks, ensure_ascii=False)
    analysis_prompt = f"""针对以下实时行情数据，请以专业分析师角度进行研判。
    数据：{stock_context}
    
    格式要求（逐个分析）：
    【代码+名称】
    📊 板块定位：
    💡 实时操作：(买入/观望/减持)
    📌 核心逻辑：(结合价格和涨幅说明)
    """
    analysis_result = ask_doubao(analysis_prompt, "深度分析个股")

    # 2. 市场宏观信息
    market_prompt = "总结今日A股市场三大热门板块、整体资金流向及重大政策利好，要求排版精简适合手机阅读。"
    market_result = ask_doubao(market_prompt, "获取宏观环境")

    # 3. 组装
    report = f"【📊 A股AI智能研报 - {datetime.now().strftime('%Y-%m-%d')}】\n"
    report += "\n" + "="*15 + " 个股深度研判 " + "="*15 + "\n"
    report += analysis_result + "\n\n"
    report += "="*15 + " 市场热点观察 " + "="*15 + "\n"
    report += market_result
    
    return report

def send_to_wechat(content):
    if not WECOM_WEBHOOK:
        print("\n[跳过] 未配置微信Webhook，仅本地保存")
        return
    try:
        requests.post(WECOM_WEBHOOK, json={
            "msgtype": "text",
            "text": {"content": content}
        }, timeout=10)
        print("\n[通知] 微信报告推送成功！")
    except Exception as e:
        print(f"\n[失败] 微信推送异常: {e}")

def save_local_report(content):
    os.makedirs("report", exist_ok=True)
    filename = f"report/Report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[文件] 报告已保存至: {filename}")

# ========== 6. 主程序入口 ==========
if __name__ == "__main__":
    start_time = time.time()
    print("="*40)
    print("   🚀 A股 AI 智能选股系统 (热点驱动版) 启动")
    print("="*40)

    # 第一步 & 第二步：AI预选 + 实时行情筛选
    selected_stocks = get_final_stock_pool()

    # 第三步：生成研报
    final_report = generate_final_report(selected_stocks)

    # 第四步：输出与推送
    save_local_report(final_report)
    send_to_wechat(final_report)

    end_time = time.time()
    print(f"\n[完成] 全流程执行完毕，耗时 {int(end_time - start_time)}s")