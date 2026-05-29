import { useCallback, useRef, useState } from "react";
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";
import * as Speech from "expo-speech";

const ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM";

function getEnv(name: string): string {
    const processValue = typeof process !== "undefined" ? process.env?.[name] : undefined;
    return String(processValue || "").trim();
}

function stripMarkdown(text: string): string {
    return text.replace(/```json[\s\S]*?```/gi, "").replace(/\s+/g, " ").trim();
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
        const slice = bytes.subarray(index, index + chunkSize);
        binary += String.fromCharCode(...slice);
    }
    if (typeof globalThis.btoa === "function") {
        return globalThis.btoa(binary);
    }
    return "";
}

export function useTTS() {
    const [isSpeaking, setIsSpeaking] = useState(false);
    const soundRef = useRef<Audio.Sound | null>(null);
    const elevenLabsApiKey = getEnv("ELEVENLABS_API_KEY") || getEnv("EXPO_PUBLIC_ELEVENLABS_API_KEY");

    const cleanupSound = useCallback(async () => {
        if (soundRef.current) {
            try {
                await soundRef.current.unloadAsync();
            } catch {
                return;
            } finally {
                soundRef.current = null;
            }
        }
    }, []);

    const speakWithExpo = useCallback((text: string) => {
        const cleaned = stripMarkdown(text);
        if (!cleaned) {
            return;
        }
        Speech.stop();
        setIsSpeaking(true);
        Speech.speak(cleaned, {
            rate: 0.97,
            pitch: 1,
            language: "en-US",
            onDone: () => setIsSpeaking(false),
            onError: () => setIsSpeaking(false),
            onStopped: () => setIsSpeaking(false),
        });
    }, []);

    const speak = useCallback(
        async (text: string) => {
            const cleaned = stripMarkdown(text);
            if (!cleaned) {
                return;
            }
            if (!elevenLabsApiKey) {
                speakWithExpo(cleaned);
                return;
            }

            try {
                const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${ELEVENLABS_VOICE_ID}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "xi-api-key": elevenLabsApiKey,
                    },
                    body: JSON.stringify({
                        text: cleaned,
                        model_id: "eleven_turbo_v2_5",
                        voice_settings: {
                            similarity_boost: 0.7,
                            stability: 0.55,
                        },
                    }),
                });

                if (!response.ok) {
                    throw new Error("elevenlabs_failed");
                }

                const audioBuffer = await response.arrayBuffer();
                const base64 = arrayBufferToBase64(audioBuffer);
                if (!base64 || !FileSystem.cacheDirectory) {
                    throw new Error("audio_serialization_failed");
                }

                const fileUri = `${FileSystem.cacheDirectory}doctor-live-${Date.now()}.mp3`;
                await FileSystem.writeAsStringAsync(fileUri, base64, {
                    encoding: FileSystem.EncodingType.Base64,
                });

                await cleanupSound();
                const { sound } = await Audio.Sound.createAsync(
                    { uri: fileUri },
                    { shouldPlay: true },
                    (status) => {
                        if (!status.isLoaded) {
                            return;
                        }
                        setIsSpeaking(status.isPlaying);
                    }
                );
                soundRef.current = sound;
                setIsSpeaking(true);
            } catch {
                speakWithExpo(cleaned);
            }
        },
        [cleanupSound, elevenLabsApiKey, speakWithExpo]
    );

    const stop = useCallback(async () => {
        Speech.stop();
        setIsSpeaking(false);
        await cleanupSound();
    }, [cleanupSound]);

    return {
        isSpeaking,
        speak,
        stop,
    };
}
