import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { Message } from "../types/doctor.types";

interface TranscriptOverlayProps {
    messages: Message[];
    currentDoctorText: string;
}

export function TranscriptOverlay({ messages, currentDoctorText }: TranscriptOverlayProps) {
    const recentMessages = messages.slice(-6);

    return (
        <View style={styles.card}>
            <Text style={styles.title}>Live transcript</Text>
            <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
                {recentMessages.map((message) => (
                    <View key={message.id} style={styles.message}>
                        <Text style={styles.role}>{message.role === "assistant" ? "Dr. Kash" : "You"}</Text>
                        <Text style={styles.text}>{message.text}</Text>
                    </View>
                ))}
                {currentDoctorText ? (
                    <View style={[styles.message, styles.streaming]}>
                        <Text style={styles.role}>Dr. Kash</Text>
                        <Text style={styles.text}>{currentDoctorText}</Text>
                    </View>
                ) : null}
            </ScrollView>
        </View>
    );
}

const styles = StyleSheet.create({
    card: {
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        borderRadius: 24,
        padding: 16,
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.14)",
        maxHeight: 220,
    },
    title: {
        color: "#f8fafc",
        fontSize: 14,
        fontWeight: "700",
        marginBottom: 10,
    },
    content: {
        gap: 12,
    },
    message: {
        gap: 4,
    },
    streaming: {
        borderTopWidth: 1,
        borderTopColor: "rgba(59, 130, 246, 0.18)",
        paddingTop: 10,
    },
    role: {
        color: "#60a5fa",
        fontSize: 12,
        fontWeight: "700",
        textTransform: "uppercase",
        letterSpacing: 0.8,
    },
    text: {
        color: "#e2e8f0",
        fontSize: 14,
        lineHeight: 20,
    },
});
