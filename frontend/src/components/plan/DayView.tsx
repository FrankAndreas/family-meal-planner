import { format, parseISO } from 'date-fns';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { type PlanEntry, SLOTS, type Slot, type Week, weekdayKey } from '../../plan';
import type { RecipeSummary } from '../../recipes';
import { BUTTON_SECONDARY, CARD } from '../../ui';
import EntryChip from './EntryChip';
import SuggestionPanel from './SuggestionPanel';

interface DayViewProps {
    week: Week;
    familySize: number;
    version: number;
    onPlan: (day: string, slot: Slot, recipe: RecipeSummary) => void;
    onNote: (day: string, slot: Slot) => void;
    onOpenEntry: (entry: PlanEntry) => void;
}

// Phones: one day at a time; "+" on a slot opens the suggestions as a sheet from the bottom
export default function DayView({ week, familySize, version, onPlan, onNote, onOpenEntry }: DayViewProps) {
    const { t } = useTranslation();
    const [day, setDay] = useState(week.days.includes(week.today) ? week.today : week.days[0]);
    const [adding, setAdding] = useState<Slot | null>(null);
    const shown = week.days.includes(day) ? day : week.days[0];
    const place = (slot: Slot) => t('plan.place', { day: t(`weekdays.${weekdayKey(shown)}`), slot: t(`plan.slots.${slot}`) });

    return (
        <div className="space-y-3">
            <div role="tablist" className="grid grid-cols-7 gap-1">
                {week.days.map((d) => (
                    <button
                        key={d}
                        type="button"
                        role="tab"
                        aria-selected={d === shown}
                        aria-label={t(`weekdays.${weekdayKey(d)}`)}
                        onClick={() => setDay(d)}
                        className={`rounded-lg py-1.5 text-center ${
                            d === shown ? 'bg-cyan-400/20 text-cyan-100' : d === week.today ? 'text-cyan-300' : 'text-slate-400'
                        }`}
                    >
                        <div className="text-sm font-semibold">{t(`weekdays.${weekdayKey(d)}`).slice(0, 2)}</div>
                        <div className="text-xs">{format(parseISO(d), 'd.M.')}</div>
                    </button>
                ))}
            </div>
            {SLOTS.map((slot) => (
                <section key={slot} data-testid={`day-${slot}`} className={`${CARD} space-y-2 p-3`}>
                    <h2 className="text-sm text-slate-400">{t(`plan.slots.${slot}`)}</h2>
                    {week.entries
                        .filter((e) => e.date === shown && e.slot === slot)
                        .map((entry) => (
                            <EntryChip key={entry.id} entry={entry} familySize={familySize} onOpen={() => onOpenEntry(entry)} />
                        ))}
                    <button
                        type="button"
                        aria-label={t('plan.addTo', { place: place(slot) })}
                        onClick={() => setAdding(slot)}
                        className="w-full rounded-md border border-dashed border-white/15 py-1.5 text-sm text-slate-400"
                    >
                        {t('plan.add')}
                    </button>
                </section>
            ))}
            {adding && (
                <div className="fixed inset-0 z-30 flex items-end bg-black/50" onClick={() => setAdding(null)}>
                    <div
                        role="dialog"
                        aria-label={place(adding)}
                        onClick={(e) => e.stopPropagation()}
                        className="flex h-[80vh] w-full flex-col gap-2 rounded-t-2xl bg-slate-900 p-3"
                    >
                        <div className="flex items-center gap-2">
                            <h2 className="mr-auto text-base">{place(adding)}</h2>
                            <button
                                type="button"
                                className={BUTTON_SECONDARY}
                                onClick={() => {
                                    const slot = adding;
                                    setAdding(null);
                                    onNote(shown, slot);
                                }}
                            >
                                {t('plan.addNote')}
                            </button>
                        </div>
                        <div className="min-h-0 flex-1">
                            <SuggestionPanel
                                selectedId={null}
                                version={version}
                                onPick={(recipe) => {
                                    const slot = adding;
                                    setAdding(null);
                                    onPlan(shown, slot, recipe);
                                }}
                            />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
