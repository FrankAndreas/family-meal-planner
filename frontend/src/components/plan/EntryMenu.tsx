import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { PlanEntry } from '../../plan';
import { BUTTON_DANGER, BUTTON_SECONDARY } from '../../ui';
import PeopleStepper from '../recipes/PeopleStepper';

interface EntryMenuProps {
    entry: PlanEntry;
    // The day is over: whether it was eaten can be changed
    past: boolean;
    onPeople: (people: number) => void;
    onEaten: (eaten: boolean) => void;
    onMove: () => void;
    onRemove: () => void;
    onClose: () => void;
}

export default function EntryMenu({ entry, past, onPeople, onEaten, onMove, onRemove, onClose }: EntryMenuProps) {
    const { t } = useTranslation();
    const title = entry.recipe ? entry.recipe.title : entry.note!;
    // Counted here, so quick taps add up before the server has answered the first one
    const [people, setPeople] = useState(entry.people);
    return (
        <div className="fixed inset-0 z-30 flex items-end justify-center bg-black/50 p-4 sm:items-center" onClick={onClose}>
            <div
                role="dialog"
                aria-label={title}
                onClick={(e) => e.stopPropagation()}
                className="glass-card w-full max-w-sm space-y-4 bg-slate-900/90 p-5"
            >
                <h2 className="text-lg">{title}</h2>
                {entry.recipe && !entry.recipe_deleted && (
                    <Link
                        to={`/rezepte/${entry.recipe.id}?personen=${people ?? ''}`}
                        className={`${BUTTON_SECONDARY} block text-center`}
                    >
                        {t('plan.openRecipe')}
                    </Link>
                )}
                {people !== null && (
                    <PeopleStepper
                        value={people}
                        onChange={(value) => {
                            setPeople(value);
                            onPeople(value);
                        }}
                    />
                )}
                {past && (
                    <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={entry.eaten} onChange={(e) => onEaten(e.target.checked)} />
                        {t('plan.eaten')}
                    </label>
                )}
                <div className="flex flex-wrap gap-2">
                    <button type="button" className={BUTTON_SECONDARY} onClick={onMove}>
                        {t('plan.move')}
                    </button>
                    <button type="button" className={BUTTON_DANGER} onClick={onRemove}>
                        {t('plan.remove')}
                    </button>
                    <button type="button" className={`${BUTTON_SECONDARY} ml-auto`} onClick={onClose}>
                        {t('plan.close')}
                    </button>
                </div>
            </div>
        </div>
    );
}
