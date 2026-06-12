import ChatPageShell from "@/components/ChatPageShell";

const RAG_AGENT_SUGGESTIONS = [
  "帮我匹配适合家庭投保、保障高端的百万医疗险",
  "外购药保障强的百万医疗险有哪些？",
  "适合少儿的中高端医疗险怎么选？",
  "重疾险里性价比高的个人方案有哪些？",
  "有哪些产品支持特需医疗？",
];

export default function RAGAgentChatPage() {
  return (
    <ChatPageShell
      backendMode="rag_agent_chat"
      modeLabel="RAG Agent"
      emptyTitle="想从产品库里匹配什么保障？"
      emptyDescription="基于已入库产品知识库召回责任、标签和来源"
      fallbackSuggestions={RAG_AGENT_SUGGESTIONS}
    />
  );
}
