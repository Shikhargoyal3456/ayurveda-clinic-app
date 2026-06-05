import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    Alert,
    Linking,
    Pressable,
    SafeAreaView,
    ScrollView,
    Share,
    StyleSheet,
    Text,
    View
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import NetInfo from "@react-native-community/netinfo";
import Constants from "expo-constants";
import { Audio } from "expo-av";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as FileSystem from "expo-file-system";
import * as Haptics from "expo-haptics";
import { LinearGradient } from "expo-linear-gradient";
import * as Speech from "expo-speech";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import Animated, {
    Easing,
    interpolate,
    useAnimatedStyle,
    useSharedValue,
    withRepeat,
    withTiming
} from "react-native-reanimated";

type TranscriptItem = {
    id: string;
    role: "doctor" | "patient" | "system";
    text: string;
};

type DiagnosisItem = {
    name: string;
    confidence: number;
    color: string;
};

const SILENCE_LIMIT_MS = 30 * 60 * 1000;
const CHUNK_MS = 2000;
const STORAGE_KEY = "kash-ai-mobile-live-doctor-sessions";
const FALLBACK_WS_URL = "ws://35.244.0.89:8000/ws/ai-doctor";

function getExtra(name: string): string {
    const extra = Constants.expoConfig?.extra || {};
    return String(extra[name] || "").trim();
}

function uid(prefix: string) {
    return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function normalizeMetering(value?: number) {
    if (typeof value !== "number") {
        return 0.08;
    }
    const clamped = Math.max(-60, Math.min(0, value));
    return Math.max(0.08, (clamped + 60) / 60);
}

function parseDiagnoses(text: string): DiagnosisItem[] {
    const lines = text.split(/\n|\. /).map((line) => line.trim()).filter(Boolean);
    const items: DiagnosisItem[] = [];
    const palette = ["#60a5fa", "#8b5cf6", "#f59e0b"];

    for (const line of lines) {
        const match = line.match(/(?:\d+[\).\s-]*)?([A-Za-z /()-]+?)(?:\s*[-:(]\s*|\s+)(\d{1,3})%/);
        if (!match) continue;
        items.push({
            name: match[1].trim(),
            confidence: Math.max(1, Math.min(100, Number(match[2]))),
            color: palette[items.length % palette.length]
        });
        if (items.length === 3) {
            break;
        }
    }
    return items;
}

function detectEmergency(text: string) {
    const haystack = text.toLowerCase();
    return [
        "chest pain",
        "difficulty breathing",
        "trouble breathing",
        "left arm",
        "stroke",
        "severe bleeding",
        "passed out",
        "fainted",
        "seizure",
        "suicidal"
    ].some((term) => haystack.includes(term));
}

function WaveBar({ index, meter, speaking }: { index: number; meter: number; speaking: boolean }) {
    const level = useSharedValue(0.16);

    useEffect(() => {
        level.value = withRepeat(
            withTiming(speaking ? 0.8 : Math.max(0.18, meter * (0.7 + ((index % 6) * 0.07))), {
                duration: speaking ? 320 : 180,
                easing: Easing.inOut(Easing.ease)
            }),
            -1,
            true
        );
    }, [index, level, meter, speaking]);

    const style = useAnimatedStyle(() => ({
        height: interpolate(level.value, [0, 1], [12, 108]),
        backgroundColor: speaking ? "#60a5fa" : "#34d399",
        opacity: speaking ? 0.96 : 0.84
    }));

    return <Animated.View style={[styles.waveBar, style]} />;
}

export default function DoctorLiveScreen() {
    const cameraRef = useRef<CameraView | null>(null);
    const socketRef = useRef<WebSocket | null>(null);
    const recordingRef = useRef<Audio.Recording | null>(null);
    const loopActiveRef = useRef(false);
    const mountedRef = useRef(true);
    const cameraTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const lastActivityRef = useRef(Date.now());
    const audioMeterRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const [cameraPermission, requestCameraPermission] = useCameraPermissions();
    const [hasMicPermission, setHasMicPermission] = useState<boolean | null>(null);
    const [sessionStarted, setSessionStarted] = useState(false);
    const [paused, setPaused] = useState(false);
    const [micEnabled, setMicEnabled] = useState(true);
    const [cameraEnabled, setCameraEnabled] = useState(true);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [statusText, setStatusText] = useState("Ready");
    const [doctorText, setDoctorText] = useState("Doctor responses will appear here.");
    const [patientText, setPatientText] = useState("Your live transcript will appear here.");
    const [transcript, setTranscript] = useState<TranscriptItem[]>([
        {
            id: uid("doctor"),
            role: "doctor",
            text: "I'm Dr. Kash, your AI medical assistant. For final diagnosis and treatment, please consult a real doctor."
        }
    ]);
    const [diagnoses, setDiagnoses] = useState<DiagnosisItem[]>([]);
    const [meter, setMeter] = useState(0.08);
    const [isOffline, setIsOffline] = useState(false);
    const [showEmergency, setShowEmergency] = useState(false);
    const [summary, setSummary] = useState<string>("");

    const wsUrl = getExtra("aiDoctorWsUrl") || FALLBACK_WS_URL;
    const openAiApiKey = getExtra("openAiApiKey");

    const appendTranscript = useCallback((role: TranscriptItem["role"], text: string) => {
        if (!text) return;
        setTranscript((current) => [...current, { id: uid(role), role, text }].slice(-40));
        lastActivityRef.current = Date.now();
    }, []);

    const saveSession = useCallback(async (finalSummary: string) => {
        const payload = {
            createdAt: new Date().toISOString(),
            summary: finalSummary,
            transcript,
            diagnoses
        };
        const existing = await AsyncStorage.getItem(STORAGE_KEY);
        const parsed = existing ? JSON.parse(existing) : [];
        const next = Array.isArray(parsed) ? [payload, ...parsed].slice(0, 20) : [payload];
        await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    }, [diagnoses, transcript]);

    const speak = useCallback((text: string) => {
        Speech.stop();
        setIsSpeaking(true);
        Speech.speak(text, {
            language: "en-US",
            rate: 0.97,
            pitch: 1,
            onDone: () => setIsSpeaking(false),
            onStopped: () => setIsSpeaking(false),
            onError: () => setIsSpeaking(false)
        });
    }, []);

    const handleDoctorText = useCallback((text: string) => {
        setDoctorText(text);
        appendTranscript("doctor", text);
        const parsed = parseDiagnoses(text);
        if (parsed.length) {
            setDiagnoses(parsed);
        }
        if (detectEmergency(text)) {
            setShowEmergency(true);
        }
        speak(text);
    }, [appendTranscript, speak]);

    const sendJson = useCallback((payload: object) => {
        if (socketRef.current?.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify(payload));
        }
    }, []);

    const connectSocket = useCallback(async () => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            return;
        }

        await new Promise<void>((resolve, reject) => {
            const socket = new WebSocket(wsUrl);
            socketRef.current = socket;

            socket.onopen = () => {
                setStatusText("Connected");
                resolve();
            };

            socket.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data);
                    if (payload.type === "status" && payload.detail) {
                        setStatusText(payload.detail);
                    }
                    if (payload.type === "transcript" && payload.text) {
                        setPatientText(payload.text);
                        appendTranscript("patient", payload.text);
                        if (detectEmergency(payload.text)) {
                            setShowEmergency(true);
                        }
                    }
                    if (payload.type === "ai_message" && payload.text) {
                        handleDoctorText(payload.text);
                    }
                    if (payload.type === "emergency" && payload.text) {
                        setShowEmergency(true);
                        setStatusText("Emergency guidance");
                        appendTranscript("system", payload.text);
                    }
                    if (payload.type === "error" && payload.message) {
                        appendTranscript("system", payload.message);
                    }
                } catch {
                    appendTranscript("system", "Received an unreadable message from the backend.");
                }
            };

            socket.onerror = () => {
                setStatusText("Connection issue");
                reject(new Error("socket_failed"));
            };

            socket.onclose = () => {
                setStatusText("Disconnected");
            };
        });
    }, [appendTranscript, handleDoctorText, wsUrl]);

    const transcribeChunk = useCallback(async (uri: string) => {
        if (!openAiApiKey) {
            return "";
        }
        const formData = new FormData();
        formData.append("model", "whisper-1");
        formData.append("file", {
            uri,
            name: "doctor-live-audio.m4a",
            type: "audio/m4a"
        } as never);

        const response = await fetch("https://api.openai.com/v1/audio/transcriptions", {
            method: "POST",
            headers: {
                Authorization: `Bearer ${openAiApiKey}`
            },
            body: formData
        });

        if (!response.ok) {
            return "";
        }

        const payload = await response.json();
        return String(payload?.text || "").trim();
    }, [openAiApiKey]);

    const stopRecording = useCallback(async () => {
        if (audioMeterRef.current) {
            clearInterval(audioMeterRef.current);
            audioMeterRef.current = null;
        }
        if (!recordingRef.current) {
            return null;
        }
        const recording = recordingRef.current;
        recordingRef.current = null;
        await recording.stopAndUnloadAsync();
        return recording.getURI();
    }, []);

    const recordLoop = useCallback(async () => {
        while (loopActiveRef.current && mountedRef.current) {
            if (!micEnabled || paused) {
                await new Promise((resolve) => setTimeout(resolve, 300));
                continue;
            }

            const recording = new Audio.Recording();
            recordingRef.current = recording;
            await recording.prepareToRecordAsync({
                ...Audio.RecordingOptionsPresets.HIGH_QUALITY,
                isMeteringEnabled: true
            });
            await recording.startAsync();

            audioMeterRef.current = setInterval(async () => {
                try {
                    const status = await recording.getStatusAsync();
                    if (status.isLoaded) {
                        setMeter(normalizeMetering(status.metering));
                    }
                } catch {
                    setMeter(0.08);
                }
            }, 120);

            await new Promise((resolve) => setTimeout(resolve, CHUNK_MS));
            const uri = await stopRecording();
            if (!uri) {
                continue;
            }

            try {
                const base64 = await FileSystem.readAsStringAsync(uri, {
                    encoding: FileSystem.EncodingType.Base64
                });
                sendJson({
                    type: "audio_chunk",
                    mime_type: "audio/m4a",
                    audio: base64
                });
            } catch {
                appendTranscript("system", "Audio chunk upload failed.");
            }

            try {
                const text = await transcribeChunk(uri);
                if (text) {
                    setPatientText(text);
                    sendJson({ type: "user_text", text });
                    if (detectEmergency(text)) {
                        setShowEmergency(true);
                    }
                }
            } catch {
                appendTranscript("system", "Transcription failed for an audio chunk.");
            }
        }
    }, [appendTranscript, micEnabled, paused, sendJson, stopRecording, transcribeChunk]);

    const startCameraFrames = useCallback(() => {
        if (cameraTimerRef.current) {
            clearInterval(cameraTimerRef.current);
        }
        cameraTimerRef.current = setInterval(async () => {
            if (!cameraEnabled || !cameraRef.current || paused) {
                return;
            }
            try {
                const frame = await cameraRef.current.takePictureAsync({
                    base64: true,
                    quality: 0.45,
                    skipProcessing: true
                });
                if (frame?.base64) {
                    sendJson({
                        type: "video_frame",
                        mime_type: "image/jpeg",
                        image: frame.base64
                    });
                }
            } catch {
                return;
            }
        }, 4000);
    }, [cameraEnabled, paused, sendJson]);

    const requestPermissions = useCallback(async () => {
        const cam = cameraPermission?.granted ? cameraPermission : await requestCameraPermission();
        const mic = await Audio.requestPermissionsAsync();
        const granted = Boolean(cam.granted) && mic.status === "granted";
        setHasMicPermission(mic.status === "granted");
        return granted;
    }, [cameraPermission, requestCameraPermission]);

    const startSession = useCallback(async () => {
        const net = await NetInfo.fetch();
        setIsOffline(!net.isConnected);
        if (!net.isConnected) {
            setStatusText("Offline");
            Alert.alert("Offline", "Internet is required for the live AI doctor consultation.");
            return;
        }

        const granted = await requestPermissions();
        if (!granted) {
            Alert.alert("Permissions needed", "Please allow camera and microphone access to continue.");
            return;
        }

        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        await Audio.setAudioModeAsync({
            allowsRecordingIOS: true,
            playsInSilentModeIOS: true,
            shouldDuckAndroid: true,
            playThroughEarpieceAndroid: false
        });

        await connectSocket();
        setSessionStarted(true);
        setPaused(false);
        setShowEmergency(false);
        setSummary("");
        setStatusText("Listening");
        loopActiveRef.current = true;
        void recordLoop();
        startCameraFrames();
    }, [connectSocket, recordLoop, requestPermissions, startCameraFrames]);

    const endSession = useCallback(async () => {
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
        loopActiveRef.current = false;
        if (cameraTimerRef.current) {
            clearInterval(cameraTimerRef.current);
            cameraTimerRef.current = null;
        }
        await stopRecording().catch(() => null);
        Speech.stop();
        if (socketRef.current?.readyState === WebSocket.OPEN) {
            sendJson({ type: "end_consultation" });
            socketRef.current.close();
        }
        socketRef.current = null;
        setSessionStarted(false);
        setPaused(false);
        setMeter(0.08);
        setStatusText("Session ended");
        const finalSummary =
            transcript.slice(-3).map((item) => `${item.role === "doctor" ? "Dr. Kash" : "You"}: ${item.text}`).join("\n") ||
            "Session ended.";
        setSummary(finalSummary);
        await saveSession(finalSummary);
    }, [saveSession, sendJson, stopRecording, transcript]);

    const togglePause = useCallback(async () => {
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        setPaused((current) => !current);
        setStatusText((current) => (current === "Paused" ? "Listening" : "Paused"));
    }, []);

    const toggleMic = useCallback(async () => {
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        setMicEnabled((current) => !current);
        setStatusText((current) => (current === "Microphone muted" ? "Listening" : "Microphone muted"));
    }, []);

    const toggleCamera = useCallback(async () => {
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        setCameraEnabled((current) => !current);
    }, []);

    const shareSession = useCallback(async () => {
        const text = summary || doctorText || "Live AI doctor consultation from Kash AI.";
        await Share.share({ message: text });
    }, [doctorText, summary]);

    useEffect(() => {
        mountedRef.current = true;
        const unsubscribe = NetInfo.addEventListener((state) => {
            setIsOffline(!state.isConnected);
        });
        return () => {
            mountedRef.current = false;
            unsubscribe();
            loopActiveRef.current = false;
            Speech.stop();
            if (socketRef.current) {
                socketRef.current.close();
            }
        };
    }, []);

    useEffect(() => {
        const timer = setInterval(() => {
            if (sessionStarted && Date.now() - lastActivityRef.current > SILENCE_LIMIT_MS) {
                void endSession();
                Alert.alert("Session ended", "The session was ended after 30 minutes of silence.");
            }
        }, 60000);
        return () => clearInterval(timer);
    }, [endSession, sessionStarted]);

    const waveformMode = useMemo(() => (isSpeaking ? "speaking" : sessionStarted && micEnabled && !paused ? "listening" : "idle"), [
        isSpeaking,
        micEnabled,
        paused,
        sessionStarted
    ]);

    return (
        <SafeAreaView style={styles.safe}>
            <LinearGradient colors={["#0a0f1e", "#0f172a", "#0a0f1e"]} style={styles.container}>
                <FloatingAction icon={cameraEnabled ? "camera-off-outline" : "camera-outline"} onPress={toggleCamera} top={118} />
                <FloatingAction icon="share-variant-outline" onPress={shareSession} top={184} />

                <View style={styles.header}>
                    <View style={styles.headerLeft}>
                        <View style={styles.avatarWrap}>
                            <View style={[styles.avatarPulse, isSpeaking && styles.avatarPulseSpeaking]} />
                            <View style={styles.avatarCore}>
                                <Text style={styles.avatarLabel}>DK</Text>
                            </View>
                        </View>
                        <View style={styles.headerCopy}>
                            <View style={styles.headerRow}>
                                <Text style={styles.title}>Dr. Kash AI</Text>
                                <View style={styles.liveBadge}>
                                    <Text style={styles.liveBadgeText}>LIVE</Text>
                                </View>
                            </View>
                            <Text style={styles.subtitle}>{statusText}</Text>
                        </View>
                    </View>
                </View>

                <View style={styles.cameraCard}>
                    {cameraEnabled && cameraPermission?.granted ? (
                        <CameraView ref={cameraRef} facing="front" style={styles.camera} />
                    ) : (
                        <View style={styles.cameraFallback}>
                            <MaterialCommunityIcons color="#94a3b8" name="camera-off-outline" size={42} />
                            <Text style={styles.cameraFallbackText}>Camera preview is off.</Text>
                        </View>
                    )}
                    <View style={styles.cameraOverlay}>
                        <Text style={styles.cameraOverlayText}>{isOffline ? "Offline" : sessionStarted ? "Connected to backend" : "Ready to start"}</Text>
                        <Text style={styles.cameraOverlayHint}>
                            {cameraEnabled ? "Show the affected area clearly for visual review." : "Turn the camera back on if you want to show symptoms."}
                        </Text>
                    </View>
                </View>

                <View style={styles.waveCard}>
                    <View style={styles.waveRow}>
                        {Array.from({ length: 25 }).map((_, index) => (
                            <WaveBar key={index} index={index} meter={meter} speaking={waveformMode === "speaking"} />
                        ))}
                    </View>
                    <Text style={styles.waveText}>
                        {isSpeaking ? "Dr. Kash is speaking..." : sessionStarted ? "Listening to your voice..." : "Tap Start to begin"}
                    </Text>
                </View>

                {!sessionStarted ? (
                    <Pressable onPress={startSession} style={styles.startButton}>
                        <MaterialCommunityIcons color="#fff" name="microphone-outline" size={24} />
                        <Text style={styles.startButtonText}>Start Consultation</Text>
                    </Pressable>
                ) : null}

                {showEmergency ? (
                    <Pressable onPress={() => Linking.openURL("tel:112")} style={styles.emergencyCard}>
                        <Text style={styles.emergencyTitle}>Emergency support</Text>
                        <Text style={styles.emergencyText}>
                            This sounds concerning. Please call emergency services now or have someone take you to the ER.
                        </Text>
                    </Pressable>
                ) : null}

                {hasMicPermission === false ? (
                    <View style={styles.noticeCard}>
                        <Text style={styles.noticeText}>Microphone access is required for voice consultation.</Text>
                    </View>
                ) : null}

                <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false} style={styles.scroll}>
                    <View style={styles.transcriptCard}>
                        <Text style={styles.cardTitle}>Live transcript</Text>
                        {transcript.slice(-6).map((item) => (
                            <View key={item.id} style={[styles.transcriptBubble, item.role === "doctor" ? styles.doctorBubble : item.role === "patient" ? styles.patientBubble : styles.systemBubble]}>
                                <Text style={styles.transcriptRole}>{item.role === "doctor" ? "Dr. Kash" : item.role === "patient" ? "You" : "System"}</Text>
                                <Text style={styles.transcriptText}>{item.text}</Text>
                            </View>
                        ))}
                    </View>

                    <View style={styles.dualCardRow}>
                        <View style={styles.captionCard}>
                            <Text style={styles.captionLabel}>You</Text>
                            <Text style={styles.captionText}>{patientText}</Text>
                        </View>
                        <View style={styles.captionCard}>
                            <Text style={styles.captionLabel}>Dr. Kash</Text>
                            <Text style={styles.captionText}>{doctorText}</Text>
                        </View>
                    </View>

                    <View style={styles.diagnosisCard}>
                        <Text style={styles.cardTitle}>Possible diagnoses</Text>
                        <Text style={styles.cardHint}>These update as the doctor gathers more information.</Text>
                        {diagnoses.length ? (
                            diagnoses.map((item) => (
                                <View key={item.name} style={styles.diagnosisRow}>
                                    <View style={styles.diagnosisHeader}>
                                        <Text style={styles.diagnosisName}>{item.name}</Text>
                                        <Text style={styles.diagnosisValue}>{item.confidence}%</Text>
                                    </View>
                                    <View style={styles.diagnosisTrack}>
                                        <View style={[styles.diagnosisFill, { width: `${item.confidence}%`, backgroundColor: item.color }]} />
                                    </View>
                                </View>
                            ))
                        ) : (
                            <Text style={styles.placeholderText}>Diagnosis confidence bars will appear once the doctor mentions likely possibilities.</Text>
                        )}
                    </View>

                    {summary ? (
                        <View style={styles.summaryCard}>
                            <Text style={styles.cardTitle}>Session summary</Text>
                            <Text style={styles.summaryText}>{summary}</Text>
                        </View>
                    ) : null}
                </ScrollView>

                <View style={styles.bottomControls}>
                    <BottomAction icon={micEnabled ? "microphone-outline" : "microphone-off"} label={micEnabled ? "Mic" : "Unmute"} onPress={toggleMic} />
                    <BottomAction icon="share-variant-outline" label="Share" onPress={shareSession} />
                    <BottomAction icon={paused ? "play-outline" : "pause"} label={paused ? "Resume" : "Pause"} onPress={togglePause} />
                    <BottomAction danger icon="close" label="End" onPress={endSession} />
                </View>
            </LinearGradient>
        </SafeAreaView>
    );
}

function FloatingAction({
    icon,
    onPress,
    top
}: {
    icon: React.ComponentProps<typeof MaterialCommunityIcons>["name"];
    onPress: () => void;
    top: number;
}) {
    return (
        <Pressable onPress={onPress} style={[styles.floatingButton, { top }]}>
            <MaterialCommunityIcons color="#f8fafc" name={icon} size={22} />
        </Pressable>
    );
}

function BottomAction({
    icon,
    label,
    onPress,
    danger = false
}: {
    icon: React.ComponentProps<typeof MaterialCommunityIcons>["name"];
    label: string;
    onPress: () => void;
    danger?: boolean;
}) {
    return (
        <Pressable onPress={onPress} style={[styles.bottomButton, danger && styles.bottomButtonDanger]}>
            <MaterialCommunityIcons color="#fff" name={icon} size={22} />
            <Text style={styles.bottomButtonText}>{label}</Text>
        </Pressable>
    );
}

const styles = StyleSheet.create({
    safe: {
        flex: 1,
        backgroundColor: "#0a0f1e"
    },
    container: {
        flex: 1,
        paddingHorizontal: 18,
        paddingTop: 14,
        paddingBottom: 20
    },
    header: {
        marginBottom: 16
    },
    headerLeft: {
        flexDirection: "row",
        alignItems: "center",
        gap: 14
    },
    avatarWrap: {
        width: 74,
        height: 74,
        alignItems: "center",
        justifyContent: "center"
    },
    avatarPulse: {
        position: "absolute",
        width: 74,
        height: 74,
        borderRadius: 37,
        backgroundColor: "rgba(52, 211, 153, 0.16)"
    },
    avatarPulseSpeaking: {
        backgroundColor: "rgba(96, 165, 250, 0.2)"
    },
    avatarCore: {
        width: 58,
        height: 58,
        borderRadius: 29,
        backgroundColor: "#111827",
        alignItems: "center",
        justifyContent: "center",
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.16)"
    },
    avatarLabel: {
        color: "#f8fafc",
        fontWeight: "800",
        fontSize: 20
    },
    headerCopy: {
        flex: 1
    },
    headerRow: {
        flexDirection: "row",
        alignItems: "center",
        gap: 10
    },
    title: {
        color: "#f8fafc",
        fontSize: 24,
        fontWeight: "800"
    },
    liveBadge: {
        paddingHorizontal: 10,
        paddingVertical: 5,
        borderRadius: 999,
        backgroundColor: "rgba(239, 68, 68, 0.18)"
    },
    liveBadgeText: {
        color: "#fecaca",
        fontWeight: "800",
        fontSize: 11,
        letterSpacing: 0.8
    },
    subtitle: {
        color: "#cbd5e1",
        marginTop: 6,
        fontSize: 14
    },
    floatingButton: {
        position: "absolute",
        right: 20,
        zIndex: 20,
        width: 52,
        height: 52,
        borderRadius: 26,
        backgroundColor: "rgba(15, 23, 42, 0.84)",
        alignItems: "center",
        justifyContent: "center",
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.18)"
    },
    cameraCard: {
        height: 240,
        borderRadius: 28,
        overflow: "hidden",
        backgroundColor: "#111827",
        marginBottom: 16
    },
    camera: {
        flex: 1
    },
    cameraFallback: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        gap: 10
    },
    cameraFallbackText: {
        color: "#94a3b8"
    },
    cameraOverlay: {
        position: "absolute",
        left: 14,
        right: 14,
        bottom: 14,
        padding: 14,
        borderRadius: 18,
        backgroundColor: "rgba(15, 23, 42, 0.7)"
    },
    cameraOverlayText: {
        color: "#f8fafc",
        fontWeight: "700"
    },
    cameraOverlayHint: {
        marginTop: 6,
        color: "#cbd5e1",
        lineHeight: 18
    },
    waveCard: {
        borderRadius: 24,
        backgroundColor: "rgba(15, 23, 42, 0.76)",
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.12)",
        padding: 18,
        marginBottom: 16
    },
    waveRow: {
        minHeight: 118,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 6
    },
    waveBar: {
        width: 7,
        borderRadius: 999
    },
    waveText: {
        marginTop: 12,
        textAlign: "center",
        color: "#cbd5e1"
    },
    startButton: {
        minHeight: 64,
        borderRadius: 22,
        backgroundColor: "#2563eb",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "row",
        gap: 10,
        marginBottom: 16
    },
    startButtonText: {
        color: "#fff",
        fontSize: 18,
        fontWeight: "800"
    },
    emergencyCard: {
        padding: 16,
        borderRadius: 22,
        backgroundColor: "rgba(127, 29, 29, 0.56)",
        borderWidth: 1,
        borderColor: "rgba(248, 113, 113, 0.24)",
        marginBottom: 16
    },
    emergencyTitle: {
        color: "#fee2e2",
        fontSize: 16,
        fontWeight: "800",
        marginBottom: 8
    },
    emergencyText: {
        color: "#fecaca",
        lineHeight: 20
    },
    noticeCard: {
        padding: 14,
        borderRadius: 18,
        backgroundColor: "rgba(51, 65, 85, 0.8)",
        marginBottom: 16
    },
    noticeText: {
        color: "#e2e8f0"
    },
    scroll: {
        flex: 1
    },
    scrollContent: {
        gap: 14,
        paddingBottom: 14
    },
    transcriptCard: {
        backgroundColor: "rgba(15, 23, 42, 0.82)",
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.12)",
        borderRadius: 24,
        padding: 16,
        gap: 12
    },
    cardTitle: {
        color: "#f8fafc",
        fontWeight: "800",
        fontSize: 16
    },
    transcriptBubble: {
        padding: 14,
        borderRadius: 18
    },
    doctorBubble: {
        backgroundColor: "rgba(15, 118, 110, 0.18)"
    },
    patientBubble: {
        backgroundColor: "rgba(37, 99, 235, 0.18)"
    },
    systemBubble: {
        backgroundColor: "rgba(148, 163, 184, 0.12)"
    },
    transcriptRole: {
        color: "#93c5fd",
        textTransform: "uppercase",
        letterSpacing: 0.8,
        fontWeight: "800",
        fontSize: 11,
        marginBottom: 6
    },
    transcriptText: {
        color: "#e2e8f0",
        lineHeight: 20
    },
    dualCardRow: {
        flexDirection: "row",
        gap: 12
    },
    captionCard: {
        flex: 1,
        backgroundColor: "rgba(15, 23, 42, 0.82)",
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.12)",
        borderRadius: 22,
        padding: 16
    },
    captionLabel: {
        color: "#60a5fa",
        fontSize: 11,
        fontWeight: "800",
        textTransform: "uppercase",
        letterSpacing: 0.8,
        marginBottom: 8
    },
    captionText: {
        color: "#e2e8f0",
        lineHeight: 20
    },
    diagnosisCard: {
        backgroundColor: "rgba(15, 23, 42, 0.82)",
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.12)",
        borderRadius: 24,
        padding: 16,
        gap: 12
    },
    cardHint: {
        color: "#94a3b8",
        lineHeight: 18
    },
    diagnosisRow: {
        gap: 8
    },
    diagnosisHeader: {
        flexDirection: "row",
        justifyContent: "space-between",
        gap: 12
    },
    diagnosisName: {
        flex: 1,
        color: "#e2e8f0",
        fontWeight: "700"
    },
    diagnosisValue: {
        color: "#cbd5e1",
        fontWeight: "700"
    },
    diagnosisTrack: {
        height: 10,
        borderRadius: 999,
        backgroundColor: "#1e293b",
        overflow: "hidden"
    },
    diagnosisFill: {
        height: "100%",
        borderRadius: 999
    },
    placeholderText: {
        color: "#cbd5e1",
        lineHeight: 18
    },
    summaryCard: {
        backgroundColor: "rgba(15, 23, 42, 0.82)",
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.12)",
        borderRadius: 24,
        padding: 16
    },
    summaryText: {
        color: "#e2e8f0",
        lineHeight: 20,
        marginTop: 10
    },
    bottomControls: {
        flexDirection: "row",
        gap: 10,
        marginTop: 12
    },
    bottomButton: {
        flex: 1,
        minHeight: 66,
        borderRadius: 22,
        backgroundColor: "#111827",
        alignItems: "center",
        justifyContent: "center",
        gap: 6
    },
    bottomButtonDanger: {
        backgroundColor: "#dc2626"
    },
    bottomButtonText: {
        color: "#fff",
        fontSize: 12,
        fontWeight: "800"
    }
});
