import { format, parseISO } from 'date-fns';
import { de, enUS } from 'date-fns/locale';
import { useTranslation } from 'react-i18next';
import { type PlanEntry, SLOTS, type Slot, type Week } from '../../plan';
import PlanCell, { type CellMode } from './PlanCell';

interface WeekGridProps {
    week: Week;
    mode: CellMode;
    familySize: number;
    onCell: (day: string, slot: Slot) => void;
    onOpenEntry: (entry: PlanEntry) => void;
}

export default function WeekGrid({ week, mode, familySize, onCell, onOpenEntry }: WeekGridProps) {
    const { t, i18n } = useTranslation();
    const locale = i18n.language === 'de' ? de : enUS;
    return (
        <div className="glass-card overflow-x-auto p-3">
            <div className="grid min-w-[44rem] grid-cols-[5.5rem_repeat(7,minmax(0,1fr))] gap-1.5">
                <div />
                {week.days.map((day) => (
                    <div
                        key={day}
                        className={`rounded-lg py-1 text-center ${day === week.today ? 'bg-cyan-400/15 text-cyan-100' : ''}`}
                    >
                        <div className="text-sm font-semibold">{format(parseISO(day), 'EEEEEE', { locale })}</div>
                        <div className="text-xs text-slate-400">{format(parseISO(day), 'd.M.')}</div>
                    </div>
                ))}
                {SLOTS.map((slot) => [
                    <div key={slot} className="flex items-center text-xs font-medium text-slate-400">
                        {t(`plan.slots.${slot}`)}
                    </div>,
                    ...week.days.map((day) => (
                        <PlanCell
                            key={`${day}-${slot}`}
                            day={day}
                            slot={slot}
                            entries={week.entries.filter((e) => e.date === day && e.slot === slot)}
                            mode={mode}
                            past={day < week.today}
                            familySize={familySize}
                            onTap={() => onCell(day, slot)}
                            onOpenEntry={onOpenEntry}
                        />
                    )),
                ])}
            </div>
        </div>
    );
}
