# Frontend Redesign Guide

## Overview
- Design direction: warm Indian health tech with Ayurvedic greens, saffron accents, cream backgrounds, and soft glass surfaces.
- Shared shell: `templates/base.html`
- Main stylesheet: `static/css/style.css`
- Minified stylesheet: `static/css/style.min.css`

## Design Tokens
- Primary: `#2D6A4F`, `#40916C`, `#52B788`
- Accent: `#FFB703`, `#F4A261`
- Background: `#FFFBF5`, `#FFFDF7`
- Text: `#2D3436`, `#495057`, `#6C757D`

## Typography
- Headings: `Poppins`
- Body: `Inter`
- Accents: `Plus Jakarta Sans`

## Base Template Usage
```jinja2
{% extends 'base.html' %}
{% set active_page = 'home' %}

{% block title %}Page Title{% endblock %}

{% block page %}
<div class="site-container">...</div>
{% endblock %}
```

## Common Components
- Cards: `.table-panel`, `.form-panel`, `.feature-card`, `.metric-card`
- Layouts: `.hero-grid`, `.dashboard-grid`, `.store-layout`, `.stats-grid`
- Buttons: `.btn`, `.btn-primary`, `.btn-outline-success`, `.btn-outline-dark`
- Forms: `.form-row`, `.form-label`, `.form-control`, `.form-select`, `.error-message`
- Feedback: `.alert`, `.badge`, `.toast-notification`, `.skeleton`

## JavaScript Hooks
- Mobile menu: `.mobile-menu-btn`, `.mobile-drawer`, `.close-drawer`
- Avatar dropdown: `[data-profile-toggle]`, `[data-profile-menu]`
- Toast system: `window.showToast(message, type)`
- Loading forms: `data-loading-form`

## Extending Pages
- Keep backend routes, `id` values, and `data-*` hooks unchanged where JS depends on them.
- Prefer shared grid utilities over page-specific layout CSS.
- Add mobile bottom nav only for workflow-heavy pages.

## Accessibility
- Use the skip link in `base.html`
- Maintain heading order from `h1` downward
- Add `aria-label` on custom controls
- Preserve keyboard and Escape behavior for menus/modals

## Browser Support
- Modern Chromium browsers
- Firefox current stable
- Safari 16+

## Common Modifications
- Add a new page: extend `base.html`, set `active_page`, compose sections from panel/grid classes.
- Add validation: wrap input in `.form-row` and add `.error-message` after the field.
- Add toast feedback: call `window.showToast('Message', 'success')`.
