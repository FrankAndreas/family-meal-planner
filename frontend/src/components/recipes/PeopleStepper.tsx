import { useTranslation } from 'react-i18next';
import { formatAmount } from '../../amounts';
import type { Language } from '../../i18n';

interface PeopleStepperProps {
    value: number;
    onChange: (people: number) => void;
}

// Big − / + buttons: easy to hit on an iPad propped up in the kitchen
export default function PeopleStepper({ value, onChange }: PeopleStepperProps) {
    const { t, i18n } = useTranslation();
    const button = 'h-10 w-10 rounded-full border border-white/15 text-xl hover:bg-white/10 disabled:opacity-40';
    return (
        <div className="inline-flex items-center gap-3">
            <button
                type="button"
                className={button}
                aria-label={t('recipes.fewerPeople')}
                disabled={value <= 1}
                onClick={() => onChange(Math.max(1, value - 1))}
            >
                −
            </button>
            <span className="min-w-24 text-center font-semibold">
                {t('recipes.people', { count: value, amount: formatAmount(value, i18n.language as Language) })}
            </span>
            <button
                type="button"
                className={button}
                aria-label={t('recipes.morePeople')}
                disabled={value >= 100}
                onClick={() => onChange(Math.min(100, value + 1))}
            >
                +
            </button>
        </div>
    );
}
