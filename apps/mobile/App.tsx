import "react-native-gesture-handler";
import React from "react";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import { StatusBar } from "expo-status-bar";

import DoctorLiveScreen from "./src/screens/DoctorLiveScreen";

const Stack = createStackNavigator();

const navTheme = {
    ...DefaultTheme,
    colors: {
        ...DefaultTheme.colors,
        background: "#0a0f1e",
        card: "#0a0f1e",
        text: "#f8fafc",
        border: "#0f172a",
        primary: "#60a5fa"
    }
};

export default function App() {
    return (
        <NavigationContainer theme={navTheme}>
            <StatusBar style="light" />
            <Stack.Navigator
                screenOptions={{
                    headerShown: false,
                    cardStyle: { backgroundColor: "#0a0f1e" }
                }}
            >
                <Stack.Screen name="DoctorLive" component={DoctorLiveScreen} />
            </Stack.Navigator>
        </NavigationContainer>
    );
}
