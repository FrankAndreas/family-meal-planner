import { format, parseISO } from 'date-fns';
import { useTranslation } from 'react-i18next';
import { usePlaceText } from '../../hooks/usePlaceText';
import { isWebLink, siteName } from '../../links';
import type { Slot } from '../../plan';
import type { Recipe } from '../../recipes';

// How a recipe from the inbox came in
const SOURCE_TEXT = {
    mail: 'recipes.sourceByMail',
    url: 'recipes.sourceByLink',
    scan: 'recipes.sourceByScan',
    text: 'recipes.sourceByText',
} as const;

interface RecipeFactsProps {
    recipe: Recipe;
    // The days it was eaten, newest first
    eatenOn: string[];
    // Where it's planned from today on
    planned: { date: string; slot: Slot }[];
}

// What there is to know about a recipe at a glance: times, yield, where it came from, when it was eaten and is
// planned, its categories and tags
export default function RecipeFacts({ recipe, eatenOn, planned }: RecipeFactsProps) {
    const { t } = useTranslation();
    const place = usePlaceText();
    return (
        <>
            <div className="flex flex-wrap gap-2 text-sm text-slate-400">
                {recipe.prep_minutes !== null && <span>{t('recipes.prep', { count: recipe.prep_minutes })}</span>}
                {recipe.cook_minutes !== null && <span>{t('recipes.cook', { count: recipe.cook_minutes })}</span>}
                {recipe.servings_unit && (
                    <span>{t('recipes.yields', { amount: recipe.servings, unit: recipe.servings_unit })}</span>
                )}
            </div>
            {(recipe.source_url || recipe.source_mail) && (
                <p className="text-sm text-slate-300">
                    {t('recipes.sourceLabel')}{' '}
                    {recipe.source_url &&
                        (isWebLink(recipe.source_url) ? (
                            <a href={recipe.source_url} target="_blank" rel="noreferrer" className="text-cyan-300 underline">
                                {siteName(recipe.source_url)}
                                <span aria-hidden> ↗</span>
                            </a>
                        ) : (
                            recipe.source_url
                        ))}
                    {recipe.source_url && recipe.source_mail && ' · '}
                    {recipe.source_mail &&
                        t(SOURCE_TEXT[recipe.source_mail.kind], {
                            name: recipe.source_mail.user_name ?? '?',
                            date: format(parseISO(`${recipe.source_mail.received_at}Z`), 'd.M.yyyy'),
                        })}
                </p>
            )}
            {recipe.last_eaten ? (
                <details className="text-sm text-slate-300">
                    <summary className="cursor-pointer">
                        {t('recipes.lastEatenOn', {
                            date: format(parseISO(recipe.last_eaten), 'd.M.yyyy'),
                            count: recipe.times_eaten,
                        })}
                    </summary>
                    <ul className="mt-1 flex flex-wrap gap-x-3 text-slate-400">
                        {eatenOn.map((day) => (
                            <li key={day}>{format(parseISO(day), 'd.M.yyyy')}</li>
                        ))}
                    </ul>
                </details>
            ) : (
                <p className="text-sm text-slate-400">{t('recipes.neverEaten')}</p>
            )}
            {planned.length > 0 && (
                <p className="text-sm text-cyan-200" data-testid="planned-ahead">
                    {t('plan.plannedAhead', { places: planned.map((p) => place(p.date, p.slot)).join(' · ') })}
                </p>
            )}
            {recipe.categories.length > 0 && (
                <ul aria-label={t('recipes.categories')} className="flex flex-wrap gap-2">
                    {recipe.categories.map((category) => (
                        <li
                            key={category}
                            className="rounded-full border border-amber-300/40 px-2 py-0.5 text-xs text-amber-100"
                        >
                            {t(`recipes.category.${category}`)}
                        </li>
                    ))}
                </ul>
            )}
            {recipe.tags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    {recipe.tags.map((tag) => (
                        <span key={tag} className="rounded-full bg-white/10 px-2 py-0.5 text-xs">
                            {tag}
                        </span>
                    ))}
                </div>
            )}
        </>
    );
}
