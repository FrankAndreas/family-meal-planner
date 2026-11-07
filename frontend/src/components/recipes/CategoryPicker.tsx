import type { Dispatch, SetStateAction } from 'react';
import { useTranslation } from 'react-i18next';
import { CATEGORIES, inOrder, type Category } from '../../categories';

interface CategoryPickerProps {
    value: Category[];
    // A state setter: each toggle works on the newest list, even two in a row
    onChange: Dispatch<SetStateAction<Category[]>>;
    labelClass: string;
}

// A recipe's categories, ticked on and off (kept in the categories' own order)
export default function CategoryPicker({ value, onChange, labelClass }: CategoryPickerProps) {
    const { t } = useTranslation();
    const toggle = (category: Category) =>
        onChange((now) => (now.includes(category) ? now.filter((c) => c !== category) : inOrder([...now, category])));
    return (
        <div className="sm:col-span-2" role="group" aria-labelledby="categories-label">
            <p id="categories-label" className={labelClass}>
                {t('recipes.categories')}
            </p>
            <div className="flex flex-wrap gap-2">
                {CATEGORIES.map((category) => {
                    const on = value.includes(category);
                    return (
                        <button
                            key={category}
                            type="button"
                            aria-pressed={on}
                            onClick={() => toggle(category)}
                            className={`rounded-full border px-3 py-1 text-sm ${
                                on
                                    ? 'border-amber-300 bg-amber-300/15 text-white'
                                    : 'border-white/10 text-slate-300 hover:bg-white/5'
                            }`}
                        >
                            {t(`recipes.category.${category}`)}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
