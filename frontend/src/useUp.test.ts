import { beforeAll, describe, expect, it } from 'vitest';
import { stubBrowser } from './browserStubs.test-helper';

const storage = stubBrowser();
let useUp: typeof import('./useUp');
beforeAll(async () => {
    useUp = await import('./useUp');
});

const EMPTY = { tab: 'search', have: [], mode: 'use_up' };

describe('what was typed in "Was habe ich?", kept on this device', () => {
    it('comes back as it was', () => {
        useUp.saveUseUp({ tab: 'use_up', have: ['Rüebli', 'Rahm'], mode: 'cook_now' });
        expect(useUp.loadUseUp()).toEqual({ tab: 'use_up', have: ['Rüebli', 'Rahm'], mode: 'cook_now' });
    });

    it('starts empty without anything stored, or with something unreadable', () => {
        storage.removeItem('meals.useUp');
        expect(useUp.loadUseUp()).toEqual(EMPTY);
        storage.setItem('meals.useUp', '{not json');
        expect(useUp.loadUseUp()).toEqual(EMPTY);
    });

    it('takes only what makes sense from an old or tampered value', () => {
        const many = Array.from({ length: 30 }, (_, n) => `Zutat ${n}`);
        storage.setItem('meals.useUp', JSON.stringify({ tab: 'other', have: [...many, 5, null], mode: 'x' }));
        const loaded = useUp.loadUseUp();
        expect(loaded.tab).toBe('search');
        expect(loaded.mode).toBe('use_up');
        expect(loaded.have).toEqual(many.slice(0, useUp.MAX_HAVE));
    });

    it('blocked storage just forgets, without an error', () => {
        storage.fail = true;
        try {
            expect(() => useUp.saveUseUp({ tab: 'use_up', have: ['Reis'], mode: 'use_up' })).not.toThrow();
            expect(useUp.loadUseUp()).toEqual(EMPTY);
        } finally {
            storage.fail = false;
        }
    });
});
