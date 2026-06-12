"""
Google ADK 逻辑的 LangChain 实现
================================
使用 LangChain 的 RunnableParallel 实现并行研究与合并流程。

执行步骤：
1. 定义三个并行研究链（可再生能源、电动汽车、碳捕获）
2. 使用 RunnableParallel 并发执行三个研究链
3. 将结果通过管道传入合并链
4. 合并链整合所有研究结果生成最终报告
"""

import os
from typing import TypedDict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable, RunnableParallel, RunnablePassthrough

# --- 配置 ---
# 确保已设置 API 密钥环境变量
try:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
except Exception as e:
    print(f"初始化语言模型时出错: {e}")
    llm = None


# --- 定义状态结构 ---
class ResearchState(TypedDict):
    """研究状态：存储各主题的研究结果"""
    renewable_energy_result: str
    ev_technology_result: str
    carbon_capture_result: str


# --- 步骤 1: 定义三个并行研究链 ---
# 每个研究链独立执行，通过 output_key 将结果存入状态

# 研究员 1：可再生能源
research_renewable_chain: Runnable = (
    ChatPromptTemplate.from_messages([
        ("system", """You are an AI Research Assistant specializing in energy.
Research the latest advancements in 'renewable energy sources'.
Summarize your key findings concisely (1-2 sentences).
Output *only* the summary."""),
        ("user", "Research topic: {topic}"),
    ])
    | llm
    | StrOutputParser()
)

# 研究员 2：电动汽车
research_ev_chain: Runnable = (
    ChatPromptTemplate.from_messages([
        ("system", """You are an AI Research Assistant specializing in transportation.
Research the latest developments in 'electric vehicle technology'.
Summarize your key findings concisely (1-2 sentences).
Output *only* the summary."""),
        ("user", "Research topic: {topic}"),
    ])
    | llm
    | StrOutputParser()
)

# 研究员 3：碳捕获
research_carbon_chain: Runnable = (
    ChatPromptTemplate.from_messages([
        ("system", """You are an AI Research Assistant specializing in climate solutions.
Research the current state of 'carbon capture methods'.
Summarize your key findings concisely (1-2 sentences).
Output *only* the summary."""),
        ("user", "Research topic: {topic}"),
    ])
    | llm
    | StrOutputParser()
)


# --- 步骤 2: 定义并行研究节点 ---
# RunnableParallel 同时执行三个研究链
parallel_research_node = RunnableParallel(
    {
        # 步骤 2a: 并行执行三个研究任务
        "renewable_energy_result": research_renewable_chain,
        "ev_technology_result": research_ev_chain,
        "carbon_capture_result": research_carbon_chain,
    }
)


# --- 步骤 3: 定义合并链 ---
# 整合三个研究结果，生成结构化报告
merge_chain: Runnable = (
    ChatPromptTemplate.from_messages([
        ("system", """You are an AI Assistant responsible for combining research findings into a structured report.

**Input Summaries:**
* **Renewable Energy:**
{renewable_energy_result}
* **Electric Vehicles:**
{ev_technology_result}
* **Carbon Capture:**
{carbon_capture_result}

**Output Format:**
## Summary of Recent Sustainable Technology Advancements

### Renewable Energy Findings
[Synthesize and elaborate *only* on the renewable energy input summary provided above.]

### Electric Vehicle Findings
[Synthesize and elaborate *only* on the EV input summary provided above.]

### Carbon Capture Findings
[Synthesize and elaborate *only* on the carbon capture input summary provided above.]

### Overall Conclusion
[Provide a brief (1-2 sentence) concluding statement that connects *only* the findings presented above.]

Output *only* the structured report. Do not add external knowledge."""),
        ("user", "Original topic: {topic}"),
    ])
    | llm
    | StrOutputParser()
)


# --- 步骤 4: 构建完整流程链 ---
# 步骤 4a: 并行研究节点接收原始主题
# 步骤 4b: 并行结果通过管道传入合并链
# 步骤 4c: 合并链生成最终报告
full_research_chain = parallel_research_node | merge_chain


# --- 执行入口 ---
async def run_research(topic: str = "sustainable technology advancements"):
    """
    执行完整的研究与合成流程。

    Args:
        topic: 研究主题（此处为统一主题，各研究员使用自己的具体主题）
    """
    if not llm:
        print("LLM 未初始化，无法运行示例。")
        return

    print(f"\n{'='*60}")
    print(f"开始研究: {topic}")
    print(f"{'='*60}\n")

    try:
        # 步骤 5: 调用链执行
        # - ainvoke 异步调用
        # - 输入 topic 被 parallel_research_node 分发给三个研究链
        # - 研究结果通过管道传入 merge_chain
        result = await full_research_chain.ainvoke({"topic": topic})

        print(f"\n{'='*60}")
        print("最终报告:")
        print(f"{'='*60}")
        print(result)
    except Exception as e:
        print(f"执行出错: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_research())
