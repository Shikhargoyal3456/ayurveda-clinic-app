# User Manual

## Login and Signup
1. Open the application homepage.
2. Sign up the first clinic administrator if public signup is enabled.
3. Log in with your clinic credentials.

## Dashboard
- Register new patients
- Review today’s appointments
- Track follow-ups due
- Launch the demo workspace for training

## AI Symptom Analyzer
1. Open `AI Symptom Analyzer`
2. Enter symptoms
3. Review the structured Ayurvedic draft
4. If Ollama is unavailable, the system shows a fallback warning and still provides grounded guidance

## Appointments and Follow-Ups
- Schedule appointments from the patient registry
- Review due and overdue follow-ups from the tracker

## Admin Dashboard
- Open `/admin`
- Review system health, active sessions, database size, and analytics totals

## FAQ
- Q: Why does the AI show a fallback warning?
  A: Ollama may be offline or disabled. The system switches to a safe rule-based mode.
- Q: How do I back up the clinic data?
  A: Run `scripts\backup_db.py` or schedule it with `scripts\schedule_backup.ps1`
- Q: How do I log out from all devices?
  A: Use the logout-all-devices action once it is exposed in your UI flow or call the route with a valid CSRF token.
