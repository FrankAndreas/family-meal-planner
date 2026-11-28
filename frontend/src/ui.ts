// Shared Tailwind classes, so forms and cards look the same everywhere (Aurora theme, see index.css)
// slate-500: a field's outline reaches 3:1 on the cards (WCAG for controls; white/10 gave 1.4:1)
export const FIELD =
    'rounded-lg border border-line-strong bg-field p-2 text-ink focus:border-accent focus:outline-none';
export const INPUT = `${FIELD} w-full`;
export const BUTTON = 'btn-primary';
export const BUTTON_SECONDARY =
    'rounded-lg border border-line px-4 py-2 text-ink hover:bg-hover disabled:opacity-50';
export const BUTTON_DANGER =
    'rounded-lg border border-danger/40 px-4 py-2 text-danger hover:bg-danger/30 disabled:opacity-50';
export const CARD = 'glass-card p-5';
// Every page that is no grid (the week plan and the recipe list use the whole width) has this one width
export const PAGE = 'mx-auto max-w-4xl';
export const ERROR = 'rounded-lg border border-danger/30 bg-danger/15 p-3 text-sm text-danger';

// An icon that is "off" (an empty star, a heart not given): 3.75:1 on the dark background, as an icon needs (3:1); text
// uses slate-400 or brighter (a11y.test.ts)
export const ICON_OFF = 'text-muted';
