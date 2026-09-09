# Kash AI - Trust & Safety Principles

This document outlines the core principles and technical systems that ensure Kash AI is used safely and responsibly in a clinical setting.

## Core Principle: Human-in-the-Loop

The fundamental safety guarantee of Kash AI is that **all AI-generated clinical output is reviewed, edited, and approved by a qualified human doctor before it reaches a patient.**

The AI's role is to act as a **clinical assistant**, not a replacement for professional medical judgment. It drafts summaries, suggests possibilities, and structures information to reduce the doctor's administrative burden. The doctor remains the final decision-maker and is in complete control of the information shared with their patients.

### Exceptions

The only exception to this rule is for hard-coded, non-AI-generated emergency information. If a user's input contains keywords indicating a potential medical emergency (e.g., "chest pain," "suicidal thoughts"), the system immediately displays a pre-written, static message advising them to contact emergency services (e.g., "Call 112 in India"). This response is a hard-coded safety reflex, not a dynamic AI generation.

## AI Trust Infrastructure

To support continuous improvement and maintain high standards of accuracy, we have implemented a dedicated AI Trust Infrastructure.

### 1. AI Call Logging

A new logging layer has been added to wrap all calls made through `services/ai_provider.py`. For every AI generation, we create a record in a new `ai_logs` database table.

Each log entry contains:
- `id`: A unique identifier for the AI call.
- `timestamp`: When the call was made.
- `doctor_id`: The doctor who initiated the call.
- `feature`: Which part of the application triggered the call (e.g., `morning_brief`, `ai_analyzer`).
- `input_payload`: The exact prompt and context sent to the AI model.
- `raw_output`: The full, unaltered response received from the AI model.
- `provider`: The AI provider used (e.g., `gemini`).
- `feedback_status`: The current review status (`pending`, `accepted`, `rejected`).
- `feedback_notes`: Any notes left by a human reviewer.

### 2. AI Accuracy Dashboard

A new, internal-only **AI Accuracy Dashboard** has been built at `/v2/admin/accuracy-dashboard`. This page is accessible only to administrators.

It provides a simple interface to:
- **Review Recent AI Outputs:** View a list of the latest AI-generated content from the `ai_logs` table.
- **Score Accuracy:** Manually score each output as "Correct," "Needs Edit," or "Wrong."
- **Provide Feedback:** Add notes explaining why a particular output was scored a certain way.

This human feedback loop is critical. The data collected from this dashboard will be used to fine-tune prompts, evaluate model performance, and identify areas where the AI's clinical reasoning needs improvement. This systematic review process ensures that the AI's utility and safety evolve under expert human supervision.