import { useTranslation } from 'react-i18next';
import { formatAmount } from '../../amounts';
import type { Language } from '../../i18n';
import type { PlanEntry } from '../../plan';

interface EntryChipProps {
    entry: PlanEntry;
    familySize: number;
    onOpen: () => void;
}

export default function EntryChip({ entry, familySize, onOpen }: EntryChipProps) {
    const { t, i18n } = useTranslation();
    const title = entry.recipe ? entry.recipe.title : entry.note;
    const style = entry.recipe
        ? 'border-cyan-400/40 bg-cyan-400/15 text-cyan-50'
        : 'border-slate-400/30 bg-slate-400/15 italic text-slate-200';
    return (
        <button
            type="button"
            onClick={(e) => {
                e.stopPropagation();
                onOpen();
            }}
            className={`block w-full hyphens-auto rounded-md border px-1.5 py-1 text-left text-xs leading-tight [overflow-wrap:anywhere] ${style} ${
                entry.eaten ? '' : 'line-through opacity-60'
            }`}
        >
            <span className={entry.recipe_deleted ? 'line-through' : ''}>{title}</span>
            {entry.recipe_deleted && <span className="ml-1 text-slate-400">{t('plan.deleted')}</span>}
            {/* People only when they differ from the family: the usual case needs no reading */}
            {entry.people !== null && entry.people !== familySize && (
                <span className="ml-1 text-cyan-300">
                    {t('plan.peopleShort', { amount: formatAmount(entry.people, i18n.language as Language) })}
                </span>
            )}
        </button>
    );
}
