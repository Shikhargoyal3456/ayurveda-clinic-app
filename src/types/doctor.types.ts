export type DoctorRole = "system" | "user" | "assistant";

export type SessionState =
    | "idle"
    | "connecting"
    | "listening"
    | "thinking"
    | "speaking"
    | "paused"
    | "ended"
    | "offline";

export interface DiagnosisItem {
    name: string;
    confidence: number;
    color: string;
}

export interface Message {
    id: string;
    role: DoctorRole;
    text: string;
    createdAt: string;
}

export interface SessionSummary {
    startedAt: string;
    endedAt: string;
    turns: number;
    keyTakeaway: string;
}
