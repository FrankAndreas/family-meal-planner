import type { Language } from './i18n';

// Amounts as people type them on an iPad with a Swiss keyboard ("0,5", "1/2", "1 1/2", "½") and as they read them
const VULGAR: Record<string, number> = { '½': 0.5, '¼': 0.25, '¾': 0.75, '⅓': 1 / 3, '⅔': 2 / 3 };
const SHOWN: [number, string][] = [
    [0.25, '¼'],
    [0.5, '½'],
    [0.75, '¾'],
];

function parsePart(part: string): number | null {
    if (part in VULGAR) return VULGAR[part];
    const mixed = /^(\d+)([½¼¾⅓⅔])$/.exec(part);
    if (mixed) return Number(mixed[1]) + VULGAR[mixed[2]];
    const fraction = /^(\d+)\/(\d+)$/.exec(part);
    if (fraction) return Number(fraction[2]) === 0 ? null : Number(fraction[1]) / Number(fraction[2]);
    // "1.000" or "1.500" might be a thousand (German) or one and a half: the person has to write it unmistakably
    if (/^\d{1,3}(\.\d{3})+$/.test(part)) return null;
    if (/^\d+([.,]\d+)?$/.test(part)) return Number(part.replace(',', '.'));
    return null;
}

/** null: no amount ("Salz"); 'invalid': not a positive amount, the form shows it and doesn't save. */
export function parseAmount(text: string): number | null | 'invalid' {
    const parts = text.trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return null;
    if (parts.length > 2) return 'invalid';
    // "1 1/2": a whole number followed by a fraction
    if (parts.length === 2 && !(/^\d+$/.test(parts[0]) && (/\//.test(parts[1]) || parts[1] in VULGAR))) return 'invalid';
    let total = 0;
    for (const part of parts) {
        const value = parsePart(part);
        if (value === null) return 'invalid';
        total += value;
    }
    return total > 0 ? total : 'invalid';
}

export function formatAmount(amount: number, lang: Language): string {
    const whole = Math.floor(amount);
    const rest = amount - whole;
    const sign = SHOWN.find(([value]) => Math.abs(rest - value) < 1e-9);
    if (sign) return `${whole || ''}${sign[1]}`;
    // de-DE, not de-CH: Swiss recipes write "0,5 dl", while de-CH formats numbers with a point
    return amount.toLocaleString(lang === 'de' ? 'de-DE' : 'en', { maximumFractionDigits: 2, useGrouping: false });
}
