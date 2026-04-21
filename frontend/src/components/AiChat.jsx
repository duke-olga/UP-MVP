import { useEffect, useRef, useState } from "react";
import { chatWithPlan } from "../api";

const EXAMPLE_QUESTIONS = [
  "В каком семестре лучше поставить курс по БД?",
  "Сколько зачётных единиц не хватает до нормы?",
  "Какие компетенции ещё не покрыты?",
];

const AI_ERROR_TEXT = "Произошла ошибка при обращении к ИИ. Попробуйте снова.";

export default function AiChat({ planId, open, onToggle }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bodyRef = useRef(null);
  const inputRef = useRef(null);
  const messageIdRef = useRef(0);

  const hasTypingMessage = messages.some((message) => message.isTyping);
  const isBusy = loading || hasTypingMessage;

  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 280);
    }
  }, [open]);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [messages, loading]);

  useEffect(() => {
    const typingMessage = messages.find((message) => message.isTyping);
    if (!typingMessage) return undefined;

    const step = Math.max(1, Math.ceil((typingMessage.fullText.length || 0) / 90));
    const timer = setInterval(() => {
      let completed = false;

      setMessages((prev) =>
        prev.map((message) => {
          if (message.id !== typingMessage.id || !message.isTyping) {
            return message;
          }

          const nextLength = Math.min(message.text.length + step, message.fullText.length);
          completed = nextLength >= message.fullText.length;

          return {
            ...message,
            text: message.fullText.slice(0, nextLength),
            isTyping: !completed,
          };
        })
      );

      if (completed) {
        clearInterval(timer);
      }
    }, 24);

    return () => clearInterval(timer);
  }, [messages]);

  const send = async (text) => {
    const msg = (text || input).trim();
    if (!msg || isBusy) return;

    setInput("");
    setMessages((prev) => [...prev, { id: ++messageIdRef.current, role: "user", text: msg, ts: new Date() }]);
    setLoading(true);

    try {
      const answer = await chatWithPlan(planId, msg);

      setMessages((prev) => [
        ...prev,
        {
          id: ++messageIdRef.current,
          role: "ai",
          text: "",
          fullText: answer,
          ts: new Date(),
          isTyping: true,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: ++messageIdRef.current,
          role: "ai",
          text: AI_ERROR_TEXT,
          ts: new Date(),
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const fmt = (date) =>
    date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });

  return (
    <>
      <button
        className={`ai-fab${open ? " panel-open" : ""}`}
        onClick={onToggle}
        title="ИИ-ассистент"
        aria-label="Открыть чат с ИИ"
      >
        {open ? "✕" : "✦"}
      </button>

      <div className={`ai-panel${open ? " open" : ""}`} role="dialog" aria-label="ИИ-ассистент">
        <div className="ai-panel__header">
          <div className="ai-panel__icon">✦</div>
          <div>
            <div className="ai-panel__title">ИИ-ассистент</div>
            <div className="ai-panel__sub">Задайте вопрос об учебном плане</div>
          </div>
          <button className="btn-icon ai-panel__close" onClick={onToggle} title="Закрыть">
            ✕
          </button>
        </div>

        <div className="ai-panel__body" ref={bodyRef}>
          {messages.length === 0 && (
            <div className="ai-hint">
              <div>
                <strong>Как я могу помочь?</strong> Я знаю структуру вашего плана, нормативы ФГОС и типовые
                требования к учебным программам.
              </div>
              <div className="ai-hint-examples">
                {EXAMPLE_QUESTIONS.map((question) => (
                  <button
                    key={question}
                    className="ai-hint-example"
                    onClick={() => send(question)}
                    disabled={isBusy}
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id} className={`chat-bubble ${message.role}`}>
              <div className={`chat-bubble__content${message.isTyping ? " typing" : ""}`}>
                {message.text}
                {message.isTyping && <span className="chat-bubble__caret" aria-hidden="true" />}
              </div>
              <div className="chat-bubble__time">{fmt(message.ts)}</div>
            </div>
          ))}

          {loading && (
            <div className="chat-bubble ai">
              <div className="chat-bubble__content chat-bubble__content--pending" aria-label="ИИ печатает ответ">
                <span className="typing-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="ai-panel__footer">
          <textarea
            ref={inputRef}
            className="ai-panel__input"
            placeholder="Спросите что-либо об учебном плане…"
            value={input}
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            disabled={isBusy}
          />
          <button
            className="ai-panel__send"
            onClick={() => send()}
            disabled={isBusy || !input.trim()}
            title="Отправить (Enter)"
          >
            {loading ? (
              <span className="spinner" style={{ borderColor: "#fff", borderTopColor: "transparent" }} />
            ) : (
              "↑"
            )}
          </button>
        </div>
      </div>
    </>
  );
}
