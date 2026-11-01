import { describe, expect, it } from 'vitest';
import { isPickedSuggestion } from './chips';

describe('isPickedSuggestion', () => {
    const offered = ['Kartoffeln', 'Karotten'];

    it('takes a suggestion picked from the list', () => {
        expect(isPickedSuggestion('insertReplacementText', 'Kartoffeln', offered)).toBe(true);
    });

    it('ignores an autocorrection that is no suggestion (iPhone)', () => {
        expect(isPickedSuggestion('insertReplacementText', 'Karto', offered)).toBe(false);
    });

    it('ignores typing, even when it spells a suggestion', () => {
        expect(isPickedSuggestion('insertText', 'Kartoffeln', offered)).toBe(false);
        expect(isPickedSuggestion(undefined, 'Kartoffeln', offered)).toBe(false);
    });
});
