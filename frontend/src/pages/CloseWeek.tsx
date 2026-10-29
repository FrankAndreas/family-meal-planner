import { format, parseISO } from 'date-fns';
import { de, enUS } from 'date-fns/locale';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api, { errorMessage } from '../api';
import NoteDialog from '../components/plan/NoteDialog';
import Stars from '../components/recipes/Stars';
import { addEntry, fetchWeek, type PlanEntry, updateEntry, type Week, weekdayKey } from '../plan';
import { BUTTON, CARD, ERROR } from '../ui';

export default function CloseWeek() {
    const { t, i18n } = useTranslation();
    const [search] = useSearchParams();
    const navigate = useNavigate();
    const [week, setWeek] = useState<Week | null>(null);
    const [instead, setInstead] = useState<PlanEntry | null>(null);
    const [error, setError] = useState('');
    const start = search.get('start');
    const locale = i18n.language === 'de' ? de : enUS;

    const reload = useCallback(async () => setWeek(await fetchWeek(start)), [start]);

    useEffect(() => {
        let current = true;
        fetchWeek(start)
            .then((loaded) => current && setWeek(loaded))
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, [start]);

    const run = async (action: () => Promise<unknown>) => {
        setError('');
        try {
            await action();
            await reload();
        } catch (err) {
            setError(errorMessage(err));
            await reload().catch(() => {});
        }
    };

    // Ticks show at once (a tap must feel like a tap); the server's answer follows, an error puts it back
    const setEaten = (entry: PlanEntry, eaten: boolean) => {
        setWeek((shown) =>
            shown ? { ...shown, entries: shown.entries.map((e) => (e.id === entry.id ? { ...e, eaten } : e)) } : shown,
        );
        run(() => updateEntry(entry.id, { eaten })).catch(() => {});
    };

    const close = async () => {
        try {
            await api.post('/api/plan/close', { start: week!.start });
            navigate('/');
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    if (!week) return error ? <p className={ERROR}>{error}</p> : <p className="text-slate-400">{t('common.loading')}</p>;

    return (
        <div className="mx-auto max-w-3xl space-y-5">
            <div>
                <h1 className="text-2xl">{t('close.title')}</h1>
                <p className="text-slate-400">{t('close.intro')}</p>
            </div>
            {week.days.map((day) => {
                const entries = week.entries.filter((e) => e.date === day);
                if (entries.length === 0) return null;
                return (
                    <section key={day} className={`${CARD} space-y-2`}>
                        <h2 className="text-base text-cyan-200">
                            {t(`weekdays.${weekdayKey(day)}`)} {format(parseISO(day), 'd.M.', { locale })}
                        </h2>
                        <ul className="divide-y divide-white/5">
                            {entries.map((entry) => (
                                <li key={entry.id} className="flex flex-wrap items-center gap-3 py-2">
                                    <span className="w-24 text-xs text-slate-400">{t(`plan.slots.${entry.slot}`)}</span>
                                    {entry.recipe ? (
                                        <>
                                            <label className="mr-auto flex items-center gap-2">
                                                <input
                                                    type="checkbox"
                                                    aria-label={t('close.eatenLabel', { title: entry.recipe.title })}
                                                    checked={entry.eaten}
                                                    onChange={(e) => setEaten(entry, e.target.checked)}
                                                    className="h-5 w-5"
                                                />
                                                <span className={entry.eaten ? '' : 'text-slate-500 line-through'}>
                                                    {entry.recipe.title}
                                                </span>
                                            </label>
                                            {entry.eaten && !entry.recipe_deleted && (
                                                <Stars
                                                    value={entry.recipe.my_rating}
                                                    onChange={(stars) =>
                                                        run(() => api.put(`/api/recipes/${entry.recipe!.id}/rating`, { stars }))
                                                    }
                                                />
                                            )}
                                            {!entry.eaten && (
                                                <button type="button" className="text-sm text-cyan-300 underline" onClick={() => setInstead(entry)}>
                                                    {t('close.instead')}
                                                </button>
                                            )}
                                        </>
                                    ) : (
                                        <span className="italic text-slate-300">{entry.note}</span>
                                    )}
                                </li>
                            ))}
                        </ul>
                    </section>
                );
            })}
            {error && <p className={ERROR}>{error}</p>}
            <button type="button" className={BUTTON} onClick={close}>
                {t('plan.closeWeek')}
            </button>
            {instead && (
                <NoteDialog
                    place={`${t(`weekdays.${weekdayKey(instead.date)}`)}, ${t(`plan.slots.${instead.slot}`)}`}
                    onClose={() => setInstead(null)}
                    onAdd={(note) => {
                        const entry = instead;
                        setInstead(null);
                        run(() => addEntry({ date: entry.date, slot: entry.slot, note }));
                    }}
                />
            )}
        </div>
    );
}
