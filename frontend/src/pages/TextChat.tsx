import { useState, useRef, useEffect, useCallback } from "react";

interface TextChatProps {
  brainUrl: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export default function TextChat({ brainUrl }: TextChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    setError("");
    setInput("");

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };

    // Build conversation history for the API
    const apiMessages = [...messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const assistantMsg: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${brainUrl}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet",
          messages: apiMessages,
          stream: true,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Brain returned ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE lines
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;

          const data = trimmed.slice(6); // Remove "data: "
          if (data === "[DONE]") continue;

          try {
            const parsed = JSON.parse(data);
            const delta = parsed.choices?.[0]?.delta?.content;
            if (delta) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id
                    ? { ...m, content: m.content + delta }
                    : m
                )
              );
            }
          } catch {
            // Skip malformed JSON chunks
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User cancelled, not an error
      } else {
        const msg = err instanceof Error ? err.message : "Unknown error";
        setError(msg);
        // Remove the empty assistant message on error
        setMessages((prev) => prev.filter((m) => m.id !== assistantMsg.id));
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      inputRef.current?.focus();
    }
  }, [input, isStreaming, messages, brainUrl]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  return (
    <div className="flex flex-col h-screen bg-champ-bg">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-champ-muted">
              <div className="w-12 h-12 rounded-full bg-champ-accent/20 flex items-center justify-center mb-4">
                <span className="text-champ-accent font-bold text-lg">C</span>
              </div>
              <p className="text-lg font-medium text-white mb-1">Chat with Champ</p>
              <p className="text-sm">Send a message to start the conversation.</p>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {/* Assistant avatar */}
              {msg.role === "assistant" && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-champ-accent/20 flex items-center justify-center mt-1">
                  <span className="text-champ-accent font-bold text-xs">C</span>
                </div>
              )}

              <div
                className={`max-w-[75%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-champ-accent text-white"
                    : "bg-champ-card border border-champ-border text-white"
                }`}
              >
                {msg.role === "assistant" && (
                  <p className="text-xs text-champ-muted font-medium mb-1">Champ</p>
                )}
                {msg.content ? (
                  <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                ) : (
                  msg.role === "assistant" &&
                  isStreaming && (
                    <div className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 bg-champ-muted rounded-full animate-pulse" />
                      <span className="w-1.5 h-1.5 bg-champ-muted rounded-full animate-pulse [animation-delay:0.2s]" />
                      <span className="w-1.5 h-1.5 bg-champ-muted rounded-full animate-pulse [animation-delay:0.4s]" />
                    </div>
                  )
                )}
              </div>

              {/* User avatar */}
              {msg.role === "user" && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-champ-border flex items-center justify-center mt-1">
                  <span className="text-white font-bold text-xs">U</span>
                </div>
              )}
            </div>
          ))}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="px-4">
          <div className="max-w-3xl mx-auto bg-champ-red/10 border border-champ-red/30 text-champ-red rounded-lg px-4 py-2 text-sm mb-2">
            {error}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-champ-border px-4 py-4">
        <div className="max-w-3xl mx-auto flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Champ..."
            rows={1}
            className="flex-1 bg-champ-card border border-champ-border rounded-lg px-4 py-3 text-sm text-white placeholder-champ-muted resize-none focus:outline-none focus:border-champ-accent transition-colors"
            style={{ maxHeight: "150px" }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = Math.min(target.scrollHeight, 150) + "px";
            }}
            disabled={isStreaming}
          />
          {isStreaming ? (
            <button
              onClick={handleStop}
              className="flex-shrink-0 bg-champ-red hover:bg-champ-red/80 text-white rounded-lg px-4 py-3 text-sm font-medium transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={sendMessage}
              disabled={!input.trim()}
              className="flex-shrink-0 bg-champ-accent hover:bg-champ-accent/80 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg px-4 py-3 text-sm font-medium transition-colors"
            >
              Send
            </button>
          )}
        </div>
        <p className="max-w-3xl mx-auto text-xs text-champ-muted mt-2">
          Shift+Enter for new line. Enter to send.
        </p>
      </div>
    </div>
  );
}
