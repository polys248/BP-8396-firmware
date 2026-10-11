# BettaPay Brand Kit

Everything is derived from the shipped product (October 2026): the mark from
`public/brand-mark.svg`, colors from the HSL tokens in `src/index.css`, type
and component conventions from the app itself.

## Contents

```
brand-board.html          The full brand board — open in any browser, works offline
logo/
  brand-mark.svg          Canonical vector mark (use this everywhere)
  favicon.png             Raster twin for browser tabs / apple-touch-icon
  lockup-light.svg        Mark + wordmark for light backgrounds
  lockup-dark.svg         Mark + wordmark for dark backgrounds
colors/
  tokens.css              All color tokens as CSS custom properties (light + dark)
  colors.json             Same palette as structured data (HSL + hex)
typography/
  typography.md           Type stack, scale, currency & date conventions
usage/
  usage.md                Logo rules: clearspace, minimum size, do / don't
```

## Quick facts

- **Primary green:** `hsl(158 64% 14%)` / `#0D3B2A` (flips to `#66CCA7` in dark mode)
- **Logo tile:** `#EDF8F2`, gradient `#327B60 → #0F4330`; the tile and its
  18.75% corner radius are part of the mark
- **Type:** native system UI stack, no webfont — weights 400/500/600/700
- **Radius:** 0.5rem base · **Shadows:** green-tinted, never gray
- **Clearspace:** ¼ of tile height on all sides · **Minimum:** 24 px

The HSL custom properties in the codebase remain the source of truth; if
`src/index.css` changes, regenerate this kit. The live, editable version of
the board is the "BettaPay Brand Board" canvas in Claude artifacts.
