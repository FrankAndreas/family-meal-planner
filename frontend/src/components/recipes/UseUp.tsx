import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { errorMessage } from '../../api';
import { sinceText } from '../../lastEaten';
import { fetchIngredientNames, fetchUseUp, MAX_HAVE, MAX_MISSING, type UseUpMode, type UseUpResult } from '../../useUp';
import { BUTTON_SECONDARY, ERROR } from '../../ui';
import IngredientChips from './IngredientChips';
import { RecipeThumb } from './RecipeCard';
import SwissmilkResults from './SwissmilkResults';

interface UseUpProps {
    have: string[];
    mode: UseUpMode;
    onChange: (have: string[], mode: UseUpMode) => void;
}

const MODES: UseUpMode[] = ['use_up', 'cook_now'];

// "Was habe ich?": recipes of the collection for what's at home, e.g. what needs using soon
export default function UseUp({ have, mode, onChange }: UseUpProps) {
    const { t } = useTranslation();
    // The answer and the search it answers: shown only while that is still the search on screen
    const [answer, setAnswer] = useState<{ key: string; results: UseUpResult[] } | null>(null);
    const key = JSON.stringify([have, mode]);
    const results = answer?.key === key ? answer.results : null;
    const [error, setError] = useState('');

    useEffect(() => {
        if (!have.length) return;
        let current = true;
        // A short pause, so quick changes ask the server once
        const timer = setTimeout(() => {
            fetchUseUp(have, mode)
                .then((found) => {
                    if (!current) return;
                    setAnswer({ key: JSON.stringify([have, mode]), results: found });
                    setError('');
                })
                .catch((err) => {
                    if (!current) return;
                    setAnswer(null);
                    setError(errorMessage(err));
                });
        }, 200);
        return () => {
            current = false;
            clearTimeout(timer);
        };
    }, [have, mode]);

    // No error of an earlier search once everything is cleared
    const change = (nextHave: string[], nextMode: UseUpMode) => {
        if (!nextHave.length) setError('');
        onChange(nextHave, nextMode);
    };

    const modeButton = (key: UseUpMode) =>
        `rounded-full border px-3 py-1 text-sm ${
            mode === key ? 'border-cyan-400 bg-cyan-400/15 text-white' : 'border-white/10 text-slate-300 hover:bg-white/5'
        }`;

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-start gap-2">
                <div className="min-w-0 flex-1 basis-72">
                    <IngredientChips
                        values={have}
                        onChange={(next) => change(next, mode)}
                        label={t('useUp.ingredient')}
                        placeholder={t('useUp.placeholder')}
                        suggest={fetchIngredientNames}
                        max={MAX_HAVE}
                    />
                </div>
                {have.length > 0 && (
                    <button type="button" className={BUTTON_SECONDARY} onClick={() => change([], mode)}>
                        {t('useUp.clear')}
                    </button>
                )}
            </div>
            <div className="flex flex-wrap gap-2">
                {MODES.map((key) => (
                    <button
                        key={key}
                        type="button"
                        aria-pressed={mode === key}
                        aria-describedby={`use-up-mode-${key}`}
                        className={modeButton(key)}
                        onClick={() => change(have, key)}
                    >
                        {t(`useUp.modes.${key}`)}
                    </button>
                ))}
            </div>
            {/* What each mode does: the chosen one's shown, both read out with their button */}
            {MODES.map((key) => (
                <p key={key} id={`use-up-mode-${key}`} hidden={mode !== key} className="-mt-2 text-sm text-slate-400">
                    {t(`useUp.explain.${key}`, { max: MAX_MISSING })}
                </p>
            ))}
            {error && <p className={ERROR}>{error}</p>}
            {!have.length ? (
                <p className="text-slate-400">{t('useUp.hint')}</p>
            ) : (
                results && (
                    <>
                        {results.length === 0 && <p className="text-slate-400">{t('useUp.none')}</p>}
                        <ul className="grid gap-3 md:grid-cols-2">
                            {results.map((recipe) => (
                                <li key={recipe.id}>
                                    <Link
                                        to={`/rezepte/${recipe.id}`}
                                        className="glass-card flex items-center gap-3 p-2 transition hover:border-cyan-400/40"
                                    >
                                        <RecipeThumb recipe={recipe} className="h-16 w-16 flex-none rounded-lg" />
                                        <div className="min-w-0 space-y-0.5">
                                            <div className="font-semibold leading-tight">{recipe.title}</div>
                                            <div className="text-sm text-emerald-300">
                                                {t('useUp.used', { names: recipe.used.join(', ') })}
                                            </div>
                                            {recipe.missing.length > 0 && (
                                                <div className="text-sm text-rose-300">
                                                    {t('useUp.missing', { names: recipe.missing.join(', ') })}
                                                </div>
                                            )}
                                            <div className="text-xs text-slate-400">
                                                {recipe.last_eaten
                                                    ? t('recipes.lastEaten', { when: sinceText(recipe.last_eaten) })
                                                    : t('recipes.neverEaten')}
                                            </div>
                                        </div>
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </>
                )
            )}
            {have.length > 0 && <SwissmilkResults have={have} mode={mode} />}
        </div>
    );
}
