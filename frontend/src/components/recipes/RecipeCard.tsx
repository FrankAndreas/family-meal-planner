import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { apiUrl } from '../../api';
import { sinceText } from '../../lastEaten';
import { photoSrc } from '../../photoUrl';
import type { RecipeSummary } from '../../recipes';
import Stars from './Stars';

interface RecipeCardProps {
    recipe: RecipeSummary;
    // Without onClick the card links to the recipe
    onClick?: () => void;
    compact?: boolean;
    // A card that can be picked (planning): shown and announced as pressed
    selected?: boolean;
}

// `full`: the whole photo (a recipe's own page); else the small version, loaded only once it is near the screen
export function RecipeThumb({ recipe, className, full = false }: { recipe: RecipeSummary; className: string; full?: boolean }) {
    if (recipe.photo_url)
        return (
            <img
                src={photoSrc(apiUrl(recipe.photo_url), full ? 'full' : 'card')}
                alt=""
                loading={full ? 'eager' : 'lazy'}
                decoding="async"
                className={`${className} object-cover`}
            />
        );
    // No photo: a gradient with the first letter, so cards still differ at a glance
    return (
        <div
            className={`${className} flex items-center justify-center bg-gradient-to-br from-indigo-400/70 to-fuchsia-400/70 text-2xl font-bold text-white/90`}
        >
            {recipe.title.charAt(0).toUpperCase()}
        </div>
    );
}

// The family's average, and how many it averages, so nobody takes it for their own rating
function FamilyStars({ recipe }: { recipe: RecipeSummary }) {
    const { t, i18n } = useTranslation();
    if (recipe.rating_avg === null) return null;
    // "4,5" read out in German, "4.5" in English
    const value = new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 1 }).format(recipe.rating_avg);
    return (
        <span className="inline-flex items-center gap-1">
            <Stars value={recipe.rating_avg} label={t('recipes.familyAverage', { value, count: recipe.rating_count })} />
            <span aria-hidden="true">{t('recipes.averageOf', { count: recipe.rating_count })}</span>
        </span>
    );
}

export default function RecipeCard({ recipe, onClick, compact = false, selected }: RecipeCardProps) {
    const { t } = useTranslation();
    const body = compact ? (
        <div className="flex items-center gap-3 p-2">
            <RecipeThumb recipe={recipe} className="h-12 w-12 flex-none rounded-lg" />
            <div className="min-w-0">
                <div className="truncate font-semibold">{recipe.title}</div>
                <div className="text-xs text-slate-400">
                    <FamilyStars recipe={recipe} />
                    {recipe.my_favorite && <span className="ml-1 text-fuchsia-300">♥</span>}
                </div>
                <div className="text-xs text-slate-400">
                    {recipe.last_eaten ? t('recipes.lastEaten', { when: sinceText(recipe.last_eaten) }) : t('recipes.neverEaten')}
                </div>
            </div>
        </div>
    ) : (
        <>
            <RecipeThumb recipe={recipe} className="h-36 w-full rounded-t-2xl" />
            <div className="space-y-1 p-3">
                <div className="flex items-start gap-2">
                    <span className="mr-auto font-semibold leading-tight">{recipe.title}</span>
                    {recipe.my_favorite && <span className="text-fuchsia-300">♥</span>}
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                    {recipe.rating_avg !== null ? <FamilyStars recipe={recipe} /> : t('recipes.notRated')}
                    {recipe.total_minutes !== null && <span>· {t('recipes.minutes', { count: recipe.total_minutes })}</span>}
                </div>
            </div>
        </>
    );
    const className = `glass-card block w-full overflow-hidden text-left transition hover:border-cyan-400/40 ${
        selected ? 'ring-2 ring-cyan-400' : ''
    }`;
    if (onClick) {
        return (
            <button type="button" onClick={onClick} className={className} aria-pressed={selected}>
                {body}
            </button>
        );
    }
    return (
        <Link to={`/rezepte/${recipe.id}`} className={className}>
            {body}
        </Link>
    );
}
