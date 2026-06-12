// useSoporteChat.js
// Maneja el estado del chat y la comunicación con la API de FastAPI

import { useState, useCallback, useRef } from "react";

const API_URL = "http://localhost:8000";

export function useSoporteChat() {
  const [messages, setMessages] = useState([]);   // solo para renderizar
  const [isTyping,  setIsTyping]  = useState(false);
  const [error,     setError]     = useState(null);
  const [sessionSystem, setSessionSystem] = useState(null); // system prompt de la sesión

  // historyRef es la fuente de verdad del historial
  // useState es asíncrono — la ref siempre tiene el valor actualizado
  const historyRef  = useRef([]);
  const abortRef    = useRef(null);

  // ── Iniciar sesión: pide el system prompt al backend ──────────────────────
  const startSession = useCallback(async () => {
    setError(null);
    try {
      const res  = await fetch(`${API_URL}/session/new`);
      const data = await res.json();
      setSessionSystem(data.system);
      historyRef.current = [];
      setMessages([]);
    } catch {
      setError("No se pudo conectar con la API. ¿Está corriendo el backend?");
    }
  }, []);

  // ── Enviar mensaje ─────────────────────────────────────────────────────────
  const sendMessage = useCallback(async (userText) => {
    if (!userText.trim() || isTyping) return;
    setError(null);

    // 1. Agregar mensaje del especialista a la ref y al estado visual
    const userMsg = { role: "user", content: userText };
    historyRef.current = [...historyRef.current, userMsg];
    setMessages([...historyRef.current]);

    // 2. Mostrar indicador "escribiendo..."
    setIsTyping(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        signal:  controller.signal,
        body: JSON.stringify({
          messages: historyRef.current,   // historial completo siempre actualizado
          system:   sessionSystem,        // mismo system prompt durante toda la sesión
        }),
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail || `Error ${res.status}`);
      }

      const data = await res.json();

      // 3. Agregar respuesta del cliente-IA a la ref y al estado visual
      const assistantMsg = { role: "assistant", content: data.message };
      historyRef.current = [...historyRef.current, assistantMsg];
      setMessages([...historyRef.current]);

    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || "Error al contactar la API");

      // Revertir el mensaje del usuario si hubo error
      historyRef.current = historyRef.current.slice(0, -1);
      setMessages([...historyRef.current]);
    } finally {
      setIsTyping(false);
      abortRef.current = null;
    }
  }, [isTyping, sessionSystem]);

  // ── Cancelar request en vuelo ──────────────────────────────────────────────
  const cancelRequest = useCallback(() => {
    abortRef.current?.abort();
    setIsTyping(false);
  }, []);

  // ── Reiniciar la sesión completamente ─────────────────────────────────────
  const resetSession = useCallback(() => {
    abortRef.current?.abort();
    historyRef.current = [];
    setMessages([]);
    setSessionSystem(null);
    setError(null);
    setIsTyping(false);
  }, []);

  return {
    messages,
    isTyping,
    error,
    sessionReady: !!sessionSystem,  // true cuando ya hay system prompt
    startSession,
    sendMessage,
    cancelRequest,
    resetSession,
  };
}
