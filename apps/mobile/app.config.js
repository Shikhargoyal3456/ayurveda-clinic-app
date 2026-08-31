import "dotenv/config";

export default {
    expo: {
        name: "Kash AI Live Doctor",
        slug: "kash-ai-live-doctor",
        scheme: "kashailivedoctor",
        version: "1.0.0",
        orientation: "portrait",
        userInterfaceStyle: "dark",
        assetBundlePatterns: ["**/*"],
        ios: {
            supportsTablet: true,
            bundleIdentifier: "com.kashai.livedoctor",
            infoPlist: {
                NSCameraUsageDescription: "Kash AI uses the camera so patients can show symptoms during a live doctor consultation.",
                NSMicrophoneUsageDescription: "Kash AI uses the microphone so patients can speak to the live AI doctor."
            }
        },
        android: {
            package: "com.kashai.livedoctor",
            permissions: ["CAMERA", "RECORD_AUDIO", "INTERNET", "MODIFY_AUDIO_SETTINGS"]
        },
        plugins: [
            [
                "expo-camera",
                {
                    cameraPermission: "Allow Kash AI to access your camera for live doctor consultations."
                }
            ],
            [
                "expo-av",
                {
                    microphonePermission: "Allow Kash AI to access your microphone for live doctor consultations."
                }
            ]
        ],
        extra: {
            aiDoctorWsUrl: process.env.EXPO_PUBLIC_AI_DOCTOR_WS_URL || "ws://35.244.0.89:8000/ws/ai-doctor",
            anthropicApiKey: process.env.ANTHROPIC_API_KEY || "",
            elevenLabsApiKey: process.env.ELEVENLABS_API_KEY || "",
            openAiApiKey: process.env.OPENAI_API_KEY || ""
        }
    }
};
