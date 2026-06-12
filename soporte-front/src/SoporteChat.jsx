/* SoporteChat.jsx
   Simulador de soporte TI — especialista (humano) vs cliente frustrado (IA)
   Estética: panel de helpdesk corporativo, limpio y funcional
*/

import { useState, useEffect, useRef } from "react";
import { useSoporteChat } from "./useSoporteChat";

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:          #f4f5f7;
    --surface:     #ffffff;
    --surface2:    #f8f9fa;
    --border:      #e1e4e8;
    --border2:     #d0d4db;
    --text:        #1c1e21;
    --text-dim:    #6b7280;
    --text-xdim:   #9ca3af;
    --agent:       #2563eb;
    --agent-light: #eff6ff;
    --agent-dark:  #1d4ed8;
    --client:      #ffffff;
    --online:      #16a34a;
    --red:         #dc2626;
    --yellow:      #d97706;
    --mono:        'JetBrains Mono', monospace;
    --sans:        'Inter', sans-serif;
    --r:           12px;
    --r-sm:        8px;
  }

  body { background: var(--bg); font-family: var(--sans); }

  .app {
    display: flex; flex-direction: column; height: 100dvh;
    max-width: 720px; margin: 0 auto;
    background: var(--surface);
    box-shadow: 0 0 0 1px var(--border);
  }

  /* ── Header ─────────────────────────────────────────────────────────────── */
  .header {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 20px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .avatar {
    width: 38px; height: 38px; border-radius: 50%;
    background: #fef9c3; border: 1.5px solid #fde047;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; flex-shrink: 0;
  }
  .header-info { flex: 1; min-width: 0; }
  .header-name { font-size: 14px; font-weight: 600; color: var(--text); }
  .header-meta {
    display: flex; align-items: center; gap: 6px;
    margin-top: 2px; font-size: 12px; color: var(--text-dim);
  }
  .status-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--online); flex-shrink: 0;
  }
  .status-dot.typing { background: var(--text-xdim); animation: blink 1s ease-in-out infinite; }
  .status-dot.offline { background: var(--border2); }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }

  .ticket-tag {
    font-family: var(--mono); font-size: 11px;
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text-dim); padding: 2px 8px; border-radius: 4px;
    white-space: nowrap;
  }
  .btn-ghost {
    font-family: var(--sans); font-size: 12px; font-weight: 500;
    color: var(--text-dim); background: none;
    border: 1px solid var(--border); border-radius: var(--r-sm);
    padding: 5px 12px; cursor: pointer;
    transition: border-color .15s, color .15s;
    white-space: nowrap;
  }
  .btn-ghost:hover:not(:disabled) { border-color: var(--red); color: var(--red); }
  .btn-ghost:disabled { opacity: .4; cursor: not-allowed; }

  /* ── Estado vacío / pantalla de inicio ──────────────────────────────────── */
  .start-screen {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 20px;
    padding: 40px; text-align: center;
  }
  .start-icon { font-size: 48px; opacity: .7; }
  .start-title { font-size: 18px; font-weight: 600; color: var(--text); }
  .start-sub {
    font-size: 14px; color: var(--text-dim);
    line-height: 1.7; max-width: 300px;
  }
  .btn-primary {
    font-family: var(--sans); font-size: 14px; font-weight: 600;
    background: var(--agent); color: #fff; border: none;
    padding: 12px 28px; border-radius: var(--r); cursor: pointer;
    transition: background .15s, transform .1s;
  }
  .btn-primary:hover { background: var(--agent-dark); }
  .btn-primary:active { transform: scale(.97); }

  /* ── Área de mensajes ────────────────────────────────────────────────────── */
  .messages {
    flex: 1; overflow-y: auto; padding: 20px 16px;
    display: flex; flex-direction: column; gap: 16px;
    scroll-behavior: smooth;
  }
  .messages::-webkit-scrollbar { width: 4px; }
  .messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  /* Separador de fecha/inicio */
  .day-label {
    text-align: center; font-size: 11px; color: var(--text-xdim);
    font-family: var(--mono); margin: 4px 0;
  }

  /* ── Burbuja ─────────────────────────────────────────────────────────────── */
  .row { display: flex; flex-direction: column; gap: 3px; }
  .row.agent  { align-items: flex-end; }
  .row.client { align-items: flex-start; }

  .row-label {
    font-size: 11px; color: var(--text-xdim); padding: 0 4px;
  }

  .bubble {
    max-width: 80%; padding: 10px 14px;
    font-size: 14px; line-height: 1.65;
    word-break: break-word; white-space: pre-wrap;
    position: relative;
  }

  /* Agente: azul, derecha */
  .row.agent .bubble {
    background: var(--agent);
    color: #fff;
    border-radius: var(--r) var(--r) 3px var(--r);
  }

  /* Cliente IA: blanco, izquierda */
  .row.client .bubble {
    background: var(--client);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--r) var(--r) var(--r) 3px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
  }

  .bubble-time {
    font-size: 10px; margin-top: 4px; padding: 0 4px;
    color: var(--text-xdim);
  }

  /* ── Indicador "escribiendo" ─────────────────────────────────────────────── */
  .typing-indicator {
    display: flex; align-items: center; gap: 4px;
    background: var(--client);
    border: 1px solid var(--border);
    border-radius: var(--r) var(--r) var(--r) 3px;
    padding: 12px 16px; width: fit-content;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
    animation: fadeUp .2s ease-out;
  }
  @keyframes fadeUp { from{opacity:0;transform:translateY(5px)} to{opacity:1;transform:none} }

  .typing-indicator span {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--text-xdim);
    animation: bounce .9s ease-in-out infinite;
  }
  .typing-indicator span:nth-child(2) { animation-delay: .15s; }
  .typing-indicator span:nth-child(3) { animation-delay: .30s; }
  @keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-5px)} }

  /* ── Error ───────────────────────────────────────────────────────────────── */
  .error-banner {
    margin: 0 16px 8px;
    padding: 9px 14px; flex-shrink: 0;
    background: #fef2f2; border: 1px solid #fecaca;
    border-radius: var(--r-sm);
    font-size: 13px; color: var(--red);
    display: flex; align-items: center; gap: 8px;
  }

  /* ── Input ───────────────────────────────────────────────────────────────── */
  .input-area {
    flex-shrink: 0; padding: 12px 16px 16px;
    border-top: 1px solid var(--border);
    background: var(--surface);
    display: flex; gap: 8px; align-items: flex-end;
  }
  textarea {
    flex: 1; font-family: var(--sans); font-size: 14px; line-height: 1.5;
    background: var(--surface2); color: var(--text);
    border: 1px solid var(--border); border-radius: 20px;
    padding: 9px 16px; resize: none; outline: none;
    transition: border-color .15s;
    min-height: 40px; max-height: 120px;
  }
  textarea::placeholder { color: var(--text-xdim); }
  textarea:focus { border-color: var(--agent); background: var(--surface); }
  textarea:disabled { opacity: .45; cursor: not-allowed; }

  .send-btn {
    width: 40px; height: 40px; flex-shrink: 0;
    border: none; border-radius: 50%; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: background .15s, transform .1s;
    background: var(--agent);
  }
  .send-btn:hover:not(:disabled) { background: var(--agent-dark); }
  .send-btn:active:not(:disabled) { transform: scale(.93); }
  .send-btn:disabled { background: var(--border); cursor: not-allowed; }
  .send-btn.stop { background: #fee2e2; }
  .send-btn.stop svg { color: var(--red); }
  .send-btn svg { width: 16px; height: 16px; color: #fff; }

  .input-hint {
    text-align: center; font-size: 11px; color: var(--text-xdim);
    padding: 4px 0 0; flex-shrink: 0;
    font-family: var(--mono);
  }
`;

function formatTime(date) {
  return date?.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }) ?? "";
}

export default function SoporteChat() {
  const {
    messages, isTyping, error,
    sessionReady, startSession,
    sendMessage, cancelRequest, resetSession,
  } = useSoporteChat();

  const [input, setInput]   = useState("");
  const timesRef            = useRef({});   // { index: Date }
  const prevLenRef          = useRef(0);
  const messagesEndRef      = useRef(null);
  const textareaRef         = useRef(null);

  // Guardar timestamp cuando llegan mensajes nuevos
  useEffect(() => {
    for (let i = prevLenRef.current; i < messages.length; i++) {
      timesRef.current[i] = new Date();
    }
    prevLenRef.current = messages.length;
  }, [messages]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
  }, [input]);

  const handleSubmit = () => {
    if (!input.trim() || isTyping) return;
    sendMessage(input.trim());
    setInput("");
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const turnCount = Math.ceil(messages.length / 2);

  return (
    <>
      <style>{css}</style>
      <div className="app">

        {/* Header */}
        <header className="header">
          <div className="avatar">😤</div>
          <div className="header-info">
            <div className="header-name">Cliente — Soporte TI</div>
            <div className="header-meta">
              <div className={`status-dot ${!sessionReady ? "offline" : isTyping ? "typing" : ""}`} />
              <span>
                {!sessionReady
                  ? "Sin sesión activa"
                  : isTyping
                  ? "escribiendo..."
                  : `en línea · turno ${turnCount}`}
              </span>
            </div>
          </div>
          {sessionReady && (
            <span className="ticket-tag">SIM-{String(turnCount).padStart(3, "0")}</span>
          )}
          <button
            className="btn-ghost"
            onClick={sessionReady ? resetSession : startSession}
            disabled={isTyping}
          >
            {sessionReady ? "cerrar caso" : "iniciar caso"}
          </button>
        </header>

        {/* Pantalla de inicio o mensajes */}
        {!sessionReady ? (
          <div className="start-screen">
            <div className="start-icon">🎧</div>
            <div className="start-title">Simulador de soporte TI</div>
            <div className="start-sub">
              Se te asignará un cliente con un problema técnico. No sabrás quién es ni qué le pasa hasta que hables con él.
            </div>
            <button className="btn-primary" onClick={startSession}>
              Iniciar caso
            </button>
          </div>
        ) : (
          <>
            <div className="messages">
              {messages.length === 0 && (
                <div className="day-label">
                  Caso iniciado — saluda al cliente para comenzar
                </div>
              )}

              {messages.map((msg, i) => (
                <div key={i} className={`row ${msg.role === "user" ? "agent" : "client"}`}>
                  <div className="row-label">
                    {msg.role === "user" ? "Tú" : "Cliente"}
                  </div>
                  <div className="bubble">{msg.content}</div>
                  <div className="bubble-time">{formatTime(timesRef.current[i])}</div>
                </div>
              ))}

              {isTyping && (
                <div className="row client">
                  <div className="row-label">Cliente</div>
                  <div className="typing-indicator">
                    <span /><span /><span />
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {error && (
              <div className="error-banner">
                <span>⚠</span> {error}
              </div>
            )}

            <div className="input-area">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Escribe tu respuesta al cliente…"
                disabled={isTyping}
                rows={1}
              />
              <button
                className={`send-btn ${isTyping ? "stop" : ""}`}
                onClick={isTyping ? cancelRequest : handleSubmit}
                disabled={!isTyping && !input.trim()}
                title={isTyping ? "Cancelar" : "Enviar"}
              >
                {isTyping ? (
                  <svg viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                )}
              </button>
            </div>
            <div className="input-hint">Enter para enviar · Shift+Enter para nueva línea</div>
          </>
        )}

      </div>
    </>
  );
}
