import { formatAmount } from './amounts';
import type { Language } from './i18n';

// Kept apart from shopping.ts (which talks to the API) so it can be tested without a browser

export interface ShoppingLine {
    key: string;
    name: string;
    amounts: { amount: number; unit: string | null }[];
    extras: string[];
    meals: string[];
    staple: boolean;
    buy: boolean;
}

/** The amount text a line shows and Bring! gets as its description: "1 Bund + 50 g", "500 g + 1 Pack". */
export function formatSpec(line: ShoppingLine, unitLabel: (unit: string) => string, lang: Language): string {
    const parts = line.amounts.map(({ amount, unit }) =>
        unit === null ? formatAmount(amount, lang) : `${formatAmount(amount, lang)} ${unitLabel(unit)}`,
    );
    return [...parts, ...line.extras.filter(Boolean)].join(' + ');
}
