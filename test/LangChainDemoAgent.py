import os
import getpass
import asyncio
import nest_asyncio
from typing import List
from dotenv import load_dotenv
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool as langchain_tool
from langchain.agents import create_tool_calling_agent, AgentExecutor

# --- 配置 API 密钥 ---
# 提示用户安全输入 API 密钥并设置为环境变量
os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter your Google API key: ")
os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")

try:
    # 需要支持函数/工具调用的模型
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    print(f"语言模型已初始化: {llm.model}")
except Exception as e:
    print(f"初始化语言模型时出错: {e}")
    llm = None


# --- 定义工具 ---
@langchain_tool
def search_information(query: str) -> str:
    """
    提供关于给定主题的事实信息。使用此工具查找类似
    '法国首都' 或 '伦敦天气' 等问题的答案。
    """
    print(f"\n--- 工具调用: search_information，查询: '{query}' ---")

    # 模拟搜索工具，使用预定义结果字典
    simulated_results = {
        "weather in london": "伦敦当前天气多云，气温 15°C。",
        "capital of france": "法国的首都是巴黎。",
        "population of earth": "地球估计人口约 80 亿。",
        "tallest mountain": "珠穆朗玛峰是海拔最高的山峰。",
        "default": f"关于 '{query}' 的模拟搜索结果：未找到具体信息，但这个话题似乎很有趣。",
    }

    result = simulated_results.get(query.lower(), simulated_results["default"])
    print(f"--- 工具结果: {result} ---")
    return result


tools = [search_information]


# --- 创建工具调用 Agent ---
if llm:
    # 此提示词模板需要 `agent_scratchpad` 占位符，用于 Agent 内部步骤
    agent_prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个有用的助手。"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    # 创建 Agent，将 LLM、工具和提示词绑定在一起
    agent = create_tool_calling_agent(llm, tools, agent_prompt)

    # AgentExecutor 是运行时，用于调用 Agent 并执行选定的工具
    # 此处不需要 'tools' 参数，因为它们已经绑定到 Agent
    agent_executor = AgentExecutor(agent=agent, verbose=True, tools=tools)


async def run_agent_with_tool(query: str):
    """使用查询调用 Agent 执行器并打印最终响应。"""
    print(f"\n--- 使用查询运行 Agent: '{query}' ---")
    try:
        response = await agent_executor.ainvoke({"input": query})
        print("\n--- 最终 Agent 响应 ---")
        print(response["output"])
    except Exception as e:
        print(f"\nAgent 执行过程中发生错误: {e}")


async def main():
    """并发运行所有 Agent 查询。"""
    tasks = [
        run_agent_with_tool("法国的首都是什么？"),
        run_agent_with_tool("伦敦的天气怎么样？"),
        run_agent_with_tool("给我讲讲关于狗的事情。"),  # 应触发默认工具响应
    ]
    await asyncio.gather(*tasks)


nest_asyncio.apply()
asyncio.run(main())
