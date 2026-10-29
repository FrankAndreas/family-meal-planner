import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { formatAmount } from '../amounts';
import api, { errorMessage } from '../api';
import { useAuth } from '../AuthContext';
import PeopleStepper from '../components/recipes/PeopleStepper';
import { RecipeThumb } from '../components/recipes/RecipeCard';
import Stars from '../components/recipes/Stars';
import type { Language } from '../i18n';
import { defaultPeople, fetchRecipe, type Ingredient, type Recipe } from '../recipes';
import type { FamilySettings } from '../types';
import { BUTTON_DANGER, BUTTON_SECONDARY, CARD, ERROR } from '../ui';

function IngredientLine({ ingredient }: { ingredient: Ingredient }) {
    const { t, i18n } = useTranslation();
    const amount = ingredient.scaled_amount;
    const parts = [
        amount === null ? '' : formatAmount(amount, i18n.language as Language),
        ingredient.unit ? t(`units.${ingredient.unit}` as 'units.g') : '',
        ingredient.name,
    ].filter(Boolean);
    return (
        <li className="flex gap-2 py-1">
            <span>{parts.join(' ')}</span>
            {ingredient.note && <span className="text-slate-400">({ingredient.note})</span>}
        </li>
    );
}

export default function RecipeView() {
    const { t } = useTranslation();
    const { id } = useParams();
    const navigate = useNavigate();
    const [search] = useSearchParams();
    const { user } = useAuth();
    const [recipe, setRecipe] = useState<Recipe | null>(null);
    const [people, setPeople] = useState<number | null>(Number(search.get('personen')) || null);
    const [error, setError] = useState('');

    // First load without people, to learn the recipe's own yield; then every change of people asks again
    useEffect(() => {
        let current = true;
        const load = async () => {
            let wanted = people;
            if (wanted === null) {
                const [plain, settings] = await Promise.all([
                    fetchRecipe(id!),
                    api.get<FamilySettings>('/api/settings'),
                ]);
                wanted = defaultPeople(plain, settings.data.family_size);
                if (!current) return;
                setPeople(wanted);
            }
            const scaled = await fetchRecipe(id!, wanted);
            if (current) setRecipe(scaled);
        };
        load().catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, [id, people]);

    const change = async (action: () => Promise<{ data: Recipe }>) => {
        setError('');
        try {
            const changed = (await action()).data;
            setRecipe({ ...changed, ingredients: recipe!.ingredients, people: recipe!.people, factor: recipe!.factor });
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    const remove = async () => {
        if (!confirm(t('recipes.confirmDelete', { title: recipe!.title }))) return;
        try {
            await api.delete(`/api/recipes/${recipe!.id}`);
            navigate('/rezepte');
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    if (!recipe) return error ? <p className={ERROR}>{error}</p> : <p className="text-slate-400">{t('common.loading')}</p>;

    // Ingredients under their headings, in order
    const groups: { name: string | null; items: Ingredient[] }[] = [];
    for (const ingredient of recipe.ingredients) {
        const last = groups[groups.length - 1];
        if (last && last.name === ingredient.group) last.items.push(ingredient);
        else groups.push({ name: ingredient.group, items: [ingredient] });
    }

    return (
        <article className="mx-auto max-w-4xl space-y-6">
            {recipe.deleted && <p className={ERROR}>{t('recipes.deletedBanner')}</p>}
            <div className={`${CARD} grid gap-5 md:grid-cols-[16rem_1fr]`}>
                <RecipeThumb recipe={recipe} className="h-56 w-full rounded-xl md:h-64" />
                <div className="space-y-3">
                    <h1 className="text-3xl">{recipe.title}</h1>
                    <div className="flex flex-wrap gap-2 text-sm text-slate-400">
                        {recipe.prep_minutes !== null && <span>{t('recipes.prep', { count: recipe.prep_minutes })}</span>}
                        {recipe.cook_minutes !== null && <span>{t('recipes.cook', { count: recipe.cook_minutes })}</span>}
                        {recipe.servings_unit && (
                            <span>{t('recipes.yields', { amount: recipe.servings, unit: recipe.servings_unit })}</span>
                        )}
                        {recipe.source_url ? (
                            <a href={recipe.source_url} target="_blank" rel="noreferrer" className="text-cyan-300 underline">
                                {t('recipes.source')}
                            </a>
                        ) : null}
                    </div>
                    {recipe.tags.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                            {recipe.tags.map((tag) => (
                                <span key={tag} className="rounded-full bg-white/10 px-2 py-0.5 text-xs">
                                    {tag}
                                </span>
                            ))}
                        </div>
                    )}
                    {!recipe.deleted && (
                        <div className="flex flex-wrap items-center gap-3">
                            <Stars
                                value={recipe.my_rating}
                                size="lg"
                                onChange={(stars) => change(() => api.put(`/api/recipes/${recipe.id}/rating`, { stars }))}
                            />
                            <button
                                type="button"
                                aria-pressed={recipe.my_favorite}
                                aria-label={t('recipes.favorite')}
                                onClick={() =>
                                    change(() =>
                                        api.put(`/api/recipes/${recipe.id}/favorite`, { favorite: !recipe.my_favorite }),
                                    )
                                }
                                className={`text-3xl ${recipe.my_favorite ? 'text-fuchsia-300' : 'text-slate-600 hover:text-fuchsia-200'}`}
                            >
                                ♥
                            </button>
                        </div>
                    )}
                    {recipe.ratings.length > 0 && (
                        <ul className="flex flex-wrap gap-x-4 text-sm text-slate-300" aria-label={t('recipes.ratingsBy')}>
                            {recipe.ratings.map((r) => (
                                <li key={r.user_id}>
                                    {r.name}: {r.stars}★
                                </li>
                            ))}
                        </ul>
                    )}
                    {!recipe.deleted && (
                        <div className="flex flex-wrap gap-2 pt-2">
                            <Link to={`/rezepte/${recipe.id}/bearbeiten`} className={BUTTON_SECONDARY}>
                                {t('common.edit')}
                            </Link>
                            {user?.role === 'PARENT' && (
                                <button type="button" className={BUTTON_DANGER} onClick={remove}>
                                    {t('recipes.delete')}
                                </button>
                            )}
                        </div>
                    )}
                </div>
            </div>
            {error && <p className={ERROR}>{error}</p>}
            <div className="grid gap-6 md:grid-cols-[minmax(16rem,1fr)_2fr]">
                <section className={`${CARD} space-y-3`}>
                    <h2 className="text-lg">{t('recipes.ingredients')}</h2>
                    {people !== null && <PeopleStepper value={people} onChange={setPeople} />}
                    <ul aria-label={t('recipes.ingredients')} className="divide-y divide-white/5">
                        {groups.map((group, n) => [
                            group.name && (
                                <li key={`g${n}`} className="pt-3 text-sm font-semibold text-cyan-200">
                                    {group.name}
                                </li>
                            ),
                            ...group.items.map((item) => <IngredientLine key={item.id} ingredient={item} />),
                        ])}
                    </ul>
                </section>
                <section className={`${CARD} space-y-3`}>
                    <h2 className="text-lg">{t('recipes.steps')}</h2>
                    <ol aria-label={t('recipes.steps')} className="list-decimal space-y-3 pl-5">
                        {recipe.steps.map((step, n) => (
                            <li key={n} className="leading-relaxed">
                                {step}
                            </li>
                        ))}
                    </ol>
                    {recipe.notes && <p className="whitespace-pre-line text-slate-300">{recipe.notes}</p>}
                </section>
            </div>
        </article>
    );
}
