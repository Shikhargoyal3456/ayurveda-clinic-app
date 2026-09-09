import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";

interface FloatingControlsProps {
    cameraEnabled: boolean;
    onToggleCamera: () => void;
    onShareScreen: () => void;
}

function ActionButton({
    icon,
    onPress,
}: {
    icon: React.ComponentProps<typeof MaterialCommunityIcons>["name"];
    onPress: () => void;
}) {
    return (
        <Pressable style={styles.button} onPress={onPress}>
            <MaterialCommunityIcons color="#f8fafc" name={icon} size={22} />
        </Pressable>
    );
}

export function FloatingControls({
    cameraEnabled,
    onToggleCamera,
    onShareScreen,
}: FloatingControlsProps) {
    return (
        <View style={styles.container}>
            <ActionButton icon={cameraEnabled ? "camera-off-outline" : "camera-outline"} onPress={onToggleCamera} />
            <ActionButton icon="monitor-share" onPress={onShareScreen} />
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        position: "absolute",
        right: 20,
        top: 132,
        gap: 12,
    },
    button: {
        width: 52,
        height: 52,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 26,
        backgroundColor: "rgba(15, 23, 42, 0.72)",
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.18)",
    },
});
