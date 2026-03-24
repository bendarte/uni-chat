interface Props {
  role: "user" | "assistant";
  content: string;
}

export default function ChatMessage({ role, content }: Props) {
  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[88%] rounded-[24px] px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap shadow-[0_18px_45px_rgba(31,42,42,0.08)] ${
          isUser
            ? "rounded-br-md bg-[var(--accent)] text-white"
            : "rounded-bl-md border border-[color:var(--line)] bg-[color:var(--card-strong)] text-[color:var(--ink)]"
        }`}
      >
        <div
          className={`mb-1 text-[10px] uppercase tracking-[0.22em] ${
            isUser ? "text-white/70" : "text-[color:var(--ink-soft)]"
          }`}
          style={{ fontFamily: "var(--font-mono), monospace" }}
        >
          {isUser ? "Du" : "UniChat"}
        </div>
        {content}
      </div>
    </div>
  );
}
