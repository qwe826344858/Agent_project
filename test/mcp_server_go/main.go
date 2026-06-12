/*
MCP Server - 符合标准 MCP 协议
================================
使用 JSON-RPC 2.0 协议规范
参考: https://modelcontextprotocol.io/specification
*/

package main

import (
	"encoding/json"
	"fmt"
	"net/http"
)

// ============================================================
// JSON-RPC 2.0 类型定义
// ============================================================

type Request struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      interface{}     `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type Response struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      interface{} `json:"id"`
	Result  interface{} `json:"result,omitempty"`
	Error   *Error      `json:"error,omitempty"`
}

type Error struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// MCP 协议定义的工具结构
type Tool struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	InputSchema json.RawMessage `json:"inputSchema"`
}

// tools/list 结果
type ToolListResult struct {
	Tools []Tool `json:"tools"`
}

// tools/call 参数
type CallParams struct {
	Name      string                 `json:"name"`
	Arguments map[string]interface{} `json:"arguments"`
}

// tools/call 结果
type CallResult struct {
	Content []ContentBlock `json:"content"`
}

type ContentBlock struct {
	Type    string `json:"type"` // "text"
	Text    string `json:"text,omitempty"`
	IsError bool   `json:"isError,omitempty"`
}

// ============================================================
// MCP 工具实现
// ============================================================

var tools = []Tool{
	{
		Name:        "get_weather",
		Description: "获取指定城市的天气信息",
		InputSchema: json.RawMessage(`{
			"type": "object",
			"properties": {
				"city": {
					"type": "string",
					"description": "城市名称，如：北京、上海"
				}
			},
			"required": ["city"]
		}`),
	},
	{
		Name:        "search_news",
		Description: "搜索最新新闻",
		InputSchema: json.RawMessage(`{
			"type": "object",
			"properties": {
				"keyword": {
					"type": "string",
					"description": "搜索关键词"
				}
			},
			"required": ["keyword"]
		}`),
	},
}

func getWeather(args map[string]interface{}) string {
	city, _ := args["city"].(string)
	return fmt.Sprintf("%s 今天天气晴朗，温度 25°C，适合外出", city)
}

func searchNews(args map[string]interface{}) string {
	keyword, _ := args["keyword"].(string)
	return fmt.Sprintf("关于「%s」的最新新闻：1) 行业突破 2) 市场动态 3) 政策更新", keyword)
}

// ============================================================
// MCP 协议处理器
// ============================================================

func handleMCP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	var req Request
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, req.ID, -32700, "Parse error")
		return
	}

	var result interface{}

	switch req.Method {
	case "initialize":
		// 初始化（标准 MCP 协议要求）
		result = map[string]interface{}{
			"protocolVersion": "2024-11-05",
			"capabilities": map[string]bool{
				"tools": true,
			},
			"serverInfo": map[string]string{
				"name":    "demo-mcp-server",
				"version": "1.0.0",
			},
		}

	case "tools/list":
		// 返回工具列表（标准格式）
		result = ToolListResult{Tools: tools}

	case "tools/call":
		// 调用工具
		var params CallParams
		if err := json.Unmarshal(req.Params, &params); err != nil {
			sendError(w, req.ID, -32602, "Invalid params")
			return
		}

		var text string
		switch params.Name {
		case "get_weather":
			text = getWeather(params.Arguments)
		case "search_news":
			text = searchNews(params.Arguments)
		default:
			sendError(w, req.ID, -32602, fmt.Sprintf("Unknown tool: %s", params.Name))
			return
		}

		// 标准 MCP 响应格式：content 数组
		result = CallResult{
			Content: []ContentBlock{
				{Type: "text", Text: text},
			},
		}

	default:
		sendError(w, req.ID, -32601, fmt.Sprintf("Method not found: %s", req.Method))
		return
	}

	json.NewEncoder(w).Encode(Response{
		JSONRPC: "2.0",
		ID:      req.ID,
		Result:  result,
	})
}

func sendError(w http.ResponseWriter, id interface{}, code int, message string) {
	json.NewEncoder(w).Encode(Response{
		JSONRPC: "2.0",
		ID:      id,
		Error:   &Error{Code: code, Message: message},
	})
}

// ============================================================
// 主函数
// ============================================================

func main() {
	http.HandleFunc("/mcp", handleMCP)

	fmt.Println("MCP Server 启动 :8080")
	fmt.Println("协议: JSON-RPC 2.0, MCP 2024-11-05")
	fmt.Println("端点: http://localhost:8080/mcp")
	fmt.Println("\n工具列表:")
	for _, t := range tools {
		fmt.Printf("  - %s: %s\n", t.Name, t.Description)
	}

	http.ListenAndServe(":8080", nil)
}
