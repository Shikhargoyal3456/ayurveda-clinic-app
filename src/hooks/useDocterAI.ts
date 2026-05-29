import { useCallback, useMemo, useRef, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import NetInfo from "@react-native-community/netinfo";

import { DOCTOR_SYSTEM_PROMPT } from "../constants/doctorPrompt";
import { DiagnosisItem, Message, SessionState, SessionSummary } from "../types/doctor.types";

const SESSION_STORAGE_KEY = "kash-ai-live-doctor-sessions";
const CLAUDE_MODEL = "claude-sonnet-4-20250514";

function getEnv(name: string): string {
    const processValue = typeof process !== "undefined" ? process.env?.[name] : undefined;
    return String(processValue || "").trim();
}

function makeMessage(role: Message["role"], text: string): Message {
    return {
        id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        role,
        text,
        createdAt: new Date().toISOString(),
    };
}

function extractDiagnosis(raw: string): DiagnosisItem[] {
    const fenced = raw.match(/```json\s*([\s\S]*?)```/i);
    const direct = raw.match(/\{\s*"diagnosis"\s*:\s*\[[\s\S]*?\]\s*\}/i);
    const candidate = fenced?.[1] || direct?.[0];
    if (!candidate) {
        return [];
    }
    try {
        const parsed = JSON.parse(candidate);
        if (!Array.isArray(parsed?.diagnosis)) {
            return [];
        }
        return parsed.diagnosis
            .map((item: DiagnosisItem) => ({
                name: String(item.name || "").trim(),
                confidence: Number(item.confidence || 0),
                color: String(item.color || "#3b82f6"),
            }))
            .filter((item: DiagnosisItem) => item.name)
            .slice(0, 3);
    } catch {
        return [];
    }
}

function stripDiagnosisJson(raw: string): string {
    return raw
        .replace(/```json[\s\S]*?```/gi, "")
        .replace(/\{\s*"diagnosis"\s*:\s*\[[\s\S]*?\]\s*\}/gi, "")
        .replace(/\s+/g, " ")
        .trim();
}

async function persistSession(payload: { messages: Message[]; summary: SessionSummary; diagnosis: DiagnosisItem[] }) {
    const existing = await AsyncStorage.getItem(SESSION_STORAGE_KEY);
    const parsed = existing ? JSON.parse(existing) : [];
    const next = Array.isArray(parsed) ? [payload, ...parsed].slice(0, 20) : [payload];
    await AsyncStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(next));
}

async function parseAnthropicStream(
    response: Response,
    onDelta: (text: string) => void
): Promise<string> {
    if (!response.body) {
        const json = await response.json();
        const fallbackText = json?.content?.[0]?.text || "";
        onDelta(String(fallbackText));
        return String(fallbackText);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let fullText = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) {
            break;
        }
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const eventBlock of events) {
            const dataLine = eventBlock
                .split("\n")
                .find((line) => line.startsWith("data: "));
            if (!dataLine) {
                continue;
            }
            const payload = dataLine.slice(6).trim();
            if (!payload || payload === "[DONE]") {
                continue;
            }
            try {
                const parsed = JSON.parse(payload);
                const deltaText = parsed?.delta?.text || parsed?.content_block?.text || "";
                if (deltaText) {
                    fullText += deltaText;
                    onDelta(fullText);
                }
            } catch {
                continue;
            }
        }
    }

    return fullText;
}

export function useDocterAI() {
    const anthropicApiKey = getEnv("ANTHROPIC_API_KEY") || getEnv("EXPO_PUBLIC_ANTHROPIC_API_KEY");
    const openAiApiKey = getEnv("OPENAI_API_KEY") || getEnv("EXPO_PUBLIC_OPENAI_API_KEY");
    const startedAtRef = useRef<string | null>(null);
    const lastActivityAtRef = useRef<number>(Date.now());
    const [messages, setMessages] = useState<Message[]>([]);
    const [diagnoses, setDiagnoses] = useState<DiagnosisItem[]>([]);
    const [doctorTranscript, setDoctorTranscript] = useState("");
    const [sessionState, setSessionState] = useState<SessionState>("idle");
    const [summary, setSummary] = useState<SessionSummary | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [lastActivityAt, setLastActivityAt] = useState<number>(Date.now());

    const beginSession = useCallback(() => {
        const greeting =
            "I'm Dr. Kash, your AI medical assistant. Tell me what feels most urgent right now, and I'll take it one step at a time. This is AI guidance, not a substitute for in-person care.";
        startedAtRef.current = new Date().toISOString();
        lastActivityAtRef.current = Date.now();
        setLastActivityAt(lastActivityAtRef.current);
        setSummary(null);
        setError(null);
        setDiagnoses([]);
        setDoctorTranscript(greeting);
        setMessages([makeMessage("assistant", greeting)]);
        setSessionState("listening");
        return greeting;
    }, []);

    const sendPatientTurn = useCallback(
        async (transcript: string) => {
            const text = transcript.trim();
            if (!text) {
                return "";
            }

            const netState = await NetInfo.fetch();
            if (!netState.isConnected) {
                setSessionState("offline");
                setError("You're offline right now. Reconnect to continue the consultation.");
                return "";
            }

            if (!anthropicApiKey) {
                setError("ANTHROPIC_API_KEY is missing.");
                return "";
            }

            const userMessage = makeMessage("user", text);
            const nextMessages = [...messages, userMessage];
            setMessages(nextMessages);
            setSessionState("thinking");
            setDoctorTranscript("");
            lastActivityAtRef.current = Date.now();
            setLastActivityAt(lastActivityAtRef.current);

            const anthropicMessages = nextMessages
                .filter((item) => item.role !== "system")
                .map((item) => ({
                    role: item.role === "assistant" ? "assistant" : "user",
                    content: item.text,
                }));

            try {
                const response = await fetch("https://api.anthropic.com/v1/messages", {
                    method: "POST",
                    headers: {
                        "content-type": "application/json",
                        "x-api-key": anthropicApiKey,
                        "anthropic-version": "2023-06-01",
                        "anthropic-dangerous-direct-browser-access": "true",
                    },
                    body: JSON.stringify({
                        model: CLAUDE_MODEL,
                        system: DOCTOR_SYSTEM_PROMPT,
                        messages: anthropicMessages,
                        max_tokens: 700,
                        temperature: 0.4,
                        stream: true,
                    }),
                });

                if (!response.ok) {
                    throw new Error(`Claude request failed with ${response.status}`);
                }

                const streamedText = await parseAnthropicStream(response, (partial) => {
                    setDoctorTranscript(stripDiagnosisJson(partial));
                    const parsedDiagnosis = extractDiagnosis(partial);
                    if (parsedDiagnosis.length) {
                        setDiagnoses(parsedDiagnosis);
                    }
                });

                const cleaned = stripDiagnosisJson(streamedText);
                const assistantMessage = makeMessage("assistant", cleaned);
                setMessages((current) => [...current, assistantMessage]);
                setDoctorTranscript(cleaned);
                setSessionState("listening");
                lastActivityAtRef.current = Date.now();
                setLastActivityAt(lastActivityAtRef.current);
                return cleaned;
            } catch (streamError) {
                setSessionState("listening");
                setError(streamError instanceof Error ? streamError.message : "The doctor connection was interrupted.");
                return "";
            }
        },
        [anthropicApiKey, messages]
    );

    const transcribeAudio = useCallback(
        async (uri: string) => {
            if (!openAiApiKey) {
                return "";
            }
            const formData = new FormData();
            formData.append("file", {
                uri,
                name: "doctor-live-audio.m4a",
                type: "audio/m4a",
            } as never);
            formData.append("model", "whisper-1");

            const response = await fetch("https://api.openai.com/v1/audio/transcriptions", {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${openAiApiKey}`,
                },
                body: formData,
            });

            if (!response.ok) {
                return "";
            }

            const payload = await response.json();
            return String(payload?.text || "").trim();
        },
        [openAiApiKey]
    );

    const endSession = useCallback(async () => {
        const summaryPayload: SessionSummary = {
            startedAt: startedAtRef.current || new Date().toISOString(),
            endedAt: new Date().toISOString(),
            turns: messages.length,
            keyTakeaway:
                messages
                    .slice()
                    .reverse()
                    .find((item) => item.role === "assistant")?.text || "Consultation ended before a final guidance message.",
        };
        setSummary(summaryPayload);
        setSessionState("ended");
        setLastActivityAt(Date.now());
        await persistSession({
            messages,
            summary: summaryPayload,
            diagnosis: diagnoses,
        });
        return summaryPayload;
    }, [diagnoses, messages]);

    const resetSession = useCallback(() => {
        setMessages([]);
        setDiagnoses([]);
        setDoctorTranscript("");
        setSummary(null);
        setError(null);
        setSessionState("idle");
        startedAtRef.current = null;
        lastActivityAtRef.current = Date.now();
        setLastActivityAt(lastActivityAtRef.current);
    }, []);

    return useMemo(
        () => ({
            messages,
            diagnoses,
            doctorTranscript,
            sessionState,
            summary,
            error,
            lastActivityAt,
            beginSession,
            sendPatientTurn,
            transcribeAudio,
            endSession,
            resetSession,
        }),
        [
            beginSession,
            diagnoses,
            doctorTranscript,
            endSession,
            error,
            messages,
            resetSession,
            sendPatientTurn,
            sessionState,
            summary,
            transcribeAudio,
            lastActivityAt,
        ]
    );
}
