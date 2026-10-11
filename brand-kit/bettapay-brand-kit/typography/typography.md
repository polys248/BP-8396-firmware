# BettaPay Typography

## Typeface

BettaPay sets everything in the **native system UI stack** — no webfont:

```css
font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
```

Why: instant load on the low-bandwidth connections many Nigerian SMEs run on,
and payroll tables read like the OS the person already trusts. Don't introduce
a webfont without revisiting page weight on 3G.

Weights in use: **400** regular · **500** medium · **600** semibold · **700** bold.

## Scale (as used in the product)

| Role            | Size  | Weight | Notes                                        |
| --------------- | ----- | ------ | -------------------------------------------- |
| Page title      | 30 px | 700    | e.g. "Employee Management"; tight tracking    |
| Card title      | 24 px | 600    | e.g. "Employee Directory"                     |
| Body            | 16 px | 400    |                                               |
| Small body      | 14 px | 400    | table cells, descriptions, form help          |
| Caption         | 12 px | 400    | muted-foreground; timestamps, counts          |
| Eyebrow label   | 14 px | 400    | UPPERCASE, letter-spacing 0.1em               |

Headings are bold with tight tracking; never all-caps except eyebrow labels.

## Currency

- All naira amounts render through `formatNaira` (`src/lib/tax/format.ts`): `₦1,250,000.00`.
- Use `font-variant-numeric: tabular-nums` in payroll tables so columns align.
- Deliberate exception: jsPDF payslips print the `NGN ` prefix because PDF base
  fonts lack the ₦ glyph (`src/lib/pdf/*`).

## Dates

- Display in West Africa Time via `formatDate` / `formatMonthYear`
  (`src/lib/datetime/wat.ts`).
- Format: `12 Jan 2024` — day, short month, year, no ordinal suffixes.
