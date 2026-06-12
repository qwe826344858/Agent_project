import os
import asyncio
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable, RunnableParallel, RunnablePassthrough

# --- 配置 ---
# 确保已设置 API 密钥环境变量（如 OPENAI_API_KEY）
try:
    llm: Optional[ChatOpenAI] = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
except Exception as e:
    print(f"初始化语言模型时出错: {e}")
    llm = None


# --- 定义独立链 ---
# 这三个链代表可以并行执行的不同任务
summarize_chain: Runnable = (
    ChatPromptTemplate.from_messages([
        ("system", "Summarize the following topic concisely:"),
        ("user", "{topic}"),
    ])
    | llm
    | StrOutputParser()
)

questions_chain: Runnable = (
    ChatPromptTemplate.from_messages([
        ("system", "Generate three interesting questions about the following topic:"),
        ("user", "{topic}"),
    ])
    | llm
    | StrOutputParser()
)

terms_chain: Runnable = (
    ChatPromptTemplate.from_messages([
        ("system", "Identify 5-10 key terms from the following topic, separated by commas:"),
        ("user", "{topic}"),
    ])
    | llm
    | StrOutputParser()
)


# --- 构建并行 + 合成链 ---
# 1. 定义需要并行运行的任务块。这些任务的结果，
#    将与原始主题一起传递给下一步。
map_chain = RunnableParallel(
    {
        "summary": summarize_chain,
        "questions": questions_chain,
        "key_terms": terms_chain,
        "topic": RunnablePassthrough(),  # 将原始主题透传下去
    }
)

# 2. 定义最终的合成提示词，用于整合并行结果
synthesis_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """Based on the following information:
 Summary: {summary}
 Related Questions: {questions}
 Key Terms: {key_terms}
 Synthesize a comprehensive answer.""",
    ),
    ("user", "Original topic: {topic}"),
])

# 3. 将并行结果直接通过管道传入合成提示词，
#    然后经过 LLM 和输出解析器，构建完整的链
full_parallel_chain = map_chain | synthesis_prompt | llm | StrOutputParser()


# --- 运行链 ---
async def run_parallel_example(topic: str) -> None:
    """
    异步调用并行处理链，对指定主题进行处理并打印合成结果。

    Args:
        topic: 要由 LangChain 链处理的主题。
    """
    if not llm:
        print("LLM 未初始化，无法运行示例。")
        return

    print(f"\n--- 运行并行 LangChain 示例，主题: '{topic}' ---")

    try:
        # ainvoke 的输入是单个 'topic' 字符串，
        # 然后传递给 map_chain 中的每个可运行对象。
        response = await full_parallel_chain.ainvoke(topic)
        print("\n--- 最终响应 ---")
        print(response)
    except Exception as e:
        print(f"\n链执行过程中发生错误: {e}")


if __name__ == "__main__":
    test_topic = "The history of space exploration"
    # Python 3.7+ 推荐使用 asyncio.run 来运行异步函数
    asyncio.run(run_parallel_example(test_topic))
