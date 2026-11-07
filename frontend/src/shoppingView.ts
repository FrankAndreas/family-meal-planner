import type { ShoppingLine, ShoppingList } from './shopping';

// Where a line goes is decided when it first shows: to buy at the top, the rest (what's usually at home, or dropped
// before) at the end. Ticking it on or off later leaves it in its place, so nothing jumps away under the finger (UX
// review). A new list (sent, thrown away, another week) starts afresh.
export interface Placement {
    // The list's week; null: no list
    list: string | null;
    // Line key → placed at the top
    top: Map<string, boolean>;
}

// The placement with the list's new lines added; the same object if nothing changed
export function place(placed: Placement, list: ShoppingList | null): Placement {
    const key = list ? list.week_start : null;
    const start = placed.list === key ? placed : { list: key, top: new Map<string, boolean>() };
    const unplaced = list ? list.lines.filter((line) => !start.top.has(line.key)) : [];
    if (unplaced.length === 0) return start;
    return { list: key, top: new Map([...start.top, ...unplaced.map((line) => [line.key, line.buy] as const)]) };
}

// After a refused send: the lines that changed meanwhile (choice or amount, as `spec` writes it), and the names no
// longer on the list
export function listDifferences(
    before: ShoppingList,
    now: ShoppingList,
    spec: (line: ShoppingLine) => string,
): { keys: Set<string>; gone: string[] } {
    const was = new Map(before.lines.map((line) => [line.key, `${line.buy} ${spec(line)}`]));
    const keys = new Set(now.lines.filter((line) => was.get(line.key) !== `${line.buy} ${spec(line)}`).map((l) => l.key));
    const still = new Set(now.lines.map((line) => line.key));
    return { keys, gone: before.lines.filter((line) => !still.has(line.key)).map((line) => line.name) };
}
