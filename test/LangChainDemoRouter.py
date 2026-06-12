# Copyright (c) 2025 Marco Fago
# https://www.linkedin.com/in/marco-fago/
#
# This code is licensed under the MIT License.
# See the LICENSE file in the repository for the full license text.
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableBranch

# --- 配置 ---
# 确保已设置 API 密钥环境变量（例如 GOOGLE_API_KEY）
try:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    print(f"语言模型已初始化: {llm.model}")
except Exception as e:
    print(f"初始化语言模型时出错: {e}")
    llm = None


# --- 定义模拟子代理处理器（相当于 ADK sub_agents） ---
def booking_handler(request: str) -> str:
    """模拟预订代理处理请求。"""
    print("\n--- 委托给预订处理器 ---")
    return f"预订处理器处理了请求: '{request}'。结果: 模拟预订操作。"


def info_handler(request: str) -> str:
    """模拟信息代理处理请求。"""
    print("\n--- 委托给信息处理器 ---")
    return f"信息处理器处理了请求: '{request}'。结果: 模拟信息检索。"


def unclear_handler(request: str) -> str:
    """处理无法委托的请求。"""
    print("\n--- 处理不明确的请求 ---")
    return f"协调器无法委托请求: '{request}'。请明确说明。"


# --- 定义协调器路由链（相当于 ADK 协调器的指令） ---
# 此链决定应将请求委托给哪个处理器。
coordinator_router_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """分析用户的请求，确定应由哪个专业处理器处理。
 - 如果请求与预订机票或酒店相关，输出 'booker'。
 - 对于所有其他一般信息问题，输出 'info'。
 - 如果请求不明确或不属于任一类别，输出 'unclear'。
 只输出一个词: 'booker'、'info' 或 'unclear'。"""
    ),
    ("user", "{request}")
])

if llm:
    coordinator_router_chain = coordinator_router_prompt | llm | StrOutputParser()


# --- 定义委托逻辑（相当于 ADK 基于 sub_agents 的自动流程） ---
# 使用 RunnableBranch 根据路由链的输出进行路由。
# 为 RunnableBranch 定义分支。
branches = {
    "booker": RunnablePassthrough.assign(
        output=lambda x: booking_handler(x['request']['request'])
    ),
    "info": RunnablePassthrough.assign(
        output=lambda x: info_handler(x['request']['request'])
    ),
    "unclear": RunnablePassthrough.assign(
        output=lambda x: unclear_handler(x['request']['request'])
    ),
}

# 创建 RunnableBranch。它接收路由链的输出，
# 并将原始输入（'request'）路由到相应的处理器。
delegation_branch = RunnableBranch(
    (lambda x: x['decision'].strip() == 'booker', branches["booker"]),  # 添加了 .strip()
    (lambda x: x['decision'].strip() == 'info', branches["info"]),  # 添加了 .strip()
    branches["unclear"]  # 'unclear' 或其他输出的默认分支
)

# 将路由链和委托分支组合成单个可运行对象。
# 路由链的输出（'decision'）与原始输入（'request'）一起传递给 delegation_branch。
coordinator_agent = {
    "decision": coordinator_router_chain,
    "request": RunnablePassthrough()
} | delegation_branch | (lambda x: x['output'])  # 提取最终输出


# --- 示例用法 ---
def main():
    if not llm:
        print("\n因 LLM 初始化失败，跳过执行。")
        return

    print("--- 运行预订请求 ---")
    request_a = "帮我预订一张去伦敦的机票。"
    result_a = coordinator_agent.invoke({"request": request_a})
    print(f"最终结果 A: {result_a}")

    print("\n--- 运行信息请求 ---")
    request_b = "意大利的首都是哪里？"
    result_b = coordinator_agent.invoke({"request": request_b})
    print(f"最终结果 B: {result_b}")

    print("\n--- 运行不明确的请求 ---")
    request_c = "给我讲讲量子物理学。"
    result_c = coordinator_agent.invoke({"request": request_c})
    print(f"最终结果 C: {result_c}")


if __name__ == "__main__":
    main()
