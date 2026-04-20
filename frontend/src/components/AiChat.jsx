import { useEffect, useRef, useState } from "react";
import { chatWithPlan } from "../api";

const EXAMPLE_QUESTIONS = [
  "В каком семестре лучше поставить курс по БД?",
  "Сколько зачётных единиц не хватает до нормы?",
  "Какие компетенции ещё не покрыты?",
];

export default function AiChat({ planId, open, onToggle }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bodyRef = useRef(null);
  const inputRef = useRef(null);

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

  const send = async (text) => {
    const msg = (text || input).trim();
    if (!msg || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: msg, ts: new Date() }]);
    setLoading(true);
    try {
      const answer = await chatWithPlan(planId, msg);
      setMessages((prev) => [...prev, { role: "ai", text: answer, ts: new Date() }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: "Произошла ошибка при обращении к ИИ. Попробуйте снова.", ts: new Date(), error: true },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const fmt = (date) =>
    date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });

  return (
    <>
      {/* FAB */}
      <button
        className={`ai-fab${open ? " panel-open" : ""}`}
        onClick={onToggle}
        title="ИИ-ассистент"
        aria-label="Открыть чат с ИИ"
      >
        {open ? "✕" : "✦"}
      </button>

      {/* Sliding panel */}
      <div className={`ai-panel${open ? " open" : ""}`} role="dialog" aria-label="ИИ-ассистент">
        <div className="ai-panel__header">
          <div className="ai-panel__icon">✦</div>
          <div>
            <div className="ai-panel__title">ИИ-ассистент</div>
            <div className="ai-panel__sub">Задайте вопрос об учебном плане</div>
          </div>
          <button className="btn-icon ai-panel__close" onClick={onToggle} title="Закрыть">✕</button>
        </div>

        <div className="ai-panel__body" ref={bodyRef}>
          {messages.length === 0 && (
            <div className="ai-hint">
              <div>
                <strong>Как я могу помочь?</strong> Я знаю структуру вашего плана,
                нормативы ФГОС и типовые требования к учебным программам.
              </div>
              <div className="ai-hint-examples">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button key={q} className="ai-hint-example" onClick={() => send(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role}`}>
              <div className="chat-bubble__content">{m.text}</div>
              <div className="chat-bubble__time">{fmt(m.ts)}</div>
            </div>
          ))}

          {loading && (
            <div className="chat-skeleton">
              <div className="skeleton-line" />
              <div className="skeleton-line" />
              <div className="skeleton-line" />
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
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
            }}
            disabled={loading}
          />
          <button
            className="ai-panel__send"
            onClick={() => send()}
            disabled={loading || !input.trim()}
            title="Отправить (Enter)"
          >
            {loading ? <span className="spinner" style={{ borderColor: "#fff", borderTopColor: "transparent" }} /> : "↑"}
          </button>
        </div>
      </div>
    </>
  );
}
