"""
LangGraph Agent 版本
====================
将 LangChain Agent 改造成 LangGraph 状态机模式

核心区别：
- LangChain Agent: AgentExecutor 内部自动循环
- LangGraph: 显式定义节点和边，状态机控制流程

执行步骤：
1. 定义 AgentState（状态结构）
2. 定义节点函数（LLM 决策、工具执行）
3. 定义边（条件路由）
4. 构建 StateGraph
5. 编译执行
"""

import os
import getpass
from typing import TypedDict, Literal, Union
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool as langchain_tool
from langgraph.graph import StateGraph, END

# --- 配置 ---
os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter your Google API key: ")

try:
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    print(f"语言模型已初始化: {llm.model}")
except Exception as e:
    print(f"初始化语言模型时出错: {e}")
    llm = None


# --- 定义工具 ---
@langchain_tool
def search_information(query: str) -> str:
    """提供关于给定主题的事实信息。"""
    print(f"\n[工具执行] search_information(query='{query}')")

    simulated_results = {
        "weather in london": "伦敦当前天气多云，气温 15°C。",
        "capital of france": "法国的首都是巴黎。",
        "population of earth": "地球估计人口约 80 亿。",
        "default": f"未找到关于 '{query}' 的具体信息。",
    }

    result = simulated_results.get(query.lower(), simulated_results["default"])
    print(f"[工具结果] {result}")
    return result


tools = [search_information]


# ============================================================
# 步骤 1: 定义 AgentState
# ============================================================
class AgentState(TypedDict):
    """
    Agent 状态：在节点间传递的共享数据
    """
    messages: list                    # 对话历史（含 LLM 和 Tool 消息）
    tool_calls: list                 # LLM 决定调用的工具列表
    tool_results: list               # 工具执行结果
    final_answer: str                # 最终回答


# ============================================================
# 步骤 2: 定义节点函数
# ============================================================

def llm_node(state: AgentState) -> AgentState:
    """
    节点 1: LLM 决策节点

    职责：
    - 读取当前 messages
    - 调用 LLM（绑定工具）
    - 返回需要调用的工具（放入 tool_calls）
    """
    print("\n[节点] llm_node - LLM 决策")

    # 将工具绑定到 LLM
    llm_with_tools = llm.bind_tools(tools)

    # 调用 LLM
    last_message = state["messages"][-1] if state["messages"] else ""
    response = llm_with_tools.invoke(last_message)

    print(f"[LLM 响应] {response.content}")
    print(f"[LLM 工具调用] {response.tool_calls}")

    # 返回更新状态
    return {
        "messages": state["messages"] + [response],
        "tool_calls": response.tool_calls or [],
        "tool_results": [],  # 清空之前的工具结果
        "final_answer": "",
    }


def tool_node(state: AgentState) -> AgentState:
    """
    节点 2: 工具执行节点

    职责：
    - 读取 tool_calls
    - 执行对应工具
    - 将结果存入 tool_results
    """
    print("\n[节点] tool_node - 工具执行")

    tool_calls = state["tool_calls"]
    tool_results = []

    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # 查找并执行工具
        selected_tool = None
        for t in tools:
            if t.name == tool_name:
                selected_tool = t
                break

        if selected_tool:
            result = selected_tool.invoke(tool_args)
            tool_results.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result
            })
            print(f"[执行工具] {tool_name} -> {result}")

    # 将工具结果作为消息加入 history
    tool_messages = [
        ToolMessage(content=r["result"], tool_call_id=tool_call["id"])
        for r, tool_call in zip(tool_results, tool_calls)
    ]

    return {
        "messages": state["messages"] + tool_messages,
        "tool_results": tool_results,
    }


def should_continue(state: AgentState) -> Literal["tool_node", "END"]:
    """
    边 1: 判断是否继续（条件边）

    返回：
    - "tool_node": 如果 LLM 要求调用工具
    - END: 如果 LLM 直接回答
    """
    print("\n[边] should_continue - 判断是否继续")

    if state["tool_calls"]:
        print("[决策] 有工具调用，继续执行工具")
        return "tool_node"
    else:
        print("[决策] 无工具调用，结束")
        return END


def should_end(state: AgentState) -> Literal["llm_node", "END"]:
    """
    边 2: 判断是否再次调用 LLM

    返回：
    - "llm_node": 如果刚执行了工具，需要再次调用 LLM
    - END: 如果已经有最终回答
    """
    print("\n[边] should_end - 判断是否再次 LLM 调用")

    if state["tool_results"]:
        print("[决策] 刚执行了工具，再次调用 LLM 生成回答")
        return "llm_node"
    else:
        print("[决策] 流程结束")
        return END


# ============================================================
# 步骤 3: 构建 StateGraph
# ============================================================

def create_agent_graph():
    """
    创建 Agent 状态机图

    图结构：
    START -> llm_node -> should_continue
                           │
               ┌───────────┴───────────┐
               ↓                       ↓
          tool_node              (END)
               │
               ↓
         should_end
               │
          ┌────┴────┐
          ↓         ↓
      llm_node    (END)
    """

    # 创建状态图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("llm_node", llm_node)
    workflow.add_node("tool_node", tool_node)

    # 设置入口点
    workflow.set_entry_point("llm_node")

    # 添加条件边
    workflow.add_conditional_edges(
        "llm_node",
        should_continue,
        {
            "tool_node": "tool_node",  # 有工具调用
            END: END                    # 无工具调用，结束
        }
    )

    workflow.add_conditional_edges(
        "tool_node",
        should_end,
        {
            "llm_node": "llm_node",  # 再调用 LLM
            END: END                  # 结束
        }
    )

    # 编译图
    return workflow.compile()


# ============================================================
# 步骤 4: 执行入口
# ============================================================

async def run_agent_graph(query: str):
    """运行 LangGraph Agent"""
    print(f"\n{'='*60}")
    print(f"用户输入: {query}")
    print(f"{'='*60}\n")

    # 创建并编译图
    graph = create_agent_graph()

    # 初始化状态
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "tool_calls": [],
        "tool_results": [],
        "final_answer": "",
    }

    # 执行图
    result = await graph.ainvoke(initial_state)

    # 打印最终结果
    print(f"\n{'='*60}")
    print("最终回答:")
    print(f"{'='*60}")

    # 从 messages 中提取 LLM 的最终回答
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            print(msg.content)
            break


async def main():
    """并发运行多个查询"""
    queries = [
        "法国的首都是什么？",
        "伦敦的天气怎么样？",
    ]

    tasks = [run_agent_graph(q) for q in queries]
    for task in tasks:
        await task


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
