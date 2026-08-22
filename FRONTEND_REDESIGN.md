# Kash AI — Frontend Redesign Summary

**Date:** 2026-08-22  ·  **Thesis:** *"Ancient intelligence, computed"* — Ayurveda meets frontier AI, deliberately avoiding the generic dark-mode-plus-neon AI cliché.

## What you can look at right now

`kash-ai-prototype.html` (repo root) is a **standalone, self-contained landing page** — open it in any browser to see the full direction: the 3D WebGL "dosha orb" hero, live diagnosis-telemetry panel, Nadi pulse-line motif, capabilities grid, and the botanical ink + turmeric + living-green palette. Nothing to install; it loads fonts and Three.js from CDN.

## The brand

A six-colour botanical system — Ink `#0B1512`, Bone `#F4EEE1`, Turmeric `#E8B24A`, Verdant `#2FC98A`, Clay `#B4633A`, Sage `#8AA894` — paired with Fraunces (display serif), Inter (body), and Space Grotesk (labels/telemetry). Full spec is in `DESIGN_SYSTEM.md`.

## What changed in the live app

The restyle was done at the **design-token level** so it cascades everywhere without touching page markup. Two master files carry the identity: `static/css/kash-ai.css` (dark botanical surface for the public `/new` frontend and landing) and `shared/static/css/variables.css` (a warm-light surface for every portal dashboard). Only token *values* changed — names are untouched, so nothing breaks.

Beyond the tokens, every hardcoded indigo/violet/cyan colour that would have clashed was remapped to the new palette across seven stylesheets, roughly twenty-eight templates, and two JavaScript files. A full sweep confirms zero cold-cliché colours remain anywhere in the frontend. Fraunces and Space Grotesk were wired into all three base templates, and the public landing (`templates/new_landing.html`) was rebuilt from scratch — new botanical copy, a CSS-only animated dosha orb, telemetry panel, Nadi divider, and on-brand sections.

## Why the live landing uses a CSS orb instead of WebGL

The app defines its Content-Security-Policy in three different places, and one of them blocks external CDN scripts. To guarantee the live landing always renders beautifully regardless of which policy wins, its orb is pure CSS (no external dependencies). The full Three.js WebGL orb lives in the standalone prototype, which runs in your browser outside those constraints.

## One thing you may want to tune

Headings across the portals now use Fraunces (via `--font-heading`). It reads premium and editorial; if the small headings inside dense dashboards ever feel too heavy, it's a one-line change in `shared/static/css/variables.css`.

## Not yet verified

The app couldn't be run in this environment (FastAPI isn't installed and package installs are blocked), so verification was static — colour sweeps, CSS brace balance, and Jinja block balance all pass. Running the app locally and clicking through the portals is the recommended final check.
