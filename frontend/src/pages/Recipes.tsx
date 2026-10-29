import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import api, { errorMessage } from '../api';
import UrlPaste from '../components/inbox/UrlPaste';
import RecipeCard from '../components/recipes/RecipeCard';
import { fetchRecipes, type RecipeSummary } from '../recipes';
import { BUTTON, BUTTON_SECONDARY, ERROR, INPUT } from '../ui';

export default function Recipes() {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const [pasting, setPasting] = useState(false);
    const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);
    const [tags, setTags] = useState<{ name: string; count: number }[]>([]);
    const [q, setQ] = useState('');
    const [tag, setTag] = useState('');
    const [onlyMine, setOnlyMine] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        api.get<{ name: string; count: number }[]>('/api/tags')
            .then((response) => setTags(response.data))
            .catch(() => {});
    }, []);

    useEffect(() => {
        let current = true;
        // A short pause while typing, so not every letter asks the server
        const timer = setTimeout(() => {
            fetchRecipes({ q, tag, favorites: onlyMine ? 'mine' : '' })
                .then((found) => current && setRecipes(found))
                .catch((err) => current && setError(errorMessage(err)));
        }, 200);
        return () => {
            current = false;
            clearTimeout(timer);
        };
    }, [q, tag, onlyMine]);

    const chip = (active: boolean) =>
        `rounded-full border px-3 py-1 text-sm ${
            active ? 'border-cyan-400 bg-cyan-400/15 text-white' : 'border-white/10 text-slate-300 hover:bg-white/5'
        }`;

    return (
        <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-3">
                <h1 className="mr-auto text-2xl">{t('nav.recipes')}</h1>
                <button type="button" className={BUTTON_SECONDARY} aria-expanded={pasting} onClick={() => setPasting(!pasting)}>
                    {t('recipes.importFromLink')}
                </button>
                <Link to="/rezepte/neu" className={BUTTON}>
                    {t('recipes.new')}
                </Link>
            </div>
            {/* Same as in the inbox: the draft shows up there (a parent's link is read at once) */}
            {pasting && <UrlPaste onAdded={() => navigate('/posteingang')} />}
            <div className="flex flex-wrap items-center gap-3">
                <input
                    className={`${INPUT} max-w-sm`}
                    type="search"
                    aria-label={t('recipes.search')}
                    placeholder={t('recipes.searchPlaceholder')}
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                />
                <label className="flex items-center gap-2 text-sm text-slate-300">
                    <input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} />
                    {t('recipes.onlyMyFavorites')}
                </label>
            </div>
            {tags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    <button type="button" className={chip(tag === '')} onClick={() => setTag('')}>
                        {t('recipes.allTags')}
                    </button>
                    {tags.map((item) => (
                        <button
                            key={item.name}
                            type="button"
                            className={chip(tag === item.name)}
                            onClick={() => setTag(tag === item.name ? '' : item.name)}
                        >
                            {item.name} <span className="text-slate-500">{item.count}</span>
                        </button>
                    ))}
                </div>
            )}
            {error && <p className={ERROR}>{error}</p>}
            {recipes && recipes.length === 0 && <p className="text-slate-400">{t('recipes.none')}</p>}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                {recipes?.map((recipe) => <RecipeCard key={recipe.id} recipe={recipe} />)}
            </div>
        </div>
    );
}
