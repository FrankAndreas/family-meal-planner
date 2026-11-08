import { beforeAll, describe, expect, it } from 'vitest';
import { stubBrowser } from './browserStubs.test-helper';

const storage = stubBrowser();
let plan: typeof import('./plan');
beforeAll(async () => {
    plan = await import('./plan');
});

describe('addDays', () => {
    it('crosses months, years and the switch to and from summer time', () => {
        expect(plan.addDays('2026-10-31', 1)).toBe('2026-11-01');
        expect(plan.addDays('2026-12-31', 1)).toBe('2027-01-01');
        expect(plan.addDays('2026-03-01', -1)).toBe('2026-02-28');
        // Summer time ends on 25 October and starts on 29 March 2026 (Switzerland)
        expect(plan.addDays('2026-10-24', 2)).toBe('2026-10-26');
        expect(plan.addDays('2026-03-28', 2)).toBe('2026-03-30');
        expect(plan.addDays('2026-11-07', 7)).toBe('2026-11-14');
    });
});

describe('weekdayKey', () => {
    it('names the day as the backend numbers them (0 = Monday)', () => {
        expect(plan.weekdayKey('2026-11-07')).toBe('sat');
        expect(plan.weekdayKey('2026-11-08')).toBe('sun');
        expect(plan.weekdayKey('2026-11-09')).toBe('mon');
    });
});

describe('the "For" choice on this device', () => {
    it('is kept, and forgotten again', () => {
        plan.saveSuggestionSlot('dinner');
        expect(plan.loadSuggestionSlot()).toBe('dinner');
        plan.saveSuggestionSlot(null);
        expect(plan.loadSuggestionSlot()).toBeNull();
    });

    it('anything else stored there counts as no choice', () => {
        storage.setItem('meals.suggestionSlot', 'brunch');
        expect(plan.loadSuggestionSlot()).toBeNull();
    });

    it('blocked storage just forgets, without an error', () => {
        storage.fail = true;
        try {
            expect(() => plan.saveSuggestionSlot('lunch')).not.toThrow();
            expect(plan.loadSuggestionSlot()).toBeNull();
        } finally {
            storage.fail = false;
        }
    });
});
