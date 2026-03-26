#!/bin/bash
# 探测 Open-WebSearch MCP HTTP 端点

echo "=== SSE endpoint ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000/sse

echo "=== message POST ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST http://localhost:3000/message -H "Content-Type: application/json" -d "{}"

echo "=== mcp POST ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST http://localhost:3000/mcp -H "Content-Type: application/json" -d "{}"

echo "=== SSE content (5s timeout) ==="
timeout 5 curl -s http://localhost:3000/sse 2>&1 | head -10

echo "=== message with tools/call ==="
curl -s --max-time 15 -X POST http://localhost:3000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' 2>&1 | head -5

echo "=== DONE ==="
