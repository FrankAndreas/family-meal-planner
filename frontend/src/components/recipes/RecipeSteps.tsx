import { useTranslation } from 'react-i18next';
import { CARD } from '../../ui';

// A recipe's steps, numbered, and its notes below
export default function RecipeSteps({ steps, notes }: { steps: string[]; notes: string }) {
    const { t } = useTranslation();
    return (
        <section className={`${CARD} space-y-3`}>
            <h2 className="text-lg">{t('recipes.steps')}</h2>
            <ol aria-label={t('recipes.steps')} className="list-decimal space-y-3 pl-5">
                {steps.map((step, n) => (
                    <li key={n} className="leading-relaxed">
                        {step}
                    </li>
                ))}
            </ol>
            {notes && <p className="whitespace-pre-line text-slate-300">{notes}</p>}
        </section>
    );
}
