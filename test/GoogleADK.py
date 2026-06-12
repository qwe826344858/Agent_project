from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import google_search

GEMINI_MODEL = "gemini-2.0-flash"

# --- 1. 定义研究员子 Agent（并行运行） ---
# 研究员 1：可再生能源
researcher_agent_1 = LlmAgent(
    name="RenewableEnergyResearcher",
    model=GEMINI_MODEL,
    instruction="""You are an AI Research Assistant specializing in energy. Research the latest advancements in 'renewable energy sources'. Use the Google
Search tool provided. Summarize your key findings concisely (1-2 sentences). Output *only* the summary. """,
    description="Researches renewable energy sources.",
    tools=[google_search],
    # 将结果存储到状态中，供合并 Agent 使用
    output_key="renewable_energy_result",
)

# 研究员 2：电动汽车
researcher_agent_2 = LlmAgent(
    name="EVResearcher",
    model=GEMINI_MODEL,
    instruction="""You are an AI Research Assistant specializing in transportation. Research the latest developments in 'electric vehicle technology'. Use the
Google Search tool provided. Summarize your key findings concisely (1-2 sentences). Output *only* the summary. """,
    description="Researches electric vehicle technology.",
    tools=[google_search],
    # 将结果存储到状态中，供合并 Agent 使用
    output_key="ev_technology_result",
)

# 研究员 3：碳捕获
researcher_agent_3 = LlmAgent(
    name="CarbonCaptureResearcher",
    model=GEMINI_MODEL,
    instruction="""You are an AI Research Assistant specializing in climate solutions. Research the current state of 'carbon capture methods'. Use the Google
Search tool provided. Summarize your key findings concisely (1-2 sentences). Output *only* the summary. """,
    description="Researches carbon capture methods.",
    tools=[google_search],
    # 将结果存储到状态中，供合并 Agent 使用
    output_key="carbon_capture_result",
)

# --- 2. 创建并行 Agent（并发运行各研究员） ---
# 该 Agent 负责协调各研究员的并发执行。
# 当所有研究员完成并将结果存入状态后，并行 Agent 结束。
parallel_research_agent = ParallelAgent(
    name="ParallelWebResearchAgent",
    sub_agents=[researcher_agent_1, researcher_agent_2, researcher_agent_3],
    description="Runs multiple research agents in parallel to gather information.",
)

# --- 3. 定义合并 Agent（并行 Agent 之后运行） ---
# 该 Agent 获取并行 Agent 存入会话状态的结果，
# 并将它们合成为一个带有归属信息的结构化响应。
merger_agent = LlmAgent(
    name="SynthesisAgent",
    model=GEMINI_MODEL,  # 合成任务也可使用更强大的模型
    instruction="""You are an AI Assistant responsible for combining research findings into a structured report. Your primary task is to synthesize the
following research summaries, clearly attributing findings to their source areas. Structure your response using headings for each topic. Ensure the report is
coherent and integrates the key points smoothly.
**Crucially:** Your entire response MUST be grounded *exclusively* on the information provided in the 'Input Summaries' below. Do NOT add any external
knowledge, facts, or details not present in these specific summaries.
**Input Summaries:**
* **Renewable Energy:**
{renewable_energy_result}
* **Electric Vehicles:**
{ev_technology_result}
* **Carbon Capture:**
{carbon_capture_result}
**Output Format:**
## Summary of Recent Sustainable Technology Advancements



### Renewable Energy Findings (Based on RenewableEnergyResearcher's findings)
[Synthesize and elaborate *only* on the renewable energy input summary provided above.]
### Electric Vehicle Findings (Based on EVResearcher's findings)
[Synthesize and elaborate *only* on the EV input summary provided above.]
### Carbon Capture Findings (Based on CarbonCaptureResearcher's findings)
[Synthesize and elaborate *only* on the carbon capture input summary provided above.]
### Overall Conclusion
[Provide a brief (1-2 sentence) concluding statement that connects *only* the findings presented above.]
Output *only* the structured report following this format. Do not include introductory or concluding phrases outside this structure, and strictly adhere to
using only the provided input summary content.
""",
    description="Combines research findings from parallel agents into a structured, cited report, strictly grounded on provided inputs.",
    # 合并阶段不需要工具
    # 也不需要 output_key，因为它的直接响应就是序列的最终输出
)

# --- 4. 创建顺序 Agent（编排整体流程） ---
# 这是将运行的主 Agent。它首先执行并行 Agent 来填充状态，
# 然后执行合并 Agent 生成最终输出。
sequential_pipeline_agent = SequentialAgent(
    name="ResearchAndSynthesisPipeline",
    # 先运行并行研究，再进行合并
    sub_agents=[parallel_research_agent, merger_agent],
    description="Coordinates parallel research and synthesizes the results.",
)

root_agent = sequential_pipeline_agent
