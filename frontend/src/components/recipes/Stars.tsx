import { useTranslation } from 'react-i18next';

interface StarsProps {
    value: number | null;
    // Without onChange the stars are only shown; tapping the current value again removes the rating
    onChange?: (stars: number | null) => void;
    size?: 'sm' | 'lg';
}

export default function Stars({ value, onChange, size = 'sm' }: StarsProps) {
    const { t } = useTranslation();
    const filled = Math.round(value ?? 0);
    const text = size === 'lg' ? 'text-3xl' : 'text-sm';
    if (!onChange) {
        return (
            <span className={`${text} tracking-tight text-amber-300`} aria-label={t('recipes.ratingShown', { value: value ?? 0 })}>
                {[1, 2, 3, 4, 5].map((n) => (
                    <span key={n} className={n <= filled ? '' : 'text-slate-600'}>
                        ★
                    </span>
                ))}
            </span>
        );
    }
    return (
        <span className="inline-flex">
            {[1, 2, 3, 4, 5].map((n) => (
                <button
                    key={n}
                    type="button"
                    aria-label={t('recipes.rate', { count: n })}
                    onClick={() => onChange(n === value ? null : n)}
                    className={`${text} px-1 ${n <= filled ? 'text-amber-300' : 'text-slate-600'} hover:text-amber-200`}
                >
                    ★
                </button>
            ))}
        </span>
    );
}
