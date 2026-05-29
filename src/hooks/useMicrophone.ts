import { useCallback, useEffect, useRef, useState } from "react";
import { Audio } from "expo-av";
import * as Haptics from "expo-haptics";

type ChunkHandler = (uri: string) => Promise<void> | void;

interface UseMicrophoneOptions {
    chunkDurationMs?: number;
    onAudioChunk?: ChunkHandler;
}

const DEFAULT_CHUNK_MS = 2000;

function normalizeMetering(value: number | undefined): number {
    if (typeof value !== "number") {
        return 0.06;
    }
    const clamped = Math.min(0, Math.max(-60, value));
    return Math.max(0.04, (clamped + 60) / 60);
}

export function useMicrophone(options: UseMicrophoneOptions = {}) {
    const { chunkDurationMs = DEFAULT_CHUNK_MS, onAudioChunk } = options;
    const recordingRef = useRef<Audio.Recording | null>(null);
    const chunkTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const meterTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const unmountedRef = useRef(false);
    const [hasPermission, setHasPermission] = useState<boolean | null>(null);
    const [isRecording, setIsRecording] = useState(false);
    const [metering, setMetering] = useState(0.06);
    const [error, setError] = useState<string | null>(null);

    const clearTimers = useCallback(() => {
        if (chunkTimerRef.current) {
            clearTimeout(chunkTimerRef.current);
            chunkTimerRef.current = null;
        }
        if (meterTimerRef.current) {
            clearInterval(meterTimerRef.current);
            meterTimerRef.current = null;
        }
    }, []);

    const monitorMetering = useCallback(() => {
        if (meterTimerRef.current) {
            clearInterval(meterTimerRef.current);
        }
        meterTimerRef.current = setInterval(async () => {
            const recording = recordingRef.current;
            if (!recording) {
                return;
            }
            try {
                const status = await recording.getStatusAsync();
                if (!status.isLoaded || !status.canRecord) {
                    return;
                }
                setMetering(normalizeMetering(status.metering));
            } catch {
                setMetering(0.06);
            }
        }, 100);
    }, []);

    const prepareRecording = useCallback(async () => {
        const recording = new Audio.Recording();
        await recording.prepareToRecordAsync({
            ...Audio.RecordingOptionsPresets.HIGH_QUALITY,
            android: {
                ...Audio.RecordingOptionsPresets.HIGH_QUALITY.android,
                extension: ".m4a",
            },
            ios: {
                ...Audio.RecordingOptionsPresets.HIGH_QUALITY.ios,
                extension: ".m4a",
                linearPCMIsFloat: false,
            },
            isMeteringEnabled: true,
        });
        await recording.startAsync();
        recordingRef.current = recording;
        monitorMetering();
    }, [monitorMetering]);

    const flushChunk = useCallback(
        async (restart: boolean) => {
            const activeRecording = recordingRef.current;
            if (!activeRecording) {
                return;
            }
            recordingRef.current = null;
            try {
                await activeRecording.stopAndUnloadAsync();
                const uri = activeRecording.getURI();
                if (uri && onAudioChunk) {
                    await onAudioChunk(uri);
                }
            } catch {
                setError("Could not process microphone audio.");
            }
            if (!unmountedRef.current && restart && isRecording) {
                await prepareRecording();
            }
        },
        [isRecording, onAudioChunk, prepareRecording]
    );

    const scheduleChunk = useCallback(() => {
        if (chunkTimerRef.current) {
            clearTimeout(chunkTimerRef.current);
        }
        chunkTimerRef.current = setTimeout(async () => {
            await flushChunk(true);
            if (!unmountedRef.current && isRecording) {
                scheduleChunk();
            }
        }, chunkDurationMs);
    }, [chunkDurationMs, flushChunk, isRecording]);

    const requestPermission = useCallback(async () => {
        const permission = await Audio.requestPermissionsAsync();
        const granted = permission.status === "granted";
        setHasPermission(granted);
        if (!granted) {
            setError("Microphone permission is required.");
        }
        return granted;
    }, []);

    const start = useCallback(async () => {
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        setError(null);
        const granted = hasPermission ?? (await requestPermission());
        if (!granted) {
            return false;
        }
        await Audio.setAudioModeAsync({
            allowsRecordingIOS: true,
            playsInSilentModeIOS: true,
            shouldDuckAndroid: true,
            playThroughEarpieceAndroid: false,
        });
        setIsRecording(true);
        await prepareRecording();
        scheduleChunk();
        return true;
    }, [hasPermission, prepareRecording, requestPermission, scheduleChunk]);

    const stop = useCallback(async () => {
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        setIsRecording(false);
        clearTimers();
        await flushChunk(false);
        setMetering(0.06);
    }, [clearTimers, flushChunk]);

    const toggle = useCallback(async () => {
        if (isRecording) {
            await stop();
            return false;
        }
        return start();
    }, [isRecording, start, stop]);

    useEffect(() => {
        return () => {
            unmountedRef.current = true;
            clearTimers();
            if (recordingRef.current) {
                void recordingRef.current.stopAndUnloadAsync().catch(() => undefined);
            }
        };
    }, [clearTimers]);

    return {
        hasPermission,
        isRecording,
        metering,
        error,
        requestPermission,
        start,
        stop,
        toggle,
    };
}
