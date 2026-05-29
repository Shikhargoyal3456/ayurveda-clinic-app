import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";

interface BottomControlsProps {
    isMicActive: boolean;
    isPaused: boolean;
    onToggleMic: () => void;
    onShare: () => void;
    onPause: () => void;
    onEnd: () => void;
}

function ControlButton({
    icon,
    label,
    onPress,
    tone = "default",
}: {
    icon: React.ComponentProps<typeof MaterialCommunityIcons>["name"];
    label: string;
    onPress: () => void;
    tone?: "default" | "danger";
}) {
    return (
        <Pressable style={[styles.button, tone === "danger" && styles.buttonDanger]} onPress={onPress}>
            <MaterialCommunityIcons
                color={tone === "danger" ? "#fff" : "#e2e8f0"}
                name={icon}
                size={22}
            />
            <Text style={[styles.label, tone === "danger" && styles.labelDanger]}>{label}</Text>
        </Pressable>
    );
}

export function BottomControls({
    isMicActive,
    isPaused,
    onToggleMic,
    onShare,
    onPause,
    onEnd,
}: BottomControlsProps) {
    return (
        <View style={styles.row}>
            <ControlButton
                icon={isMicActive ? "microphone-outline" : "microphone-off"}
                label={isMicActive ? "Mic" : "Unmute"}
                onPress={onToggleMic}
            />
            <ControlButton icon="share-variant-outline" label="Share" onPress={onShare} />
            <ControlButton icon={isPaused ? "play-outline" : "pause"} label={isPaused ? "Resume" : "Pause"} onPress={onPause} />
            <ControlButton icon="close" label="End" onPress={onEnd} tone="danger" />
        </View>
    );
}

const styles = StyleSheet.create({
    row: {
        flexDirection: "row",
        justifyContent: "space-between",
        gap: 10,
    },
    button: {
        flex: 1,
        minHeight: 68,
        borderRadius: 24,
        backgroundColor: "#111b30",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.14)",
    },
    buttonDanger: {
        backgroundColor: "#dc2626",
        borderColor: "#ef4444",
    },
    label: {
        color: "#e2e8f0",
        fontWeight: "700",
        fontSize: 12,
    },
    labelDanger: {
        color: "#fff",
    },
});
