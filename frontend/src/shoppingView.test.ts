import { describe, expect, it } from 'vitest';
import type { ShoppingLine, ShoppingList } from './shopping';
import { listDifferences, place, type Placement } from './shoppingView';

const line = (key: string, buy: boolean, amount = 1): ShoppingLine => ({
    key,
    name: key.toUpperCase(),
    amounts: [{ amount, unit: null }],
    extras: [],
    meals: [],
    staple: false,
    buy,
});
const list = (week: string, lines: ShoppingLine[]) => ({ week_start: week, lines }) as unknown as ShoppingList;
const spec = (l: ShoppingLine) => String(l.amounts[0]?.amount ?? '');

describe('place', () => {
    it('places each line once, where it first showed: to buy at the top, the rest at the end', () => {
        const first = place({ list: null, top: new Map() }, list('2026-11-07', [line('a', true), line('b', false)]));
        expect([...first.top]).toEqual([
            ['a', true],
            ['b', false],
        ]);
        // Ticked off later, it stays where it is; a new line gets its place
        const later = place(first, list('2026-11-07', [line('a', false), line('b', false), line('c', true)]));
        expect([...later.top]).toEqual([
            ['a', true],
            ['b', false],
            ['c', true],
        ]);
    });

    it('nothing new: the same placement, so nothing renders again', () => {
        const placed = place({ list: null, top: new Map() }, list('2026-11-07', [line('a', true)]));
        expect(place(placed, list('2026-11-07', [line('a', false)]))).toBe(placed);
    });

    it('another list starts afresh', () => {
        const placed: Placement = { list: '2026-11-07', top: new Map([['a', false]]) };
        expect([...place(placed, list('2026-11-14', [line('a', true)])).top]).toEqual([['a', true]]);
        expect(place(placed, null)).toEqual({ list: null, top: new Map() });
    });
});

describe('listDifferences', () => {
    it('marks lines whose amount or choice changed, and names the ones gone', () => {
        const before = list('w', [line('a', true, 1), line('b', true, 2), line('c', true, 3)]);
        const now = list('w', [line('a', true, 1), line('b', false, 2), line('c', true, 4), line('d', true)]);
        const { keys, gone } = listDifferences(before, now, spec);
        expect([...keys].sort()).toEqual(['b', 'c', 'd']);
        expect(gone).toEqual([]);
        expect(listDifferences(before, list('w', [line('a', true, 1)]), spec).gone).toEqual(['B', 'C']);
    });
});
