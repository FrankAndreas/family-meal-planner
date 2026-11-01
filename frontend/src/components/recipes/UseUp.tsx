import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { errorMessage } from '../../api';
import { sinceText } from '../../lastEaten';
import { fetchIngredientNames, fetchUseUp, MAX_HAVE, type UseUpMode, type UseUpResult } from '../../useUp';
import { BUTTON_SECONDARY, ERROR } from '../../ui';
import IngredientChips from './IngredientChips';
import { RecipeThumb } from './RecipeCard';

interface UseUpProps {
    have: string[];
    mode: UseUpMode;
    onChange: (have: string[], mode: UseUpMode) => void;
}

const MODES: UseUpMode[] = ['use_up', 'cook_now'];

// "Was habe ich?": recipes of the collection for what's at home, e.g. what needs using soon
export default function UseUp({ have, mode, onChange }: UseUpProps) {
    const { t } = useTranslation();
    const [results, setResults] = useState<UseUpResult[] | null>(null);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!have.length) return;
        let current = true;
        // A short pause, so quick changes ask the server once
        const timer = setTimeout(() => {
            fetchUseUp(have, mode)
                .then((found) => {
                    if (!current) return;
                    setResults(found);
                    setError('');
                })
                .catch((err) => {
                    if (!current) return;
                    // No old results under an error: they'd look like the answer
                    setResults(null);
                    setError(errorMessage(err));
                });
        }, 200);
        return () => {
            current = false;
            clearTimeout(timer);
        };
    }, [have, mode]);

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
                        onChange={(next) => onChange(next, mode)}
                        label={t('useUp.ingredient')}
                        placeholder={t('useUp.placeholder')}
                        suggest={fetchIngredientNames}
                        max={MAX_HAVE}
                    />
                </div>
                {have.length > 0 && (
                    <button type="button" className={BUTTON_SECONDARY} onClick={() => onChange([], mode)}>
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
                        className={modeButton(key)}
                        onClick={() => onChange(have, key)}
                    >
                        {t(`useUp.modes.${key}`)}
                    </button>
                ))}
            </div>
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
                                            <div className="text-xs text-slate-500">
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
        </div>
    );
}
