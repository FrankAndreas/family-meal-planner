import { format, parseISO } from 'date-fns';
import { de, enUS } from 'date-fns/locale';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { bringReady } from '../bring';
import ShoppingLines from '../components/shopping/ShoppingLines';
import ShoppingMeals from '../components/shopping/ShoppingMeals';
import { useShoppingList } from '../hooks/useShoppingList';
import type { Language } from '../i18n';
import {
    addExtra,
    chooseLine,
    discardShopping,
    formatSpec,
    removeExtra,
    startShopping,
    tickMeal,
    type ShoppingLine,
    type ShoppingMeal,
} from '../shopping';
import { BUTTON, BUTTON_SECONDARY, CARD, ERROR, PAGE } from '../ui';

// The shared shopping list (spec 2026-11-06): pick the week's meals, drop or add items, send them to Bring!
export default function ShoppingPage() {
    const { t, i18n } = useTranslation();
    const lang = (i18n.language === 'en' ? 'en' : 'de') as Language;
    const locale = lang === 'de' ? de : enUS;
    const [search, setSearch] = useSearchParams();
    const requested = search.get('start');
    const { list, setList, weekStart, bring, busy, error, message, changed, placed, run, send } =
        useShoppingList(requested);

    const day = (iso: string) => format(parseISO(iso), 'EEEEEE d.M.', { locale });
    const range = (start: string, end: string) => `${day(start)} – ${day(end)}`;
    const end = (start: string) => format(new Date(parseISO(start).getTime() + 6 * 86_400_000), 'yyyy-MM-dd');
    const time = (utc: string) => format(new Date(`${utc}Z`), 'HH:mm', { locale });
    const spec = (line: ShoppingLine) => formatSpec(line, (unit) => t(`units.${unit}` as 'units.g'), lang);

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
        return <div className={`${PAGE} space-y-4`}>{feedback}</div>;
    }

    if (list === null) {
        return (
            <div className={`${PAGE} space-y-4`}>
                <h1 className="text-2xl">{t('shopping.title')}</h1>
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
            <div className={`${PAGE} space-y-4`}>
                <h1 className="text-2xl">{t('shopping.title')}</h1>
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
    // Shown at once; the answer brings the lines that follow from it
    const tick = (meal: ShoppingMeal, ticked: boolean) => {
        setList({ ...list, meals: list.meals.map((m) => (m === meal ? { ...m, ticked } : m)) });
        run(() => tickMeal(meal.entry_id, ticked));
    };
    const choose = (line: ShoppingLine, buy: boolean) => {
        setList({ ...list, lines: list.lines.map((l) => (l === line ? { ...l, buy } : l)) });
        run(() => chooseLine(line.key, buy));
    };
    const discard = () => {
        if (confirm(t('shopping.confirmDiscard'))) run(async () => {
            await discardShopping();
            return null;
        });
    };

    return (
        <div className={`${PAGE} space-y-4`}>
            <div className="flex flex-wrap items-baseline gap-x-3">
                <h1 className="text-2xl">
                    {t('shopping.title')} · {range(list.week_start, list.week_end)}
                </h1>
                <p className="text-sm text-slate-400">
                    {list.started_by && t('shopping.startedBy', { name: list.started_by })}
                    {list.changed_by && ` · ${t('shopping.changedBy', { name: list.changed_by, time: time(list.changed_at) })}`}
                </p>
            </div>
            {feedback}

            <ShoppingMeals list={list} busy={busy} onTick={tick} />

            <ShoppingLines
                list={list}
                placed={placed}
                changed={changed}
                busy={busy}
                spec={spec}
                onChoose={choose}
                onAdd={(name, amount) => run(() => addExtra(name, amount))}
                onRemoveExtra={(id) => run(() => removeExtra(id))}
            />

            {/* Sending stays in reach on a long list: above the phone's bottom bar, at the bottom of the screen elsewhere */}
            {bringReady(bring) && (
                <div className="sticky bottom-[4.25rem] z-10 -mx-3 rounded-2xl border border-white/10 bg-slate-900/90 p-3 backdrop-blur-md sm:bottom-2">
                    <button type="button" className={`${BUTTON} w-full sm:w-auto`} disabled={busy || toBuy === 0} onClick={() => send(list, spec)}>
                        {t('shopping.send', { count: toBuy })}
                    </button>
                </div>
            )}
            <div className="flex flex-wrap items-center gap-3">
                {!bringReady(bring) && (
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
