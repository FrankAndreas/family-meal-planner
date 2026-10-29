import { format, parseISO } from 'date-fns';
import { de, enUS } from 'date-fns/locale';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { addDays, type Week } from '../../plan';

interface WeekHeaderProps {
    week: Week;
    onWeek: (start: string) => void;
}

export default function WeekHeader({ week, onWeek }: WeekHeaderProps) {
    const { t, i18n } = useTranslation();
    const locale = i18n.language === 'de' ? de : enUS;
    const label = (day: string) => format(parseISO(day), 'EEEEEE d.M.', { locale });
    const arrow = 'h-10 w-10 rounded-full border border-white/15 text-lg hover:bg-white/10';
    return (
        <div className="space-y-3">
            {week.previous_needs_closing && (
                <div className="glass-card flex flex-wrap items-center gap-3 border-amber-300/30 p-3">
                    <span className="mr-auto text-sm text-amber-100">{t('plan.closePrevious')}</span>
                    <Link to={`/woche-abschliessen?start=${addDays(week.start, -7)}`} className="btn-primary text-sm">
                        {t('plan.closeWeek')}
                    </Link>
                </div>
            )}
            <div className="flex flex-wrap items-center gap-3">
                <button type="button" className={arrow} aria-label={t('plan.previousWeek')} onClick={() => onWeek(addDays(week.start, -7))}>
                    ‹
                </button>
                <h1 className="text-xl" data-testid="week-range" data-start={week.start}>
                    {label(week.start)} – {label(week.end)}
                </h1>
                <button type="button" className={arrow} aria-label={t('plan.nextWeek')} onClick={() => onWeek(addDays(week.start, 7))}>
                    ›
                </button>
                <span className="ml-auto rounded-full bg-emerald-400/15 px-3 py-1 text-sm text-emerald-200">
                    {t('plan.counter', { planned: week.planned_slots, total: week.total_slots })}
                </span>
            </div>
        </div>
    );
}
