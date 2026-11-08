import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AutoSaver, type AutoSaveOptions, type SaveStatus } from './autoSave';

interface Settings {
    size: number;
    day: number;
    staples: string[];
}

// A save the test answers when it wants: each call waits in `calls` until resolved or rejected
function backend() {
    const calls: { fields: Partial<Settings>; resolve: (s: Settings) => void; reject: (e: unknown) => void }[] = [];
    const save = (fields: Partial<Settings>) =>
        new Promise<Settings>((resolve, reject) => calls.push({ fields, resolve, reject }));
    return { calls, save };
}

function saver(options: Partial<AutoSaveOptions<Settings>> = {}) {
    const server = backend();
    const statuses: SaveStatus[] = [];
    const errors: unknown[] = [];
    const engine = new AutoSaver<Settings>(
        () => ({ save: server.save, ...options }),
        { status: (s) => statuses.push(s), error: (e) => errors.push(e) },
    );
    return { engine, server, statuses, errors };
}

const SAVED: Settings = { size: 4, day: 5, staples: ['Salz'] };
// Lets the promise chain run (the queue, the awaits in it)
const settled = () => vi.runAllTimersAsync();

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('AutoSaver', () => {
    it('saves a change, and only then says saved', async () => {
        const { engine, server, statuses } = saver();
        engine.change({ day: 2 });
        expect(statuses).toEqual(['saving']);
        await settled();
        expect(server.calls.map((c) => c.fields)).toEqual([{ day: 2 }]);
        server.calls[0].resolve(SAVED);
        await settled();
        expect(statuses).toEqual(['saving', 'saved']);
    });

    it('waits the pause before sending, and a newer change restarts it: "12" is never saved as 1', async () => {
        const { engine, server } = saver();
        engine.change({ size: 1 }, 600);
        await vi.advanceTimersByTimeAsync(400);
        engine.change({ size: 12 }, 600);
        await vi.advanceTimersByTimeAsync(400);
        expect(server.calls).toEqual([]);
        await vi.advanceTimersByTimeAsync(200);
        expect(server.calls.map((c) => c.fields)).toEqual([{ size: 12 }]);
    });

    it('sends one save after the other: an older answer never wins over a newer change', async () => {
        const { engine, server, statuses } = saver();
        engine.change({ day: 1 });
        await settled();
        engine.change({ day: 2 });
        await settled();
        // The second waits for the first
        expect(server.calls).toHaveLength(1);
        server.calls[0].resolve({ ...SAVED, day: 1 });
        await settled();
        expect(server.calls.map((c) => c.fields)).toEqual([{ day: 1 }, { day: 2 }]);
        // Not "saved" while the second is still on its way
        expect(statuses.at(-1)).toBe('saving');
        server.calls[1].resolve({ ...SAVED, day: 2 });
        await settled();
        expect(statuses.at(-1)).toBe('saved');
    });

    it('a failed save is not lost: it goes again with the next change, unless that change replaced it', async () => {
        const { engine, server, statuses, errors } = saver();
        engine.change({ day: 1, size: 3 });
        await settled();
        server.calls[0].reject(new Error('down'));
        await settled();
        expect(statuses.at(-1)).toBe('idle');
        expect(errors.at(-1)).toBeInstanceOf(Error);
        engine.change({ day: 2 });
        await settled();
        expect(server.calls[1].fields).toEqual({ size: 3, day: 2 });
        server.calls[1].resolve(SAVED);
        await settled();
        expect(errors.at(-1)).toBeNull();
        expect(statuses.at(-1)).toBe('saved');
    });

    it('tells whether a field changed again while its save was on the way', async () => {
        const seen: boolean[] = [];
        const { engine, server } = saver({ onSaved: (_saved, _fields, changedSince) => seen.push(changedSince('staples')) });
        engine.change({ staples: ['Salz'] });
        await settled();
        engine.change({ staples: ['Salz', 'Öl'] });
        server.calls[0].resolve(SAVED);
        await settled();
        server.calls[1].resolve(SAVED);
        await settled();
        expect(seen).toEqual([true, false]);
    });

    it('a change that is no change after all is dropped, and nothing is sent', async () => {
        const { engine, server, statuses } = saver();
        engine.change({ size: 2 }, 600);
        engine.drop('size');
        await settled();
        expect(server.calls).toEqual([]);
        expect(statuses).toEqual(['saving', 'idle']);
    });

    it('dropping one field keeps the others', async () => {
        const { engine, server } = saver();
        engine.change({ day: 3 }, 600);
        engine.change({ size: 2 }, 600);
        engine.drop('size');
        await settled();
        expect(server.calls.map((c) => c.fields)).toEqual([{ day: 3 }]);
    });

    it('leaving the page sends what is still waiting, without the pause', async () => {
        const { engine, server } = saver();
        engine.change({ size: 5 }, 600);
        engine.flush();
        await vi.advanceTimersByTimeAsync(0);
        expect(server.calls.map((c) => c.fields)).toEqual([{ size: 5 }]);
        engine.flush();
        await settled();
        expect(server.calls).toHaveLength(1);
    });

    it('closing the tab sends what is waiting as a request that outlives the page, at once', async () => {
        const kept: Partial<Settings>[] = [];
        const { engine, server, statuses } = saver({
            saveOnLeave: (fields) => {
                kept.push(fields);
                return Promise.resolve(SAVED);
            },
        });
        engine.change({ size: 5 }, 600);
        engine.leave();
        // Started right away, inside the page's last moment
        expect(kept).toEqual([{ size: 5 }]);
        await settled();
        expect(server.calls).toEqual([]);
        expect(statuses.at(-1)).toBe('saved');
        engine.leave();
        expect(kept).toHaveLength(1);
    });
});
