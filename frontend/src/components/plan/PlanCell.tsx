import { useDroppable } from '@dnd-kit/core';
import { useTranslation } from 'react-i18next';
import { type PlanEntry, type Slot, weekdayKey } from '../../plan';
import Draggable from './Draggable';
import EntryChip from './EntryChip';

export type CellMode = 'plan' | 'move' | 'idle';

interface PlanCellProps {
    day: string;
    slot: Slot;
    entries: PlanEntry[];
    mode: CellMode;
    past: boolean;
    familySize: number;
    onTap: () => void;
    onOpenEntry: (entry: PlanEntry) => void;
}

export default function PlanCell({ day, slot, entries, mode, past, familySize, onTap, onOpenEntry }: PlanCellProps) {
    const { t } = useTranslation();
    const place = t('plan.place', { day: t(`weekdays.${weekdayKey(day)}`), slot: t(`plan.slots.${slot}`) });
    const label = mode === 'plan' ? t('plan.planOn', { place }) : mode === 'move' ? t('plan.moveTo', { place }) : t('plan.addTo', { place });
    const target = mode !== 'idle';
    const { setNodeRef, isOver } = useDroppable({ id: `cell|${day}|${slot}` });
    return (
        <div
            ref={setNodeRef}
            data-testid={`cell-${weekdayKey(day)}-${slot}`}
            className={`flex min-h-20 flex-col gap-1 rounded-lg border p-1 ${
                isOver
                    ? 'border-fuchsia-300 bg-fuchsia-400/10'
                    : target
                      ? 'border-cyan-400/50 bg-cyan-400/5'
                      : 'border-dashed border-white/10'
            } ${past ? 'opacity-60' : ''}`}
        >
            {entries.map((entry) => (
                <Draggable key={entry.id} id={`entry|${entry.id}`}>
                    <EntryChip entry={entry} familySize={familySize} onOpen={() => onOpenEntry(entry)} />
                </Draggable>
            ))}
            {/* The free part of the cell: plan the picked recipe here, move here, or add a note */}
            <button
                type="button"
                aria-label={label}
                onClick={onTap}
                className={`min-h-6 flex-1 rounded text-xs ${
                    target ? 'text-cyan-300 hover:bg-cyan-400/10' : 'text-transparent hover:bg-white/5 hover:text-slate-500'
                }`}
            >
                {mode === 'plan' ? t('plan.planHere') : mode === 'move' ? t('plan.moveHere') : '+'}
            </button>
        </div>
    );
}
