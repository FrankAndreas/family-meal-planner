import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import api, { errorMessage } from '../../api';
import { fetchSwissmilk, SWISSMILK_GAP_MS, type SwissmilkResult, type UseUpMode } from '../../useUp';
import { BUTTON_SECONDARY, ERROR } from '../../ui';
import AuthImage from '../AuthImage';

interface SwissmilkResultsProps {
    have: string[];
    mode: UseUpMode;
}

// A pause after a change, so a few quick changes make one search
const SETTLE_MS = 600;

// Swissmilk recipes for what's at home, searched only when asked: the words go to Swissmilk only then
export default function SwissmilkResults({ have, mode }: SwissmilkResultsProps) {
    const { t } = useTranslation();
    const [open, setOpen] = useState(false);
    // The answer and the search it answers: shown only while that is still the search on screen
    const [answer, setAnswer] = useState<{ key: string; results: SwissmilkResult[] } | null>(null);
    const [error, setError] = useState('');
    // Taken over here: waiting in the inbox now
    const [taken, setTaken] = useState<string[]>([]);
    const lastSearch = useRef(0);
    const key = JSON.stringify([have, mode]);

    useEffect(() => {
        if (!open) return;
        let current = true;
        // Never sooner than the backend allows, so changing the ingredients doesn't end in "too many searches"
        const wait = Math.max(SETTLE_MS, SWISSMILK_GAP_MS - (Date.now() - lastSearch.current));
        const timer = setTimeout(
            () => {
                lastSearch.current = Date.now();
                fetchSwissmilk(have, mode)
                    .then((results) => {
                        if (!current) return;
                        setAnswer({ key: JSON.stringify([have, mode]), results });
                        setError('');
                    })
                    .catch((err) => {
                        if (!current) return;
                        setAnswer(null);
                        setError(errorMessage(err));
                    });
            },
            lastSearch.current ? wait : 0,
        );
        return () => {
            current = false;
            clearTimeout(timer);
        };
    }, [open, have, mode]);

    const takeOver = async (url: string) => {
        setError('');
        try {
            await api.post('/api/inbox/urls', { url });
            setTaken((before) => [...before, url]);
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    if (!open) {
        return (
            <button type="button" className={BUTTON_SECONDARY} onClick={() => setOpen(true)}>
                {t('swissmilk.search')}
            </button>
        );
    }

    const results = answer?.key === key ? answer.results : null;
    return (
        <section aria-label={t('swissmilk.title')} className="space-y-3">
            <h2 className="text-lg">{t('swissmilk.title')}</h2>
            {error && <p className={ERROR}>{error}</p>}
            {!results && !error && <p className="text-slate-400">{t('swissmilk.searching')}</p>}
            {results && results.length === 0 && <p className="text-slate-400">{t('swissmilk.none')}</p>}
            {results && results.length > 0 && (
                <ul className="grid gap-3 md:grid-cols-2">
                    {results.map((recipe) => {
                        const waiting = recipe.waiting || taken.includes(recipe.url);
                        return (
                            <li key={recipe.url} className="glass-card flex gap-3 p-2">
                                {recipe.photo ? (
                                    <AuthImage src={recipe.photo} alt="" className="h-16 w-16 flex-none rounded-lg object-cover" />
                                ) : (
                                    <div className="h-16 w-16 flex-none rounded-lg bg-white/5" aria-hidden />
                                )}
                                <div className="min-w-0 flex-1 space-y-1">
                                    <div className="font-semibold leading-tight">{recipe.title}</div>
                                    <div className="text-sm text-emerald-300">
                                        {t('useUp.used', { names: recipe.used.join(', ') })}
                                    </div>
                                    {recipe.missing.length > 0 && (
                                        <div className="text-sm text-rose-300">
                                            {t('useUp.missing', { names: recipe.missing.join(', ') })}
                                        </div>
                                    )}
                                    <div className="flex flex-wrap items-center gap-3 pt-1 text-sm">
                                        <a href={recipe.url} target="_blank" rel="noopener noreferrer" className="text-cyan-300 underline">
                                            {t('swissmilk.view')}
                                        </a>
                                        {recipe.recipe_id !== null ? (
                                            <Link to={`/rezepte/${recipe.recipe_id}`} className="text-slate-300 underline">
                                                {t('swissmilk.already')}
                                            </Link>
                                        ) : waiting ? (
                                            <Link to="/posteingang" className="text-slate-300 underline">
                                                {t('swissmilk.waiting')}
                                            </Link>
                                        ) : (
                                            <button
                                                type="button"
                                                className="rounded-lg border border-white/15 px-3 py-1 hover:bg-white/5"
                                                onClick={() => takeOver(recipe.url)}
                                            >
                                                {t('swissmilk.takeOver')}
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}
        </section>
    );
}
