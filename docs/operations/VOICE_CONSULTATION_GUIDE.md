# Voice Consultation Guide

## What It Does
The voice consultation system lets a doctor speak naturally during a patient visit while Kash AI listens, transcribes, and extracts the structured details needed for a case sheet. It is designed to reduce manual typing and keep the clinician focused on the patient.

## API Keys
Set these in `.env`:
- `GROQ_API_KEY`
- `SARVAM_API_KEY`
- `OPENAI_API_KEY`

## How To Test
1. Open the Voice Consultation page.
2. Click `Start Voice Consultation`.
3. Speak the demo flow:
   - "Patient is Priya Sharma, 35 years old, female."
   - "I have had a fever for the past 5 days."
   - "Yes, I have a cough and my throat hurts."
   - "My stomach feels heavy."
   - "This looks like a Vata-Kapha imbalance."
   - "Prescribe Chitrakadi Vati and Dashmool Kadha."
   - "Follow up in 7 days."
4. Confirm the live transcript updates and the extracted JSON fills in.
5. Click `Stop Consultation` to end the session.

## UI Layout
The page is split into:
- Recording controls
- Live transcription panel
- Auto-fill panel

## Screenshot Placeholders
- `[Voice consultation header](templates/consultation/voice_consultation.html)`
- `[Device check page](templates/device_check.html)`
- `[Feature status page](templates/feature_status.html)`

## Troubleshooting
- If the microphone does not start, allow browser mic permissions and reload the page.
- If speech recognition is unavailable, use Chrome on desktop or a compatible Android browser.
- If voice parsing looks wrong, check the transcript for names, age, and symptom keywords first.
- If the session will not start, verify the doctor id is present in the consultation URL.
