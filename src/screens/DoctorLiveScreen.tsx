import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    Alert,
    Pressable,
    SafeAreaView,
    ScrollView,
    Share,
    StatusBar,
    StyleSheet,
    Text,
    View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";

import { BottomControls } from "../components/BottomControls";
import { DiagnosisPanel } from "../components/DiagnosisPanel";
import { FloatingControls } from "../components/FloatingControls";
import { TranscriptOverlay } from "../components/TranscriptOverlay";
import { Waveform } from "../components/Waveform";
import { useDocterAI } from "../hooks/useDocterAI";
import { useMicrophone } from "../hooks/useMicrophone";
import { useTTS } from "../hooks/useTTS";

const MAX_SILENCE_MS = 30 * 60 * 1000;

export default function DoctorLiveScreen() {
    const [sessionStarted, setSessionStarted] = useState(false);
    const [cameraEnabled, setCameraEnabled] = useState(true);
    const [paused, setPaused] = useState(false);
    const [liveStatus, setLiveStatus] = useState("Ready");
    const lastTranscriptRef = useRef("");
    const processingChunkRef = useRef(false);

    const {
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
    } = useDocterAI();
    const { isSpeaking, speak, stop: stopSpeaking } = useTTS();

    const handleAudioChunk = useCallback(
        async (uri: string) => {
            if (!sessionStarted || paused || processingChunkRef.current) {
                return;
            }
            processingChunkRef.current = true;
            try {
                const transcript = await transcribeAudio(uri);
                if (!transcript || transcript === lastTranscriptRef.current) {
                    return;
                }
                lastTranscriptRef.current = transcript;
                const reply = await sendPatientTurn(transcript);
                if (reply) {
                    await speak(reply);
                }
            } finally {
                processingChunkRef.current = false;
            }
        },
        [paused, sendPatientTurn, sessionStarted, speak, transcribeAudio]
    );

    const microphone = useMicrophone({ onAudioChunk: handleAudioChunk });

    const waveformMode = useMemo(() => {
        if (isSpeaking) {
            return "speaking" as const;
        }
        if (microphone.isRecording) {
            return "listening" as const;
        }
        return "idle" as const;
    }, [isSpeaking, microphone.isRecording]);

    const startSession = useCallback(async () => {
        if (sessionStarted) {
            return;
        }
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        resetSession();
        const greeting = beginSession();
        setSessionStarted(true);
        setPaused(false);
        setLiveStatus("Listening");
        const started = await microphone.start();
        if (!started) {
            setLiveStatus("Microphone blocked");
            return;
        }
        await speak(greeting);
    }, [beginSession, microphone, resetSession, sessionStarted, speak]);

    const endCurrentSession = useCallback(async () => {
        await microphone.stop();
        await stopSpeaking();
        setPaused(false);
        setSessionStarted(false);
        setLiveStatus("Ended");
        await endSession();
    }, [endSession, microphone, stopSpeaking]);

    const togglePause = useCallback(async () => {
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        if (paused) {
            const resumed = await microphone.start();
            if (resumed) {
                setPaused(false);
                setLiveStatus("Listening");
            }
            return;
        }
        await microphone.stop();
        await stopSpeaking();
        setPaused(true);
        setLiveStatus("Paused");
    }, [microphone, paused, stopSpeaking]);

    const toggleMic = useCallback(async () => {
        const active = await microphone.toggle();
        setPaused(!active);
        setLiveStatus(active ? "Listening" : "Mic off");
    }, [microphone]);

    const shareSummary = useCallback(async () => {
        const payload = summary
            ? `${summary.keyTakeaway}\n\nThis is AI guidance, not a substitute for in-person care.`
            : doctorTranscript || "Live AI Doctor session from Kash AI.";
        await Share.share({ message: payload });
    }, [doctorTranscript, summary]);

    const handleScreenShare = useCallback(() => {
        Alert.alert("Screen share", "Screen sharing can be connected to your native meeting SDK or Expo screen-capture flow.");
    }, []);

    const handleToggleCamera = useCallback(async () => {
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        setCameraEnabled((value) => !value);
    }, []);

    useEffect(() => {
        if (!sessionStarted) {
            return;
        }
        const timer = setInterval(() => {
            if (Date.now() - lastActivityAt > MAX_SILENCE_MS) {
                void endCurrentSession();
                Alert.alert("Session ended", "The consultation ended after 30 minutes of silence.");
            }
        }, 60_000);
        return () => clearInterval(timer);
    }, [endCurrentSession, lastActivityAt, sessionStarted]);

    useEffect(() => {
        if (sessionState === "offline") {
            setLiveStatus("Offline");
        } else if (isSpeaking) {
            setLiveStatus("Dr. Kash is speaking");
        } else if (microphone.isRecording) {
            setLiveStatus("Listening");
        }
    }, [isSpeaking, microphone.isRecording, sessionState]);

    useEffect(() => {
        return () => {
            void microphone.stop();
            void stopSpeaking();
        };
    }, [microphone, stopSpeaking]);

    return (
        <SafeAreaView style={styles.safe}>
            <StatusBar barStyle="light-content" />
            <LinearGradient
                colors={["#0a0f1e", "#0d1328", "#0a0f1e"]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={styles.container}
            >
                <FloatingControls
                    cameraEnabled={cameraEnabled}
                    onToggleCamera={handleToggleCamera}
                    onShareScreen={handleScreenShare}
                />

                <View style={styles.header}>
                    <View style={styles.avatarWrap}>
                        <View style={[styles.pulseRing, isSpeaking && styles.pulseRingSpeaking]} />
                        <View style={styles.avatarCore}>
                            <Text style={styles.avatarText}>DK</Text>
                        </View>
                    </View>
                    <View style={styles.headerCopy}>
                        <View style={styles.liveRow}>
                            <Text style={styles.title}>Dr. Kash AI</Text>
                            <View style={styles.liveBadge}>
                                <Text style={styles.liveBadgeText}>LIVE</Text>
                            </View>
                        </View>
                        <Text style={styles.subtitle}>{liveStatus}</Text>
                    </View>
                </View>

                <View style={styles.waveShell}>
                    <Waveform metering={microphone.metering} mode={waveformMode} />
                    <Text style={styles.waveLabel}>
                        {isSpeaking
                            ? "Dr. Kash is speaking..."
                            : microphone.isRecording
                              ? "Listening for your voice..."
                              : "Tap start to begin your consultation"}
                    </Text>
                </View>

                {!sessionStarted ? (
                    <Pressable style={styles.startButton} onPress={startSession}>
                        <MaterialCommunityIcons name="microphone-outline" color="#ffffff" size={26} />
                        <Text style={styles.startButtonText}>Start Consultation</Text>
                    </Pressable>
                ) : null}

                {error ? (
                    <View style={styles.errorBanner}>
                        <Text style={styles.errorText}>{error}</Text>
                    </View>
                ) : null}

                <ScrollView
                    style={styles.scroll}
                    contentContainerStyle={styles.scrollContent}
                    showsVerticalScrollIndicator={false}
                >
                    <TranscriptOverlay messages={messages} currentDoctorText={doctorTranscript} />
                    <DiagnosisPanel diagnoses={diagnoses} />
                    {summary ? (
                        <View style={styles.summaryCard}>
                            <Text style={styles.summaryTitle}>Session summary</Text>
                            <Text style={styles.summaryText}>{summary.keyTakeaway}</Text>
                            <Text style={styles.summaryMeta}>
                                {summary.turns} turns • {new Date(summary.startedAt).toLocaleTimeString()} to{" "}
                                {new Date(summary.endedAt).toLocaleTimeString()}
                            </Text>
                        </View>
                    ) : null}
                </ScrollView>

                <BottomControls
                    isMicActive={microphone.isRecording}
                    isPaused={paused}
                    onToggleMic={toggleMic}
                    onShare={shareSummary}
                    onPause={togglePause}
                    onEnd={endCurrentSession}
                />
            </LinearGradient>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    safe: {
        flex: 1,
        backgroundColor: "#0a0f1e",
    },
    container: {
        flex: 1,
        paddingHorizontal: 20,
        paddingTop: 18,
        paddingBottom: 22,
    },
    header: {
        flexDirection: "row",
        alignItems: "center",
        gap: 16,
        marginTop: 8,
    },
    avatarWrap: {
        width: 84,
        height: 84,
        alignItems: "center",
        justifyContent: "center",
    },
    pulseRing: {
        position: "absolute",
        width: 84,
        height: 84,
        borderRadius: 42,
        backgroundColor: "rgba(52, 211, 153, 0.14)",
        transform: [{ scale: 1 }],
    },
    pulseRingSpeaking: {
        backgroundColor: "rgba(96, 165, 250, 0.18)",
    },
    avatarCore: {
        width: 62,
        height: 62,
        borderRadius: 31,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#111b30",
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.2)",
    },
    avatarText: {
        color: "#f8fafc",
        fontSize: 22,
        fontWeight: "800",
    },
    headerCopy: {
        flex: 1,
        gap: 6,
    },
    liveRow: {
        flexDirection: "row",
        alignItems: "center",
        gap: 10,
    },
    title: {
        color: "#f8fafc",
        fontSize: 24,
        fontWeight: "800",
    },
    liveBadge: {
        paddingHorizontal: 10,
        paddingVertical: 5,
        borderRadius: 999,
        backgroundColor: "rgba(239, 68, 68, 0.18)",
        borderWidth: 1,
        borderColor: "rgba(248, 113, 113, 0.3)",
    },
    liveBadgeText: {
        color: "#fda4af",
        fontSize: 11,
        fontWeight: "800",
        letterSpacing: 0.9,
    },
    subtitle: {
        color: "#cbd5e1",
        fontSize: 14,
        fontWeight: "600",
    },
    waveShell: {
        alignItems: "center",
        justifyContent: "center",
        paddingVertical: 26,
        marginTop: 20,
        borderRadius: 30,
        backgroundColor: "rgba(15, 23, 42, 0.54)",
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.12)",
    },
    waveLabel: {
        marginTop: 16,
        color: "#cbd5e1",
        fontSize: 14,
    },
    startButton: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        minHeight: 68,
        borderRadius: 24,
        backgroundColor: "#0f766e",
        marginTop: 20,
        shadowColor: "#0f766e",
        shadowOpacity: 0.4,
        shadowRadius: 24,
        shadowOffset: { width: 0, height: 10 },
    },
    startButtonText: {
        color: "#ffffff",
        fontSize: 18,
        fontWeight: "800",
    },
    errorBanner: {
        marginTop: 16,
        padding: 14,
        borderRadius: 18,
        backgroundColor: "rgba(127, 29, 29, 0.52)",
        borderWidth: 1,
        borderColor: "rgba(248, 113, 113, 0.2)",
    },
    errorText: {
        color: "#fecaca",
        fontSize: 13,
        lineHeight: 18,
    },
    scroll: {
        flex: 1,
        marginTop: 18,
    },
    scrollContent: {
        gap: 14,
        paddingBottom: 16,
    },
    summaryCard: {
        backgroundColor: "#10182c",
        borderRadius: 24,
        padding: 18,
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.18)",
    },
    summaryTitle: {
        color: "#f8fafc",
        fontSize: 16,
        fontWeight: "700",
        marginBottom: 10,
    },
    summaryText: {
        color: "#e2e8f0",
        fontSize: 14,
        lineHeight: 21,
    },
    summaryMeta: {
        marginTop: 10,
        color: "#94a3b8",
        fontSize: 12,
    },
});
