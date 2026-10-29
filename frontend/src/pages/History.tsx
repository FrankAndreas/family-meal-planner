import { format, parseISO } from 'date-fns';
import { de, enUS } from 'date-fns/locale';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import api, { errorMessage } from '../api';
import { type PlanEntry, type Week, weekdayKey } from '../plan';
import { BUTTON_SECONDARY, CARD, ERROR } from '../ui';

const PAGE = 8;

function Entry({ entry }: { entry: PlanEntry }) {
    if (!entry.recipe) return <span className="italic text-slate-400">{entry.note}</span>;
    const link = (
        <Link to={`/rezepte/${entry.recipe.id}`} className="hover:text-cyan-200">
            {entry.recipe.title}
        </Link>
    );
    // Not eaten: struck through, and announced as such
    return entry.eaten ? link : <del className="text-slate-500">{link}</del>;
}

export default function History() {
    const { t, i18n } = useTranslation();
    const locale = i18n.language === 'de' ? de : enUS;
    const [weeks, setWeeks] = useState<Week[]>([]);
    const [more, setMore] = useState(true);
    const [error, setError] = useState('');

    const load = async (before?: string) => {
        try {
            const older = (await api.get<Week[]>('/api/plan/history', { params: { weeks: PAGE, ...(before ? { before } : {}) } }))
                .data;
            setWeeks((shown) => [...shown, ...older]);
            setMore(older.length === PAGE);
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    useEffect(() => {
        let current = true;
        api.get<Week[]>('/api/plan/history', { params: { weeks: PAGE } })
            .then((r) => {
                if (!current) return;
                setWeeks(r.data);
                setMore(r.data.length === PAGE);
            })
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, []);

    const range = (week: Week) =>
        `${format(parseISO(week.start), 'EEEEEE d.M.', { locale })} – ${format(parseISO(week.end), 'EEEEEE d.M.', { locale })}`;

    return (
        <div className="mx-auto max-w-5xl space-y-5">
            <h1 className="text-2xl">{t('nav.history')}</h1>
            {error && <p className={ERROR}>{error}</p>}
            {weeks.length === 0 && !error && <p className="text-slate-400">{t('history.none')}</p>}
            {weeks.map((week) => (
                <section key={week.start} aria-label={range(week)} className={`${CARD} space-y-3`}>
                    <h2 className="flex items-center gap-2 text-base">
                        {range(week)}
                        {week.closed && <span className="rounded-full bg-emerald-400/15 px-2 text-xs text-emerald-200">{t('history.closed')}</span>}
                    </h2>
                    <div className="grid gap-2 sm:grid-cols-7">
                        {week.days.map((day) => (
                            <div key={day} className="space-y-1 rounded-lg bg-white/5 p-2 text-sm">
                                <div className="text-xs text-slate-400">
                                    {t(`weekdays.${weekdayKey(day)}`).slice(0, 2)} {format(parseISO(day), 'd.M.')}
                                </div>
                                {week.entries
                                    .filter((e) => e.date === day)
                                    .map((entry) => (
                                        <div key={entry.id} className="leading-tight">
                                            <Entry entry={entry} />
                                        </div>
                                    ))}
                            </div>
                        ))}
                    </div>
                </section>
            ))}
            {more && weeks.length > 0 && (
                <button type="button" className={BUTTON_SECONDARY} onClick={() => load(weeks[weeks.length - 1].start)}>
                    {t('history.older')}
                </button>
            )}
        </div>
    );
}
