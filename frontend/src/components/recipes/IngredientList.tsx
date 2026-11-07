import { useTranslation } from 'react-i18next';
import { formatAmount } from '../../amounts';
import type { Language } from '../../i18n';
import type { Ingredient } from '../../recipes';
import { ingredientGroups } from '../../recipeView';
import { CARD } from '../../ui';
import PeopleStepper from './PeopleStepper';

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

interface IngredientListProps {
    ingredients: Ingredient[];
    // For how many people the amounts are; null: not known yet (no stepper)
    people: number | null;
    onPeople: (people: number) => void;
}

// A recipe's ingredients under their headings, scaled for the people chosen with the stepper
export default function IngredientList({ ingredients, people, onPeople }: IngredientListProps) {
    const { t } = useTranslation();
    return (
        <section className={`${CARD} space-y-3`}>
            <h2 className="text-lg">{t('recipes.ingredients')}</h2>
            {people !== null && <PeopleStepper value={people} onChange={onPeople} />}
            <ul aria-label={t('recipes.ingredients')} className="divide-y divide-white/5">
                {ingredientGroups(ingredients).map((group, n) => [
                    group.name && (
                        <li key={`g${n}`} className="pt-3 text-sm font-semibold text-cyan-200">
                            {group.name}
                        </li>
                    ),
                    ...group.items.map((item) => <IngredientLine key={item.id} ingredient={item} />),
                ])}
            </ul>
        </section>
    );
}
