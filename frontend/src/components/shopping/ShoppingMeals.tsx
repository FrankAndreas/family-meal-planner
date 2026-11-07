import { format, parseISO } from 'date-fns';
import { de, enUS } from 'date-fns/locale';
import { useTranslation } from 'react-i18next';
import type { ShoppingList, ShoppingMeal } from '../../shopping';
import { CARD } from '../../ui';

interface ShoppingMealsProps {
    list: ShoppingList;
    busy: boolean;
    onTick: (meal: ShoppingMeal, ticked: boolean) => void;
}

// The week's meals to shop for, ticked on or off; notes in the plan ("Pizza bestellen") are listed below
export default function ShoppingMeals({ list, busy, onTick }: ShoppingMealsProps) {
    const { t, i18n } = useTranslation();
    const locale = i18n.language === 'en' ? enUS : de;
    const weekday = (iso: string) => format(parseISO(iso), 'EEEEEE', { locale });
    return (
        <section className={`${CARD} space-y-2`} aria-labelledby="shopping-meals">
            <h2 id="shopping-meals" className="text-lg">
                {t('shopping.meals')}
            </h2>
            <ul className="space-y-1">
                {list.meals.map((meal) => (
                    <li key={meal.entry_id}>
                        <label className="flex items-start gap-2">
                            <input
                                type="checkbox"
                                className="mt-1"
                                checked={meal.ticked}
                                disabled={busy}
                                onChange={(e) => onTick(meal, e.target.checked)}
                            />
                            <span className="min-w-0 break-words">
                                {weekday(meal.date)} · {t(`plan.slots.${meal.slot}`)} · <b>{meal.title}</b>
                                {meal.people !== null && (
                                    <span className="text-slate-400"> ({t('shopping.people', { count: meal.people })})</span>
                                )}
                            </span>
                        </label>
                    </li>
                ))}
                {list.notes.map((note) => (
                    <li key={`${note.date}-${note.slot}-${note.note}`} className="pl-6 text-slate-500">
                        {weekday(note.date)} · {t(`plan.slots.${note.slot}`)} · {note.note}
                    </li>
                ))}
            </ul>
        </section>
    );
}
