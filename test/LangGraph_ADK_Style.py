"""
Google ADK 逻辑的 LangGraph 实现
================================
使用 LangGraph 的 StateGraph 实现并行研究与合并流程。

执行步骤：
1. 定义状态结构（存储三个研究结果）
2. 定义三个并行研究节点函数
3. 定义合并节点函数
4. 构建 StateGraph：research_renewable/research_ev/research_carbon → merge_results → END
5. 编译并执行图

架构特点：
- 状态在节点间共享
- 节点函数接收当前状态，返回要更新的状态字段
- 支持条件分支和循环
"""

import os
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END

# --- 配置 ---
try:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
except Exception as e:
    print(f"初始化语言模型时出错: {e}")
    llm = None


# --- 步骤 1: 定义状态结构 ---
class ResearchState(TypedDict):
    """
    研究状态：所有节点共享的状态字典。
    每个节点函数接收当前状态，返回要更新的字段。
    """
    topic: str                           # 原始主题
    renewable_energy_result: str          # 可再生能源研究结果
    ev_technology_result: str            # 电动汽车研究结果
    carbon_capture_result: str            # 碳捕获研究结果
    final_report: str                     # 最终合并报告


# --- 步骤 2: 定义 LLM 调用函数 ---
def create_research_chain(topic: str, system_prompt: str) -> str:
    """
    创建研究链的工厂函数。

    Args:
        topic: 研究主题
        system_prompt: 系统提示词

    Returns:
        研究结果字符串
    """
    chain = (
        ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Research topic: {topic}"),
        ])
        | llm
        | StrOutputParser()
    )
    return chain.invoke({"topic": topic})


# --- 步骤 3: 定义并行研究节点函数 ---
# 每个节点独立执行，通过返回字典更新状态

def research_renewable(state: ResearchState) -> ResearchState:
    """
    节点 1: 研究可再生能源

    从状态读取 topic，执行研究，结果写回状态。
    """
    print("  [节点1] 研究可再生能源...")
    result = create_research_chain(
        topic=state["topic"],
        system_prompt="""You are an AI Research Assistant specializing in energy.
Research the latest advancements in 'renewable energy sources'.
Summarize your key findings concisely (1-2 sentences).
Output *only* the summary."""
    )
    return {"renewable_energy_result": result}


def research_ev(state: ResearchState) -> ResearchState:
    """
    节点 2: 研究电动汽车

    从状态读取 topic，执行研究，结果写回状态。
    """
    print("  [节点2] 研究电动汽车...")
    result = create_research_chain(
        topic=state["topic"],
        system_prompt="""You are an AI Research Assistant specializing in transportation.
Research the latest developments in 'electric vehicle technology'.
Summarize your key findings concisely (1-2 sentences).
Output *only* the summary."""
    )
    return {"ev_technology_result": result}


def research_carbon(state: ResearchState) -> ResearchState:
    """
    节点 3: 研究碳捕获

    从状态读取 topic，执行研究，结果写回状态。
    """
    print("  [节点3] 研究碳捕获...")
    result = create_research_chain(
        topic=state["topic"],
        system_prompt="""You are an AI Research Assistant specializing in climate solutions.
Research the current state of 'carbon capture methods'.
Summarize your key findings concisely (1-2 sentences).
Output *only* the summary."""
    )
    return {"carbon_capture_result": result}


# --- 步骤 4: 定义合并节点函数 ---
def merge_results(state: ResearchState) -> ResearchState:
    """
    节点 4: 合并研究结果

    从状态读取三个研究结果，生成结构化报告。
    """
    print("  [节点4] 合并研究结果...")

    # 读取并行研究阶段的结果
    renewable = state.get("renewable_energy_result", "")
    ev = state.get("ev_technology_result", "")
    carbon = state.get("carbon_capture_result", "")

    # 构建合并提示词
    merge_chain = (
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
            ("user", "Please synthesize the research findings above."),
        ])
        | llm
        | StrOutputParser()
    )

    # 执行合并
    report = merge_chain.invoke({
        "renewable_energy_result": renewable,
        "ev_technology_result": ev,
        "carbon_capture_result": carbon,
    })

    return {"final_report": report}


# --- 步骤 5: 构建 StateGraph ---
def create_research_graph():
    """
    创建研究流程图。

    图结构：
    START → research_renewable ─┐
         → research_ev ─────────┼→ merge_results → END
         → research_carbon ─────┘

    三个研究节点并行执行，完成后进入合并节点。
    """

    # 创建状态图
    workflow = StateGraph(ResearchState)

    # 步骤 5a: 添加节点
    workflow.add_node("research_renewable", research_renewable)
    workflow.add_node("research_ev", research_ev)
    workflow.add_node("research_carbon", research_carbon)
    workflow.add_node("merge_results", merge_results)

    # 步骤 5b: 定义入口点（三个节点同时开始）
    workflow.set_entry_point("research_renewable")
    workflow.add_edge("research_renewable", "merge_results")

    workflow.set_entry_point("research_ev")
    workflow.add_edge("research_ev", "merge_results")

    workflow.set_entry_point("research_carbon")
    workflow.add_edge("research_carbon", "merge_results")

    # 合并节点完成后结束
    workflow.add_edge("merge_results", END)

    # 步骤 5c: 编译图
    return workflow.compile()


# --- 执行入口 ---
async def run_research(topic: str = "sustainable technology advancements"):
    """
    执行完整的研究与合成流程。

    Args:
        topic: 研究主题
    """
    if not llm:
        print("LLM 未初始化，无法运行示例。")
        return

    print(f"\n{'='*60}")
    print(f"开始 LangGraph 研究流程: {topic}")
    print(f"{'='*60}\n")

    # 创建并编译图
    graph = create_research_graph()

    # 初始化状态
    initial_state = {
        "topic": topic,
        "renewable_energy_result": "",
        "ev_technology_result": "",
        "carbon_capture_result": "",
        "final_report": "",
    }

    try:
        # 步骤 6: 执行图
        # - LangGraph 从 entry_point 开始
        # - 三个研究节点并行调度（通过独立边设置实现）
        # - 所有研究完成后进入 merge_results
        # - 最终输出包含完整状态
        result = await graph.ainvoke(initial_state)

        print(f"\n{'='*60}")
        print("最终报告:")
        print(f"{'='*60}")
        print(result["final_report"])
    except Exception as e:
        print(f"执行出错: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_research())
