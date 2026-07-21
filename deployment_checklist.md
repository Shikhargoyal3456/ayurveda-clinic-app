# Deployment Checklist

1. Set the new environment variables in `.env`: `OPENAI_API_KEY`, `GROQ_API_KEY`, `SARVAM_API_KEY`, `JITSI_DOMAIN`, and feature flags like `ENABLE_VISION=True`.
2. Restart the FastAPI app and confirm the SQLite tables `tongue_analyses`, `billing_codes`, and `telemedicine_sessions` exist.
3. Open a consultation page, capture or upload a tongue image, and verify the analysis appears and is saved.
4. Run the voice-to-action flow, confirm the draft case sheet, medicines, prescription, and follow-up date render on screen.
5. Open the dashboard and verify the churn widget loads at-risk patients with reminder links.
6. Generate billing codes from a prescription and confirm the ICD-11 / AYUSH JSON is stored.
7. Open a patient record, start a video consultation, and confirm the session URL opens.
8. Check the `static/uploads/tongue/` folder for uploaded images and confirm the case sheet/prescription records are present in SQLite.
9. If any endpoint returns `503`, verify the corresponding `ENABLE_*` flag is set to `True`.
