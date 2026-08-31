import React, { useEffect } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
    Easing,
    interpolate,
    useAnimatedStyle,
    useSharedValue,
    withRepeat,
    withTiming,
} from "react-native-reanimated";

interface WaveformProps {
    metering: number;
    mode: "idle" | "listening" | "speaking";
}

function WaveBar({
    index,
    metering,
    mode,
}: {
    index: number;
    metering: number;
    mode: WaveformProps["mode"];
}) {
    const level = useSharedValue(0.12);

    useEffect(() => {
        if (mode === "idle") {
            level.value = withRepeat(
                withTiming(0.18 + (index % 4) * 0.03, {
                    duration: 1200,
                    easing: Easing.inOut(Easing.ease),
                }),
                -1,
                true
            );
            return;
        }

        const spread = 0.55 + ((index % 7) / 12);
        level.value = withTiming(Math.max(0.12, metering * spread), {
            duration: 140,
            easing: Easing.out(Easing.ease),
        });
    }, [index, level, metering, mode]);

    const animatedStyle = useAnimatedStyle(() => ({
        height: interpolate(level.value, [0, 1], [10, 112]),
        backgroundColor: mode === "speaking" ? "#60a5fa" : "#34d399",
        opacity: mode === "idle" ? 0.55 : 0.95,
    }));

    return <Animated.View style={[styles.bar, animatedStyle]} />;
}

export function Waveform({ metering, mode }: WaveformProps) {
    return (
        <View style={styles.container}>
            {Array.from({ length: 25 }).map((_, index) => (
                <WaveBar key={index} index={index} metering={metering} mode={mode} />
            ))}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        minHeight: 124,
    },
    bar: {
        width: 8,
        borderRadius: 999,
    },
});
