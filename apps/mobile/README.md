# Kash AI Live Doctor Mobile App

## Setup

1. Open the Expo app folder:

```bash
cd mobile-app
```

2. Install dependencies:

```bash
npm install
npx expo install expo-av expo-camera expo-file-system expo-haptics expo-linear-gradient expo-speech react-native-gesture-handler react-native-safe-area-context react-native-screens
```

3. Make sure the root `.env` contains:

```env
ANTHROPIC_API_KEY=
ELEVENLABS_API_KEY=
OPENAI_API_KEY=
EXPO_PUBLIC_AI_DOCTOR_WS_URL=ws://35.244.0.89:8000/ws/ai-doctor
```

4. Start the app:

```bash
npm run start
```

## iOS build

```bash
npx expo run:ios
```

Or with EAS:

```bash
npx eas build --platform ios
```

## Android build

```bash
npx expo run:android
```

Or with EAS:

```bash
npx eas build --platform android
```

## Notes

- The screen connects to `ws://35.244.0.89:8000/ws/ai-doctor` by default.
- Audio chunks are sent to the FastAPI WebSocket backend.
- Whisper transcription uses `OPENAI_API_KEY` if provided.
- Doctor voice playback uses Expo Speech.
