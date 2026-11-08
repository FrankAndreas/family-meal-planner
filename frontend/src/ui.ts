// Shared Tailwind classes, so forms and cards look the same everywhere (Aurora theme, see index.css)
export const FIELD =
    'rounded-lg border border-white/10 bg-slate-900/60 p-2 text-slate-100 focus:border-cyan-400 focus:outline-none';
export const INPUT = `${FIELD} w-full`;
export const BUTTON = 'btn-primary';
export const BUTTON_SECONDARY =
    'rounded-lg border border-white/15 px-4 py-2 text-slate-200 hover:bg-white/5 disabled:opacity-50';
export const BUTTON_DANGER =
    'rounded-lg border border-red-400/40 px-4 py-2 text-red-300 hover:bg-red-900/30 disabled:opacity-50';
export const CARD = 'glass-card p-5';
// Every page that is no grid (the week plan and the recipe list use the whole width) has this one width
export const PAGE = 'mx-auto max-w-4xl';
export const ERROR = 'rounded-lg border border-red-400/30 bg-red-900/30 p-3 text-sm text-red-200';

// An icon that is "off" (an empty star, a heart not given): 3.75:1 on the dark background, as an icon needs (3:1); text
// uses slate-400 or brighter (contrast.test.ts)
export const ICON_OFF = 'text-slate-500';
