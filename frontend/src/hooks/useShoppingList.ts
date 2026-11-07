import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { errorCode, errorMessage } from '../api';
import { fetchBring, type BringLogin } from '../bring';
import { fetchWeek } from '../plan';
import { fetchShopping, sendShopping, type ShoppingLine, type ShoppingList } from '../shopping';
import { listDifferences, place, type Placement } from '../shoppingView';

const NOTHING_CHANGED = { keys: new Set<string>(), gone: [] as string[] };

// The shared shopping list's data and what changes it (spec 2026-11-06). `requested`: the week asked for in the
// address; else the plan's current week
export function useShoppingList(requested: string | null) {
    const { t } = useTranslation();
    // undefined: still loading; null: no list open
    const [list, setList] = useState<ShoppingList | null | undefined>(undefined);
    const [weekStart, setWeekStart] = useState<string | null>(null);
    const [bring, setBring] = useState<BringLogin | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    // After a refused send: the lines that changed meanwhile, and the names no longer on the list
    const [changed, setChanged] = useState(NOTHING_CHANGED);
    // Where each line is shown (see shoppingView.place), kept up to date with the list while rendering
    const [placed, setPlaced] = useState<Placement>({ list: null, top: new Map() });
    const placedNow = place(placed, list ?? null);
    if (placedNow !== placed) setPlaced(placedNow);

    useEffect(() => {
        let current = true;
        Promise.all([fetchWeek(requested), fetchShopping(), fetchBring()])
            .then(([week, open, login]) => {
                if (!current) return;
                setWeekStart(week.start);
                setList(open);
                setBring(login);
            })
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, [requested]);

    // A change: its answer is the list as it is now (null: no list any more; nothing: unchanged). True if it worked
    const run = async (action: () => Promise<ShoppingList | null | void>): Promise<boolean> => {
        setError('');
        setMessage('');
        setBusy(true);
        try {
            const result = await action();
            if (result !== undefined) setList(result);
            return true;
        } catch (err) {
            setError(errorMessage(err));
            // A tick shown before the answer: back to what the list really is
            fetchShopping()
                .then(setList)
                .catch(() => {});
            return false;
        } finally {
            setBusy(false);
        }
    };

    // To Bring!, each line as `spec` writes its amount
    const send = async (shopping: ShoppingList, spec: (line: ShoppingLine) => string) => {
        setError('');
        setMessage('');
        setChanged(NOTHING_CHANGED);
        setBusy(true);
        try {
            const specs = Object.fromEntries(shopping.lines.map((line) => [line.key, spec(line)]));
            const { sent, kept } = await sendShopping(shopping.version, specs);
            if (kept) {
                // Changed while it was being sent: it stays, to check and send what's missing
                setList(await fetchShopping());
                setMessage(t('shopping.sentKept', { count: sent }));
            } else {
                setList(null);
                setMessage(t('shopping.sent', { count: sent }));
            }
        } catch (err) {
            setError(errorMessage(err));
            // Changed meanwhile: show the list as it is now, with what changed marked, to check and send again
            if (errorCode(err) === 'shopping_changed') {
                const now = await fetchShopping().catch(() => shopping);
                setList(now);
                if (now) setChanged(listDifferences(shopping, now, spec));
            }
        } finally {
            setBusy(false);
        }
    };

    return { list, setList, weekStart, bring, busy, error, message, changed, placed: placedNow, run, send };
}
