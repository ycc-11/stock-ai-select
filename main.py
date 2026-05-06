import os
import json
import requests
from datetime import datetime
from openai import OpenAI, AuthenticationError

# ========== 环境变量 ==========
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")

# ========== 股票池 ==========
def get_stock_pool():
    return [
        {"code": "000001", "name": "平安银行"},
        {"code": "600036", "name": "招商银行"},
        {"code": "601318", "name": "中国平安"},
        {"code": "000333", "name": "格力电器"},
        {"code": "600519", "name": "贵州茅台"},
    ]

# ========== 豆包 AI 分析（带详细日志 + 密钥错误提示） ==========
def ai_analyze(stocks):
    print("\n=== 开始调用豆包 AI ===")

    if not DOUBAO_API_KEY:
        print("❌ 错误：未配置 DOUBAO_API_KEY 环境变量")
        return "未配置豆包API密钥"

    print(f"✅ 已加载 API 密钥：{DOUBAO_API_KEY[:10]}...")

    try:
        client = OpenAI(
            api_key=DOUBAO_API_KEY,
            base_url="https://ark.cn-beijing.volces.com/api/v1"
        )
        print("✅ 豆包客户端初始化成功")

        prompt = f"""你是A股专业分析师，请从以下股票中精选5只：
{json.dumps(stocks, ensure_ascii=False)}

要求：简洁，列出代码、名称、推荐逻辑。
"""

        print("✅ 已发送请求到豆包 AI...")
        response = client.chat.completions.create(
            model="ep-20250318150347-29fwl",  # 通用免费模型
            messages=[{"role": "user", "content": prompt}],
            timeout=20
        )
        print("✅ 豆包 AI 返回成功！")
        return response.choices[0].message.content.strip()

    except AuthenticationError:
        print("❌ 认证失败：**豆包 API 密钥错误或无效**")
        return "错误：豆包API密钥不正确"
    except Exception as e:
        print(f"❌ 调用失败：{str(e)[:100]}")
        return "豆包AI调用失败，使用默认股票列表\n" + "\n".join([f"{s['code']} {s['name']}" for s in stocks[:5]])

# ========== 微信推送 ==========
def send_wechat(content):
    print("\n=== 开始推送微信 ===")
    if not WECOM_WEBHOOK:
        print("❌ 未配置 WECOM_WEBHOOK，跳过推送")
        return

    try:
        requests.post(WECOM_WEBHOOK, json={
            "msgtype": "text",
            "text": {"content": f"【A股豆包AI选股】\n{content}"}
        }, timeout=10)
        print("✅ 微信推送成功！")
    except:
        print("❌ 微信推送失败")

# ========== 保存报告（已修复） ==========
def save_report(content):
    print("\n=== 保存报告 ===")
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("report", exist_ok=True)
    with open(f"report/{today}.md", "w", encoding="utf-8") as f:
        f.write(f"# A股AI选股 {today}\n\n{content}")
    print("✅ 报告已保存")

# ========== 主程序 ==========
if __name__ == "__main__":
    print("=== A股智能选股程序启动 ===")
    stocks = get_stock_pool()
    print("✅ 股票池加载完成")

    result = ai_analyze(stocks)
    save_report(result)
    send_wechat(result)

    print("\n=== ✅ 全部任务完成 ===")