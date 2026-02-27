# HTML emails
Restrictions for HTML emails:

**CSS/Styling:**
- All styles must be inline (`style="..."`) — no `<style>` tags, no external stylesheets
- No CSS variables, no `calc()`, no flexbox/grid (limited support), no CSS animations
- Use `px` not `rem`/`em` for fonts and spacing
- `float` works but be careful
- No `position: absolute/fixed`

**Layout:**
- Use `<table>` for layout, not `<div>` — this is the only reliable cross-client approach
- `<table cellpadding="0" cellspacing="0" border="0">` on every table
- Use `width` attribute on `<td>` not just CSS

**Images:**
- Must be absolute URLs (no relative paths)
- Always set `width` and `height` attributes
- Add `alt` text — many clients block images by default
- No SVG, no `<canvas>`

**General HTML:**
- No `<script>` — stripped by every client
- No forms, no iframes
- No `<link>` tags
- Use HTML4 doctype: `<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" ...>`
- Add `xmlns` to `<html>` tag for Outlook
- Always include `<meta charset="UTF-8">`

**Outlook specifically:**
- Needs `mso-` conditional comments for certain fixes
- Ignores many modern CSS properties
- Use `font-family` with web-safe fallbacks only

**Dark mode:**
- Some clients invert colors, so add `color-scheme: light` meta tag and explicit background colors everywhere

# Text Fallback Emails
Just write it as text. Very simple.