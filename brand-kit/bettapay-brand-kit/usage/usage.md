# BettaPay Logo Usage

The mark is a hexagonal S-fold — a payslip folding through a hex badge — drawn
in the brand's deep green gradient (#327B60 → #0F4330) on a pale green tile
(#EDF8F2). The tile, its corner radius (18.75% of its size) and the gradient
are part of the mark.

## Files

| File                              | Use                                           |
| --------------------------------- | --------------------------------------------- |
| `logo/brand-mark.svg`              | Canonical vector mark — use this everywhere    |
| `logo/favicon.png`                 | Raster twin for browser tabs / apple-touch-icon |
| `logo/lockup-light.svg`            | Mark + wordmark for light backgrounds          |
| `logo/lockup-dark.svg`             | Mark + wordmark for dark backgrounds           |

In app code, render through `src/components/brand/BrandLogo.tsx`.
If the mark ever changes, regenerate `brand-mark.svg` AND `favicon.png`
together from the parametric builder kept in the rebrand commit history.

## Lockup

Mark + wordmark "BettaPay" set in the system UI stack at weight 700.
Wordmark color: Primary `#0D3B2A` on light, Foreground `#F0F4F3` on dark,
white on the hero gradient.

## Rules

- **Clearspace:** keep at least ¼ of the tile's height clear on every side.
- **Minimum size:** never below 24 px (favicon); prefer ≥ 32 px in UI chrome.
- **Approved backgrounds:** background `#FAFAFA`, white, dark `#0D1210`,
  brand tint `#EDF8F2`, hero gradient.
- **Shadow:** only the token `shadow-glow`, and only in hero contexts.

## Don't

- Stretch or squash — scale uniformly only.
- Recolor — the green gradient and tile are fixed.
- Rotate or tilt — the fold reads upright.
- Place on busy or clashing fills.
- Add outlines, bevels or non-token glows.
- Restyle the wordmark (no serifs, no italics, no other weights).
- Crop the tile or change its corner radius.
