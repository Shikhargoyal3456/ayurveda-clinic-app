import React from "react";
import { StyleSheet, Text, View } from "react-native";
import Animated, { useAnimatedStyle, withTiming } from "react-native-reanimated";

import { DiagnosisItem } from "../types/doctor.types";

interface DiagnosisPanelProps {
    diagnoses: DiagnosisItem[];
}

function ConfidenceRow({ item }: { item: DiagnosisItem }) {
    const animatedStyle = useAnimatedStyle(() => ({
        width: withTiming(`${Math.max(4, Math.min(100, item.confidence))}%`, { duration: 350 }),
    }));

    return (
        <View style={styles.row}>
            <View style={styles.rowHeader}>
                <Text style={styles.name}>{item.name}</Text>
                <Text style={styles.value}>{item.confidence}%</Text>
            </View>
            <View style={styles.track}>
                <Animated.View style={[styles.fill, { backgroundColor: item.color }, animatedStyle]} />
            </View>
        </View>
    );
}

export function DiagnosisPanel({ diagnoses }: DiagnosisPanelProps) {
    return (
        <View style={styles.card}>
            <Text style={styles.title}>Live diagnostic possibilities</Text>
            <Text style={styles.caption}>These update as Dr. Kash gathers more information.</Text>
            {diagnoses.length ? (
                diagnoses.map((item) => <ConfidenceRow key={item.name} item={item} />)
            ) : (
                <Text style={styles.empty}>The diagnosis panel will update after enough history is gathered.</Text>
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    card: {
        backgroundColor: "#10182c",
        borderRadius: 24,
        padding: 18,
        borderWidth: 1,
        borderColor: "rgba(148, 163, 184, 0.18)",
        gap: 12,
    },
    title: {
        color: "#f8fafc",
        fontSize: 16,
        fontWeight: "700",
    },
    caption: {
        color: "#94a3b8",
        fontSize: 13,
        lineHeight: 18,
    },
    empty: {
        color: "#cbd5e1",
        fontSize: 13,
        lineHeight: 18,
    },
    row: {
        gap: 8,
    },
    rowHeader: {
        flexDirection: "row",
        justifyContent: "space-between",
        gap: 12,
    },
    name: {
        flex: 1,
        color: "#e2e8f0",
        fontSize: 14,
        fontWeight: "600",
    },
    value: {
        color: "#cbd5e1",
        fontSize: 13,
        fontWeight: "700",
    },
    track: {
        height: 10,
        borderRadius: 999,
        overflow: "hidden",
        backgroundColor: "#1e293b",
    },
    fill: {
        height: "100%",
        borderRadius: 999,
    },
});
