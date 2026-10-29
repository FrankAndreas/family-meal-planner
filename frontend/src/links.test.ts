import { describe, expect, it } from 'vitest';
import { isOtherLink, isWebLink, siteName } from './links';

describe('siteName', () => {
    it('is the host without www', () => {
        expect(siteName('https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/LM201401_57/')).toBe('swissmilk.ch');
        expect(siteName('https://fooby.ch/de/rezepte/12345/risotto')).toBe('fooby.ch');
    });

    it('is the text itself for something that is no address', () => {
        expect(siteName('Omas Kochbuch')).toBe('Omas Kochbuch');
    });
});

describe('isWebLink', () => {
    it('takes http and https only', () => {
        expect(isWebLink(' https://fooby.ch/x ')).toBe(true);
        expect(isWebLink('javascript:alert(1)')).toBe(false);
        expect(isWebLink('Omas Kochbuch')).toBe(false);
    });
});

describe('isOtherLink', () => {
    it('is an address that is no web link', () => {
        expect(isOtherLink('javascript:alert(1)')).toBe(true);
        expect(isOtherLink(' file:///etc/passwd')).toBe(true);
        expect(isOtherLink('https://fooby.ch/x')).toBe(false);
        expect(isOtherLink('Betty Bossi Kochbuch, S. 42')).toBe(false);
        expect(isOtherLink('Oma: Notizbuch')).toBe(false);
    });
});
