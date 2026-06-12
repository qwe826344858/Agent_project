"""
MCP Client - 符合标准 MCP 协议
===============================
参考: https://modelcontextprotocol.io/specification
"""

import json
import httpx
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")

# ============================================================
# MCP 协议常量
# ============================================================

MCP_SERVER_URL = "http://localhost:8080/mcp"
MCP_PROTOCOL_VERSION = "2024-11-05"

# ============================================================
# 步骤1: 初始化连接 (initialize)
# ============================================================
def mcp_initialize():
    """MCP 协议要求：先发送 initialize"""
    response = httpx.post(MCP_SERVER_URL, json={
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": "demo-mcp-client",
                "version": "1.0.0"
            }
        }
    })
    result = response.json()["result"]
    print(f"[初始化] Server: {result['serverInfo']['name']}, 版本: {result['serverInfo']['version']}")
    return result

# ============================================================
# 步骤2: 获取工具列表 (tools/list)
# ============================================================
def mcp_list_tools():
    """获取 MCP Server 提供的工具列表"""
    response = httpx.post(MCP_SERVER_URL, json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })
    tools = response.json()["result"]["tools"]
    print(f"[工具列表] 发现 {len(tools)} 个工具:")
    for t in tools:
        print(f"  - {t['name']}: {t['description']}")
        print(f"    参数: {json.dumps(t['inputSchema'], ensure_ascii=False)}")
    return tools

# ============================================================
# 步骤3: LLM 判断是否调用工具
# ============================================================
def llm_decide(user_input: str, tools: list) -> dict:
    """
    让 LLM 根据用户输入和可用工具判断是否需要调用工具
    返回: {"need_tool": True/False, "tool": "xxx", "args": {...}, "direct_answer": "xxx"}
    """
    # 将工具格式化为 LLM 可理解的描述
    tools_desc = []
    for t in tools:
        schema = t.get("inputSchema", {})
        props = schema.get("properties", {})
        params = ", ".join([f"{k}({v.get('type')}): {v.get('description','')}" for k, v in props.items()])
        tools_desc.append(f"- {t['name']}: {t['description']} [参数: {params}]")

    tools_str = "\n".join(tools_desc)

    prompt = f"""你是一个助手。可用工具：
{tools_str}

用户输入：{user_input}

判断是否需要调用工具：
- 如果需要，输出JSON格式（无其他内容）：
{{"tool": "工具名", "arguments": {{"参数名": "参数值"}}}}

- 如果可以直接回答，输出文本。"""

    response = llm.invoke(prompt).content.strip()

    # 尝试解析 JSON
    if response.startswith("{"):
        try:
            data = json.loads(response)
            return {"need_tool": True, "tool": data["tool"], "args": data["arguments"]}
        except json.JSONDecodeError:
            pass

    return {"need_tool": False, "direct_answer": response}

# ============================================================
# 步骤4: 调用工具 (tools/call)
# ============================================================
def mcp_call_tool(tool_name: str, arguments: dict) -> str:
    """调用 MCP Server 的工具"""
    response = httpx.post(MCP_SERVER_URL, json={
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    })

    result = response.json()["result"]
    # 标准 MCP 格式：result.content 是数组
    content = result.get("content", [])
    if content and content[0].get("type") == "text":
        return content[0]["text"]
    return str(result)

# ============================================================
# 步骤5: 整合结果
# ============================================================
def make_final_answer(user_input: str, mcp_result: str) -> str:
    """将 MCP 结果整合成最终回答"""
    prompt = f"""用户问：{user_input}
工具返回：{mcp_result}
请根据工具返回结果，自然地回答用户。"""
    return llm.invoke(prompt).content

# ============================================================
# 主流程
# ============================================================
def main():
    user_input = "北京天气怎么样？"

    print(f"\n{'='*50}")
    print(f"用户输入: {user_input}")
    print(f"{'='*50}\n")

    # 步骤1: 初始化
    mcp_initialize()

    # 步骤2: 获取工具列表
    tools = mcp_list_tools()

    # 步骤3: LLM 判断
    decision = llm_decide(user_input, tools)
    print(f"\n[LLM 决策] {decision}")

    # 步骤4: 执行
    if decision["need_tool"]:
        tool_name = decision["tool"]
        args = decision["args"]
        print(f"\n[调用工具] {tool_name}({args})")

        mcp_result = mcp_call_tool(tool_name, args)
        print(f"[工具返回] {mcp_result}")

        answer = make_final_answer(user_input, mcp_result)
    else:
        answer = decision["direct_answer"]
        print(f"\n[直接回答] {answer}")

    print(f"\n{'='*50}")
    print(f"最终回答: {answer}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
