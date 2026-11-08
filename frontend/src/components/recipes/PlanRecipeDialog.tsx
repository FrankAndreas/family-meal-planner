import { format, parseISO } from 'date-fns';
import { de, enUS } from 'date-fns/locale';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { errorMessage } from '../../api';
import { addDays, addEntry, fetchWeek, type PlanEntry, SLOTS, type Slot, type Week, weekdayKey } from '../../plan';
import { BUTTON, BUTTON_SECONDARY, ERROR } from '../../ui';
import Modal from '../Modal';
import { useWide } from '../../useWide';
import PeopleStepper from './PeopleStepper';

interface PlanRecipeDialogProps {
    recipeId: number;
    title: string;
    // Starts at the people the recipe view shows
    people: number;
    onPlanned: (entry: PlanEntry) => void;
    onClose: () => void;
}

type Place = { day: string; slot: Slot };

const ARROW = 'h-9 w-9 rounded-full border border-white/15 text-lg hover:bg-white/10';
const CHIP = 'rounded-full border px-3 py-1.5 text-sm disabled:opacity-30';
const chipColor = (on: boolean) => (on ? 'border-cyan-400 bg-cyan-400/20 text-cyan-100' : 'border-white/15 hover:bg-white/10');

// Plans one recipe from its own page: the week as a small grid on the big screen, day and meal buttons on the phone
export default function PlanRecipeDialog({ recipeId, title, people: initialPeople, onPlanned, onClose }: PlanRecipeDialogProps) {
    const { t, i18n } = useTranslation();
    const locale = i18n.language === 'de' ? de : enUS;
    const wide = useWide();
    // null: the week the planner opens on (from Friday on, the coming one)
    const [start, setStart] = useState<string | null>(null);
    const [week, setWeek] = useState<Week | null>(null);
    const [day, setDay] = useState<string | null>(null);
    const [slot, setSlot] = useState<Slot | null>(null);
    const picked: Place | null = day && slot ? { day, slot } : null;
    const pick = (place: Place) => {
        setDay(place.day);
        setSlot(place.slot);
    };
    const [people, setPeople] = useState(initialPeople);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    // A week is on its way: the one shown can't be picked from meanwhile
    const [loading, setLoading] = useState(true);
    const heading = useRef<HTMLHeadingElement>(null);

    useEffect(() => {
        let current = true;
        fetchWeek(start)
            .then((loaded) => {
                if (!current) return;
                setWeek(loaded);
                setError('');
                setLoading(false);
            })
            .catch((err) => {
                if (!current) return;
                setError(errorMessage(err));
                setLoading(false);
            });
        return () => {
            current = false;
        };
    }, [start]);

    // Focus into the dialog once, when it opens
    useEffect(() => heading.current?.focus(), []);

    const toWeek = (days: number) => {
        if (!week) return;
        setDay(null);
        setLoading(true);
        // From the week asked for last, so two quick taps move two weeks
        setStart(addDays(start ?? week.start, days));
    };
    const dayName = (day: string) => `${t(`weekdays.${weekdayKey(day)}`)} ${format(parseISO(day), 'd.M.')}`;
    const place = ({ day, slot }: Place) => t('plan.place', { day: dayName(day), slot: t(`plan.slots.${slot}`) });
    const entriesAt = (day: string, slot: Slot) => week?.entries.filter((e) => e.date === day && e.slot === slot) ?? [];
    const label = (entry: PlanEntry) => entry.recipe?.title ?? entry.note ?? '';
    // Days already gone can't be picked; today still can
    const past = (day: string) => !!week && day < week.today;
    const takenText = (entries: PlanEntry[]) =>
        entries.length ? t('plan.slotTaken', { titles: entries.map(label).join(', ') }) : t('plan.slotFree');

    const save = async () => {
        if (!picked) return;
        setSaving(true);
        setError('');
        try {
            onPlanned(await addEntry({ date: picked.day, slot: picked.slot, recipe_id: recipeId, people }));
        } catch (err) {
            setError(errorMessage(err));
            setSaving(false);
        }
    };

    const weekLabel = (day: string) => format(parseISO(day), 'EEEEEE d.M.', { locale });
    const taken = picked ? entriesAt(picked.day, picked.slot) : [];

    return (
        <Modal
            label={t('plan.planRecipeTitle', { title })}
            onClose={onClose}
            overlayClassName="fixed inset-0 z-30 flex items-end justify-center bg-black/50 sm:items-center sm:p-4"
            className="glass-card max-h-[90vh] w-full max-w-3xl space-y-4 overflow-y-auto rounded-b-none bg-slate-900/95 p-4 sm:rounded-b-2xl sm:p-5"
        >
            <h2 ref={heading} tabIndex={-1} className="text-lg focus:outline-none">{t('plan.planRecipeTitle', { title })}</h2>
            {week && (
                <div className="flex items-center justify-between gap-2">
                    <button type="button" className={ARROW} aria-label={t('plan.previousWeek')} onClick={() => toWeek(-7)}>
                        ‹
                    </button>
                    <span className="font-semibold" data-testid="plan-dialog-week">
                        {weekLabel(week.start)} – {weekLabel(week.end)}
                    </span>
                    <button type="button" className={ARROW} aria-label={t('plan.nextWeek')} onClick={() => toWeek(7)}>
                        ›
                    </button>
                </div>
            )}
            {!week ? (
                !error && <p className="text-slate-400">{t('common.loading')}</p>
            ) : wide ? (
                <table className="w-full table-fixed border-separate border-spacing-1 text-xs">
                    <thead>
                        <tr>
                            <th className="w-24" />
                            {week.days.map((day) => (
                                <th key={day} className={`font-medium ${day === week.today ? 'text-cyan-300' : 'text-slate-400'}`}>
                                    <div>{t(`weekdays.${weekdayKey(day)}`).slice(0, 2)}</div>
                                    <div className="font-normal">{format(parseISO(day), 'd.M.')}</div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {SLOTS.map((slot) => (
                            <tr key={slot}>
                                <th className="text-left font-medium text-slate-400">{t(`plan.slots.${slot}`)}</th>
                                {week.days.map((day) => {
                                    const here = entriesAt(day, slot);
                                    const on = picked?.day === day && picked.slot === slot;
                                    return (
                                        <td key={day} className="p-0">
                                            <button
                                                type="button"
                                                aria-label={`${place({ day, slot })}: ${takenText(here)}`}
                                                aria-pressed={on}
                                                disabled={past(day) || loading}
                                                onClick={() => pick({ day, slot })}
                                                className={`flex h-12 w-full flex-col items-center justify-center overflow-hidden rounded-md px-1 disabled:opacity-30 ${
                                                    on
                                                        ? 'bg-cyan-500 font-semibold text-white'
                                                        : here.length
                                                          ? 'bg-white/10 text-slate-200 hover:bg-white/15'
                                                          : 'bg-white/5 text-slate-400 hover:bg-white/10'
                                                }`}
                                            >
                                                {on ? (
                                                    '✓'
                                                ) : here.length ? (
                                                    here.map((entry) => (
                                                        <span key={entry.id} className="w-full truncate">
                                                            {label(entry)}
                                                        </span>
                                                    ))
                                                ) : (
                                                    '+'
                                                )}
                                            </button>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            ) : (
                <div className="space-y-3">
                    <div>
                        <h3 className="mb-1 text-sm text-slate-400">{t('plan.pickDay')}</h3>
                        <div className="grid grid-cols-7 gap-1">
                            {week.days.map((d) => (
                                <button
                                    key={d}
                                    type="button"
                                    aria-label={dayName(d)}
                                    aria-pressed={day === d}
                                    disabled={past(d) || loading}
                                    onClick={() => setDay(d)}
                                    className={`rounded-lg border py-1.5 text-center disabled:opacity-30 ${chipColor(day === d)}`}
                                >
                                    <div className="text-sm font-semibold">{t(`weekdays.${weekdayKey(d)}`).slice(0, 2)}</div>
                                    <div className="text-xs">{format(parseISO(d), 'd.M.')}</div>
                                </button>
                            ))}
                        </div>
                    </div>
                    <div>
                        <h3 className="mb-1 text-sm text-slate-400">{t('plan.pickMeal')}</h3>
                        <div className="flex flex-wrap gap-2">
                            {SLOTS.map((s) => (
                                <button
                                    key={s}
                                    type="button"
                                    aria-pressed={slot === s}
                                    onClick={() => setSlot(s)}
                                    className={`${CHIP} ${chipColor(slot === s)}`}
                                >
                                    {t(`plan.slots.${s}`)}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}
            {picked && (
                <p className="text-sm text-slate-400" data-testid="plan-dialog-taken">
                    {takenText(taken)}
                </p>
            )}
            <PeopleStepper value={people} onChange={setPeople} />
            {error && <p role="alert" className={ERROR}>{error}</p>}
            <div className="flex flex-wrap gap-2">
                <button type="button" className={BUTTON} disabled={!picked || saving || loading} onClick={save}>
                    {picked ? t('plan.planOn', { place: place(picked) }) : t('plan.pickPlace')}
                </button>
                <button type="button" className={BUTTON_SECONDARY} onClick={onClose}>
                    {t('common.cancel')}
                </button>
            </div>
        </Modal>
    );
}
