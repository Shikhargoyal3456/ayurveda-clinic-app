# Kash AI — Design System

**Thesis: "Ancient intelligence, computed."** Kash AI is Ayurveda (doshas, pulse diagnosis, botanicals) meeting frontier AI. The design rejects the generic dark-mode-plus-neon AI-startup cliché in favour of a warm, botanical, premium identity — deep herbal ink, turmeric gold, living green — that still feels precise and computed.

## Palette (6 named values)

| Token | Hex | Role |
|-------|-----|------|
| **Ink** | `#0B1512` | Deep botanical black — dark canvas (landing, marketing) |
| **Bone** | `#F4EEE1` | Warm cream — light canvas (app/portals) & text on ink |
| **Turmeric** | `#E8B24A` | Primary warm accent — CTAs, hero glow, highlights |
| **Verdant** | `#2FC98A` | Living green — secondary/tech accent, success, data |
| **Clay** | `#B4633A` | Deep terracotta — occasional warmth, used sparingly |
| **Sage** | `#8AA894` | Muted botanical gray-green — borders, muted text on ink |

Deeper support shades: `--gold-deep #C6871B`, `--verdant-deep #14855A`, `--ink-raised #13221C`.

The **app/portal** surfaces stay light (safe for data-dense medical dashboards) but share the exact brand hues: deep botanical green primary, turmeric secondary, warm cream backgrounds instead of cold gray-white. Dark landing + warm-light app = one identity, two surfaces (the pattern premium products use).

## Type (3 roles)

- **Display — Fraunces** (variable serif, high optical contrast): big headlines only, used with restraint. Warm, editorial, evokes a botanical manuscript.
- **Body/UI — Inter**: paragraphs, forms, tables, controls.
- **Utility — Space Grotesk**: eyebrows, labels, nav, stat captions — the "instrument panel" voice. A monospace (JetBrains Mono) appears *only* for live telemetry readouts.

## Signature

**The Dosha Orb** — a slowly rotating 3D sphere (WebGL) representing Vata / Pitta / Kapha as flowing gold→verdant→clay energy shells, breathing with a soft pulse. Backed by a glass "diagnosis telemetry" panel.

Recurring motif: a fine **Nadi pulse-line** (Ayurvedic pulse-diagnosis waveform) used as section divider and structural marker — structure that encodes the subject, not decoration.

## Motion

Page-load: orb fades/scales in, headline rises word-by-word, telemetry counts up. Scroll: sections reveal once. Hover: buttons lift with a gold glow; cards tilt subtly. All gated behind `prefers-reduced-motion`.

## How it maps to the live app

- `static/css/kash-ai.css` `:root` → dark identity for the `/new` public frontend + landing.
- `shared/static/css/variables.css` → warm-light identity for all portal dashboards (values only; token names unchanged so nothing breaks).
- Base templates gain the Fraunces + Space Grotesk font links.
