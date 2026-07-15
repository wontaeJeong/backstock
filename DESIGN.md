# Stock Strategy Lab Design System

## 0. Research Log

- Embedded refs: shortlisted Linear, Revolut, and Kraken; picked `taste-skill` + Linear because research workflows need precise hierarchy, restrained accent use, and dense data without trading-floor urgency.
- Lazyweb: 3 queries, 3 screens viewed (Monarch holdings, Empower portfolio analysis, Atlan data quality); adopted persistent side navigation, a single dominant analysis canvas, compact comparison summaries, visible legends, and quality state next to the data it qualifies.
- UI/UX database: queried an investment research and backtesting dashboard; adopted Fira Sans/Fira Code, tabular figures, status text paired with color, and 44px interaction targets. Rejected its decorative glow and mismatched light palette.
- Imagen drafts: skipped because no image-generation tool is available in this environment. Product screens use real application components rather than decorative mock screenshots.

## 1. Atmosphere & Identity

A quiet research command center: exact, calm, and audit-friendly. The signature is a thin cyan data horizon running through deep graphite surfaces; important information is revealed through luminance and alignment, while color is reserved for action, data series, and explicit status.

Primary persona: an individual strategy researcher comparing assumptions and reproducing runs. Secondary persona: an engineer auditing data lineage and order safety. Both need dense information, keyboard access, plain language, and no decorative urgency.

## 2. Color

| Role | Token | Value | Usage |
|---|---|---|---|
| Canvas | `--surface-canvas` | `#080b0f` | Page background |
| Panel | `--surface-panel` | `#10151c` | Sidebar and cards |
| Elevated | `--surface-elevated` | `#171e27` | Inputs, active rows, popovers |
| Recessed | `--surface-recessed` | `#0b1016` | Charts and code regions |
| Text primary | `--text-primary` | `#f3f7fa` | Headings and primary values |
| Text secondary | `--text-secondary` | `#b7c1cc` | Body and labels |
| Text muted | `--text-muted` | `#778391` | Metadata and disabled copy |
| Border subtle | `--border-subtle` | `#222b36` | Quiet structure |
| Border strong | `--border-strong` | `#34404d` | Inputs and active regions |
| Accent | `--accent-primary` | `#47c7d9` | Primary action and data horizon |
| Accent hover | `--accent-hover` | `#78d9e6` | Hover and focus emphasis |
| Accent ink | `--accent-ink` | `#051114` | Text on accent |
| Success | `--status-success` | `#4cc38a` | Valid, completed |
| Warning | `--status-warning` | `#e3b341` | Data caveat, pending approval |
| Error | `--status-error` | `#ef6a6a` | Invalid, failed, rejected |
| Info | `--status-info` | `#7aa2f7` | Neutral information |
| Focus | `--focus-ring` | `#9ce7f0` | Keyboard focus ring |

Rules:

- Accent is interactive or analytical, never decorative.
- Status color is always paired with a word or icon.
- Body text targets WCAG 2.2 AA; charts keep at least 3:1 line contrast and include a table or text summary.

## 3. Typography

Primary font is Fira Sans Variable. Numbers, identifiers, timestamps, code, and table values use Fira Code Variable with tabular figures.

| Level | Token | Size | Weight | Line height | Usage |
|---|---|---:|---:|---:|---|
| Display | `--type-display` | `2.5rem` | 600 | 1.05 | Major result |
| H1 | `--type-h1` | `2rem` | 600 | 1.15 | Page title |
| H2 | `--type-h2` | `1.5rem` | 600 | 1.25 | Section title |
| H3 | `--type-h3` | `1.125rem` | 600 | 1.35 | Panel title |
| Body | `--type-body` | `1rem` | 400 | 1.55 | Default copy |
| Small | `--type-small` | `0.875rem` | 400 | 1.5 | Secondary copy |
| Caption | `--type-caption` | `0.75rem` | 500 | 1.4 | Metadata |

Headings use negative tracking only at H1 and Display. Body copy stays within 68 characters per line.

## 4. Spacing & Layout

The base unit is 4px. Intent tokens are `--space-1` 4px, `--space-2` 8px, `--space-3` 12px, `--space-4` 16px, `--space-5` 20px, `--space-6` 24px, `--space-8` 32px, `--space-10` 40px, and `--space-12` 48px.

Layout tokens are `--sidebar-width` 272px, `--content-max` 1440px, `--showcase-max` 1152px, and `--target-min` 44px. Radius tokens are `--radius-control` 6px, `--radius-panel` 10px, and `--radius-pill` 999px. Motion tokens are `--motion-feedback` 120ms ease-out, `--motion-standard` 200ms ease-in-out, and `--motion-loading` 800ms linear infinite for explicit loading indicators.

- App shell: fixed sidebar above 1024px, fixed top bar on smaller screens, one main scroll owner bounded by `100dvb`.
- Content width: 1440px maximum with 24px desktop and 16px mobile gutters.
- Data grids use `repeat(auto-fit, minmax(min(16rem, 100%), 1fr))`.
- At 375px every primary flow is a single readable column with no horizontal page scroll.
- Dense tables may scroll horizontally inside a labeled region; the page itself must not.

## 5. Components

### Action Button

- Structure: native `button` or link, label, optional Phosphor icon.
- Variants: primary, secondary, quiet, destructive.
- Spacing: `--space-3` inline with a 44px minimum target.
- States: default, hover, active, focus-visible, disabled, loading.
- Accessibility: native semantics, visible label, `aria-busy` during loading.
- Motion: 120ms opacity and transform feedback; disabled under reduced motion.

### Status Badge

- Structure: status dot plus explicit text.
- Variants: success, warning, error, info, neutral.
- States: static; never interactive.
- Accessibility: meaning is present in text, not color alone.

### Research Panel

- Structure: semantic section with header, optional action cluster, and body.
- Variants: standard, recessed, highlighted.
- States: default, loading skeleton, empty guidance, error with recovery action.
- Layout: stack primitive; no independent scroll unless named for a table or log.

### Form Field

- Structure: label, control, helper, inline error.
- States: default, focus, disabled, read-only, invalid, loading.
- Accessibility: labels never rely on placeholders; invalid state uses `aria-describedby`.

### App Shell

- Structure: navigation, top context bar, main region.
- Layout: fixed-sidenav-shell; main is the only vertical scroll owner.
- Responsive: sidebar becomes a compact horizontal nav below 1024px.
- Accessibility: skip link, landmarks, current route state, minimum 44px targets.

## 6. Motion & Interaction

- Micro feedback: 120ms ease-out for button press and hover.
- Standard transitions: 200ms ease-in-out for disclosure and tab state.
- Only `transform`, `opacity`, and color are animated; no layout-property animation.
- Motion communicates action or state change. No perpetual decorative animation.
- `prefers-reduced-motion: reduce` removes transform and transition effects.

## 7. Depth & Surface

Strategy: mixed tonal shift and subtle borders. Canvas, panel, elevated, and recessed luminance establish most hierarchy. One-pixel token borders clarify interactive or bounded regions. Shadows are reserved for modal overlays; routine panels never float.

Corners follow one system: 6px controls, 10px panels, full pill only for status/filter chips.

## 8. Accessibility Constraints & Accepted Debt

### Constraints

- WCAG 2.2 AA minimum, with 4.5:1 body contrast and 3:1 large text/data marks.
- Full keyboard reachability, persistent focus-visible rings, skip link, and semantic landmarks.
- 44px minimum interactive target, no hover-only information, no color-only status.
- Reduced motion is honored; 200% text zoom must not hide actions or create page-level horizontal scroll.
- Charts require visible legends, exact-value interaction, and an accessible summary or table.

### Accepted Debt

None. New debt must name affected users, location, owner, and an exit condition before acceptance.
