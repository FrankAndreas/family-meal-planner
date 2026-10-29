import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { errorMessage } from '../../api';
import { fetchSuggestions, type SuggestionTab } from '../../plan';
import type { RecipeSummary } from '../../recipes';
import { ERROR, INPUT } from '../../ui';
import RecipeCard from '../recipes/RecipeCard';
import Draggable from './Draggable';

const TABS: SuggestionTab[] = ['favorites', 'long_ago', 'new', 'again'];

interface SuggestionPanelProps {
    selectedId: number | null;
    onPick: (recipe: RecipeSummary) => void;
    // Changes whenever the plan changed, so "Lange her" and "Neu" stay true
    version: number;
}

export default function SuggestionPanel({ selectedId, onPick, version }: SuggestionPanelProps) {
    const { t } = useTranslation();
    const [tab, setTab] = useState<SuggestionTab>('favorites');
    const [q, setQ] = useState('');
    const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);
    const [error, setError] = useState('');

    useEffect(() => {
        let current = true;
        const timer = setTimeout(() => {
            fetchSuggestions(tab, q)
                .then((found) => {
                    if (!current) return;
                    setRecipes(found);
                    setError('');
                })
                .catch((err) => current && setError(errorMessage(err)));
        }, 150);
        return () => {
            current = false;
            clearTimeout(timer);
        };
    }, [tab, q, version]);

    return (
        <aside className="glass-card flex max-h-[calc(100vh-8rem)] flex-col gap-3 p-3">
            <div role="tablist" className="grid grid-cols-2 gap-1">
                {TABS.map((key) => (
                    <button
                        key={key}
                        type="button"
                        role="tab"
                        aria-selected={tab === key}
                        onClick={() => setTab(key)}
                        className={`rounded-lg px-2 py-1.5 text-sm ${
                            tab === key ? 'bg-fuchsia-400/20 text-fuchsia-200' : 'text-slate-400 hover:bg-white/5'
                        }`}
                    >
                        {t(`plan.tabs.${key}`)}
                    </button>
                ))}
            </div>
            <input
                className={INPUT}
                type="search"
                aria-label={t('plan.searchSuggestions')}
                placeholder={t('recipes.searchPlaceholder')}
                value={q}
                onChange={(e) => setQ(e.target.value)}
            />
            {error && <p className={ERROR}>{error}</p>}
            <div className="flex-1 space-y-2 overflow-y-auto pr-1">
                {recipes?.length === 0 && <p className="p-2 text-sm text-slate-400">{t(`plan.empty.${tab}`)}</p>}
                {recipes?.map((recipe) => (
                    <Draggable key={recipe.id} id={`recipe|${recipe.id}|${recipe.title}`}>
                        <RecipeCard
                            recipe={recipe}
                            compact
                            selected={recipe.id === selectedId}
                            onClick={() => onPick(recipe)}
                        />
                    </Draggable>
                ))}
            </div>
            {selectedId !== null && <p className="text-xs text-cyan-300">{t('plan.pickCell')}</p>}
        </aside>
    );
}
