import { formatAmount } from './amounts';
import type { Schemas } from './apiTypes';
import type { Language } from './i18n';

// Kept apart from shopping.ts (which talks to the API) so it can be tested without a browser

export type ShoppingLine = Schemas['ShoppingLineOut'];

/** The amount text a line shows and Bring! gets as its description: "1 Bund + 50 g", "500 g + 1 Pack", then the
 * recipes' describing words: "800 g, mehligkochende". */
export function formatSpec(line: ShoppingLine, unitLabel: (unit: string) => string, lang: Language): string {
    const parts = line.amounts.map(({ amount, unit }) =>
        unit === null ? formatAmount(amount, lang) : `${formatAmount(amount, lang)} ${unitLabel(unit)}`,
    );
    const amounts = [...parts, ...line.extras.filter(Boolean)].join(' + ');
    return [amounts, ...line.details].filter(Boolean).join(', ');
}
