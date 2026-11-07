import { useTranslation } from 'react-i18next';
import { CATEGORIES } from '../../categories';
import type { useRecipeSearch } from '../../hooks/useRecipeSearch';
import { BUTTON_SECONDARY, ERROR, INPUT } from '../../ui';
import RecipeCard from './RecipeCard';

// On the phone the filters are one row each that scrolls sideways; wider screens show them all
const CHIP_ROW = 'flex gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:overflow-visible sm:pb-0';

const chip = (active: boolean) =>
    `shrink-0 whitespace-nowrap rounded-full border px-3 py-1 text-sm ${
        active ? 'border-cyan-400 bg-cyan-400/15 text-white' : 'border-white/10 text-slate-300 hover:bg-white/5'
    }`;

// The collection, searched and filtered by category, tag and the person's favourites (the state lives in the page:
// useRecipeSearch)
export default function RecipeSearch({ search }: { search: ReturnType<typeof useRecipeSearch> }) {
    const { t } = useTranslation();
    const { filter, change, recipes, tags, error, aiOn, unsorted, sorting, sortWithAi } = search;
    const { q, tag, category, onlyMine } = filter;
    return (
        <>
            <div className="flex flex-wrap items-center gap-3">
                <input
                    className={`${INPUT} max-w-sm`}
                    type="search"
                    aria-label={t('recipes.search')}
                    placeholder={t('recipes.searchPlaceholder')}
                    value={q}
                    onChange={(e) => change({ q: e.target.value })}
                />
                <label className="flex items-center gap-2 text-sm text-slate-300">
                    <input type="checkbox" checked={onlyMine} onChange={(e) => change({ onlyMine: e.target.checked })} />
                    {t('recipes.onlyMyFavorites')}
                </label>
            </div>
            <div className={CHIP_ROW} role="group" aria-label={t('recipes.filterCategory')}>
                <button
                    type="button"
                    className={chip(category === '')}
                    aria-pressed={category === ''}
                    onClick={() => change({ category: '' })}
                >
                    {t('recipes.allCategories')}
                </button>
                {[...CATEGORIES, 'none' as const].map((key) => (
                    <button
                        key={key}
                        type="button"
                        className={chip(category === key)}
                        aria-pressed={category === key}
                        onClick={() => change({ category: category === key ? '' : key })}
                    >
                        {key === 'none' ? t('recipes.noCategory') : t(`recipes.category.${key}`)}
                    </button>
                ))}
            </div>
            {aiOn && category === 'none' && (unsorted > 0 || sorting) && (
                <div className="flex items-center gap-3">
                    <button type="button" className={BUTTON_SECONDARY} disabled={sorting !== null} onClick={sortWithAi}>
                        {t('recipes.categorizeAll', { count: unsorted })}
                    </button>
                    {sorting && (
                        <span role="status" className="text-sm text-slate-300">
                            {t('recipes.categorizeProgress', sorting)}
                        </span>
                    )}
                </div>
            )}
            {tags.length > 0 && (
                <div className={CHIP_ROW}>
                    <button type="button" className={chip(tag === '')} onClick={() => change({ tag: '' })}>
                        {t('recipes.allTags')}
                    </button>
                    {tags.map((item) => (
                        <button
                            key={item.name}
                            type="button"
                            className={chip(tag === item.name)}
                            onClick={() => change({ tag: tag === item.name ? '' : item.name })}
                        >
                            {item.name} <span className="text-slate-500">{item.count}</span>
                        </button>
                    ))}
                </div>
            )}
            {error && <p className={ERROR}>{error}</p>}
            {recipes && recipes.length === 0 && <p className="text-slate-400">{t('recipes.none')}</p>}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                {recipes?.map((recipe) => (
                    <RecipeCard key={recipe.id} recipe={recipe} />
                ))}
            </div>
        </>
    );
}
