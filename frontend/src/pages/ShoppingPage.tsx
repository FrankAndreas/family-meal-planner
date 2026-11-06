import { format, parseISO } from 'date-fns';
import { de, enUS } from 'date-fns/locale';
import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { errorCode, errorMessage } from '../api';
import { bringReady, fetchBring, type BringLogin } from '../bring';
import type { Language } from '../i18n';
import { fetchWeek } from '../plan';
import {
    addExtra,
    chooseLine,
    discardShopping,
    fetchShopping,
    formatSpec,
    removeExtra,
    sendShopping,
    startShopping,
    tickMeal,
    type ShoppingList,
} from '../shopping';
import { BUTTON, BUTTON_SECONDARY, CARD, ERROR, FIELD } from '../ui';

// The shared shopping list (spec 2026-11-06): pick the week's meals, drop or add items, send them to Bring!
export default function ShoppingPage() {
    const { t, i18n } = useTranslation();
    const lang = (i18n.language === 'en' ? 'en' : 'de') as Language;
    const locale = lang === 'de' ? de : enUS;
    const [search, setSearch] = useSearchParams();
    // undefined: still loading; null: no list open
    const [list, setList] = useState<ShoppingList | null | undefined>(undefined);
    const [weekStart, setWeekStart] = useState<string | null>(null);
    const [bring, setBring] = useState<BringLogin | null>(null);
    const [name, setName] = useState('');
    const [amount, setAmount] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    // After a refused send: the lines that changed meanwhile, and the names no longer on the list
    const [changed, setChanged] = useState<{ keys: Set<string>; gone: string[] }>({ keys: new Set(), gone: [] });
    const requested = search.get('start');

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

    const day = (iso: string) => format(parseISO(iso), 'EEEEEE d.M.', { locale });
    const weekday = (iso: string) => format(parseISO(iso), 'EEEEEE', { locale });
    const range = (start: string, end: string) => `${day(start)} – ${day(end)}`;
    const end = (start: string) => format(new Date(parseISO(start).getTime() + 6 * 86_400_000), 'yyyy-MM-dd');
    const time = (utc: string) => format(new Date(`${utc}Z`), 'HH:mm', { locale });
    const spec = (line: ShoppingList['lines'][number]) => formatSpec(line, (unit) => t(`units.${unit}` as 'units.g'), lang);

    const run = async (action: () => Promise<ShoppingList | null | void>) => {
        setError('');
        setMessage('');
        setChanged({ keys: new Set(), gone: [] });
        setBusy(true);
        try {
            const result = await action();
            if (result !== undefined) setList(result);
        } catch (err) {
            setError(errorMessage(err));
            // A tick shown before the answer: back to what the list really is
            fetchShopping()
                .then(setList)
                .catch(() => {});
        } finally {
            setBusy(false);
        }
    };

    const differences = (before: ShoppingList, now: ShoppingList) => {
        const was = new Map(before.lines.map((line) => [line.key, `${line.buy} ${spec(line)}`]));
        const keys = new Set(now.lines.filter((line) => was.get(line.key) !== `${line.buy} ${spec(line)}`).map((l) => l.key));
        const still = new Set(now.lines.map((line) => line.key));
        return { keys, gone: before.lines.filter((line) => !still.has(line.key)).map((line) => line.name) };
    };

    const send = async (shopping: ShoppingList) => {
        setError('');
        setMessage('');
        setChanged({ keys: new Set(), gone: [] });
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
                if (now) setChanged(differences(shopping, now));
            }
        } finally {
            setBusy(false);
        }
    };

    const add = (e: FormEvent) => {
        e.preventDefault();
        run(async () => {
            const changed = await addExtra(name.trim(), amount.trim());
            setName('');
            setAmount('');
            return changed;
        });
    };

    const feedback = (
        <>
            {message && (
                <p role="status" className="rounded-lg border border-emerald-400/30 bg-emerald-900/30 p-3 text-sm text-emerald-100">
                    {message}
                </p>
            )}
            {error && (
                <p role="alert" className={ERROR}>
                    {error}
                </p>
            )}
        </>
    );

    if (list === undefined || weekStart === null) {
        return <div className="mx-auto max-w-3xl space-y-4">{feedback}</div>;
    }

    if (list === null) {
        return (
            <div className="mx-auto max-w-3xl space-y-4">
                <h1 className="text-xl">{t('shopping.title')}</h1>
                {feedback}
                <div className={CARD}>
                    <button type="button" className={BUTTON} disabled={busy} onClick={() => run(() => startShopping(weekStart))}>
                        {t('shopping.start', { week: range(weekStart, end(weekStart)) })}
                    </button>
                </div>
            </div>
        );
    }

    // The list keeps its week even if the first day of the week changed since: asked for by its date, it opens
    if (list.week_start !== weekStart && list.week_start !== requested) {
        const replace = () => {
            if (!confirm(t('shopping.confirmReplace', { week: range(list.week_start, list.week_end) }))) return;
            run(() => startShopping(weekStart, true));
        };
        return (
            <div className="mx-auto max-w-3xl space-y-4">
                <h1 className="text-xl">{t('shopping.title')}</h1>
                {feedback}
                <div className={`${CARD} space-y-3`}>
                    <p>{t('shopping.otherWeek', { week: range(list.week_start, list.week_end) })}</p>
                    <div className="flex flex-wrap gap-3">
                        <button type="button" className={BUTTON} onClick={() => setSearch({ start: list.week_start })}>
                            {t('shopping.openOther')}
                        </button>
                        <button type="button" className={BUTTON_SECONDARY} disabled={busy} onClick={replace}>
                            {t('shopping.replace')}
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    const toBuy = list.lines.filter((line) => line.buy).length;
    const discard = () => {
        if (confirm(t('shopping.confirmDiscard'))) run(async () => {
            await discardShopping();
            return null;
        });
    };

    return (
        <div className="mx-auto max-w-3xl space-y-4">
            <div className="flex flex-wrap items-baseline gap-x-3">
                <h1 className="text-xl">
                    {t('shopping.title')} · {range(list.week_start, list.week_end)}
                </h1>
                <p className="text-sm text-slate-400">
                    {list.started_by && t('shopping.startedBy', { name: list.started_by })}
                    {list.changed_by && ` · ${t('shopping.changedBy', { name: list.changed_by, time: time(list.changed_at) })}`}
                </p>
            </div>
            {feedback}

            <section className={`${CARD} space-y-2`} aria-labelledby="shopping-meals">
                <h2 id="shopping-meals" className="text-lg">
                    {t('shopping.meals')}
                </h2>
                <ul className="space-y-1">
                    {list.meals.map((meal) => (
                        <li key={meal.entry_id}>
                            <label className="flex items-start gap-2">
                                <input
                                    type="checkbox"
                                    className="mt-1"
                                    checked={meal.ticked}
                                    disabled={busy}
                                    onChange={(e) => {
                                        const ticked = e.target.checked;
                                        // Shown at once; the answer brings the lines that follow from it
                                        setList({ ...list, meals: list.meals.map((m) => (m === meal ? { ...m, ticked } : m)) });
                                        run(() => tickMeal(meal.entry_id, ticked));
                                    }}
                                />
                                <span className="min-w-0 break-words">
                                    {weekday(meal.date)} · {t(`plan.slots.${meal.slot}`)} · <b>{meal.title}</b>
                                    {meal.people !== null && (
                                        <span className="text-slate-400"> ({t('shopping.people', { count: meal.people })})</span>
                                    )}
                                </span>
                            </label>
                        </li>
                    ))}
                    {list.notes.map((note) => (
                        <li key={`${note.date}-${note.slot}-${note.note}`} className="pl-6 text-slate-500">
                            {weekday(note.date)} · {t(`plan.slots.${note.slot}`)} · {note.note}
                        </li>
                    ))}
                </ul>
            </section>

            <section className={`${CARD} space-y-3`} aria-labelledby="shopping-items">
                <h2 id="shopping-items" className="text-lg">
                    {t('shopping.items')}
                </h2>
                {list.lines.length === 0 && <p className="text-sm text-slate-400">{t('shopping.noItems')}</p>}
                <ul className="space-y-1">
                    {list.lines.map((line) => (
                        <li key={line.key} className={changed.keys.has(line.key) ? '-mx-2 rounded-lg bg-amber-400/15 px-2' : ''}>
                            <label className="flex items-start gap-2">
                                <input
                                    type="checkbox"
                                    className="mt-1"
                                    checked={line.buy}
                                    disabled={busy}
                                    onChange={(e) => {
                                        const buy = e.target.checked;
                                        setList({ ...list, lines: list.lines.map((l) => (l === line ? { ...l, buy } : l)) });
                                        run(() => chooseLine(line.key, buy));
                                    }}
                                />
                                <span className={`min-w-0 break-words ${line.buy ? '' : 'text-slate-500 line-through'}`}>
                                    {spec(line) && <span>{spec(line)} </span>}
                                    {line.name}
                                </span>
                                <span className="min-w-0 break-words text-sm text-slate-400">
                                    {line.meals.length > 0 && t('shopping.from', { meals: line.meals.join(', ') })}
                                    {line.staple && !line.buy && ` ${t('shopping.usuallyAtHome')}`}
                                </span>
                                {changed.keys.has(line.key) && (
                                    <span className="shrink-0 rounded-full bg-amber-400/20 px-2 text-xs text-amber-100">
                                        {t('shopping.changed')}
                                    </span>
                                )}
                            </label>
                        </li>
                    ))}
                </ul>
                {changed.gone.length > 0 && (
                    <p className="text-sm text-amber-100">{t('shopping.gone', { names: changed.gone.join(', ') })}</p>
                )}
                <form className="flex flex-wrap items-end gap-2" onSubmit={add}>
                    <label className="min-w-0 flex-1 space-y-1">
                        <span className="block text-sm text-slate-300">{t('shopping.addName')}</span>
                        <input
                            className={`${FIELD} w-full`}
                            maxLength={100}
                            required
                            placeholder={t('shopping.addNamePlaceholder')}
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </label>
                    <label className="w-32 space-y-1">
                        <span className="block text-sm text-slate-300">{t('shopping.addAmount')}</span>
                        <input
                            className={`${FIELD} w-full`}
                            maxLength={50}
                            placeholder={t('shopping.addAmountPlaceholder')}
                            value={amount}
                            onChange={(e) => setAmount(e.target.value)}
                        />
                    </label>
                    <button type="submit" className={BUTTON_SECONDARY} disabled={busy || !name.trim()}>
                        {t('shopping.add')}
                    </button>
                </form>
                {list.extras.length > 0 && (
                    <ul className="flex flex-wrap gap-2">
                        {list.extras.map((extra) => (
                            <li key={extra.id}>
                                <button
                                    type="button"
                                    className="rounded-full border border-white/15 px-3 py-1 text-sm hover:bg-white/10"
                                    aria-label={t('shopping.removeExtra', { name: extra.name })}
                                    disabled={busy}
                                    onClick={() => run(() => removeExtra(extra.id))}
                                >
                                    {extra.amount ? `${extra.amount} ${extra.name}` : extra.name} ✕
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            <div className="flex flex-wrap items-center gap-3">
                {bringReady(bring) ? (
                    <button type="button" className={BUTTON} disabled={busy || toBuy === 0} onClick={() => send(list)}>
                        {t('shopping.send', { count: toBuy })}
                    </button>
                ) : (
                    <Link to="/einstellungen" className="text-cyan-300 underline">
                        {t('shopping.setUpBring')}
                    </Link>
                )}
                <button type="button" className={`${BUTTON_SECONDARY} ml-auto`} disabled={busy} onClick={discard}>
                    {t('shopping.discard')}
                </button>
            </div>
        </div>
    );
}
