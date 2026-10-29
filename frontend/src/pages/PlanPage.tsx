import {
    DndContext,
    DragOverlay,
    MouseSensor,
    TouchSensor,
    useSensor,
    useSensors,
    type DragEndEvent,
    type DragStartEvent,
} from '@dnd-kit/core';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import api, { errorMessage } from '../api';
import DayView from '../components/plan/DayView';
import EntryMenu from '../components/plan/EntryMenu';
import NoteDialog from '../components/plan/NoteDialog';
import SuggestionPanel from '../components/plan/SuggestionPanel';
import WeekGrid from '../components/plan/WeekGrid';
import WeekHeader from '../components/plan/WeekHeader';
import { addEntry, fetchWeek, type PlanEntry, removeEntry, type Slot, updateEntry, type Week, weekdayKey } from '../plan';
import type { RecipeSummary } from '../recipes';
import type { FamilySettings } from '../types';
import { ERROR } from '../ui';
import { useWide } from '../useWide';

export default function PlanPage() {
    const { t } = useTranslation();
    const [search, setSearch] = useSearchParams();
    const [week, setWeek] = useState<Week | null>(null);
    const [familySize, setFamilySize] = useState(4);
    // Tap-tap: a picked recipe waits for a cell; a moving entry waits for its new cell
    const [picked, setPicked] = useState<RecipeSummary | null>(null);
    const [moving, setMoving] = useState<PlanEntry | null>(null);
    const [menuEntry, setMenuEntry] = useState<PlanEntry | null>(null);
    const [noteCell, setNoteCell] = useState<{ day: string; slot: Slot } | null>(null);
    const [version, setVersion] = useState(0);
    const [dragging, setDragging] = useState<string | null>(null);
    // A small move starts a drag with the mouse; on a touch screen a short hold does, so a tap stays a tap
    // (tap-tap planning) and a swipe still scrolls the suggestions
    const sensors = useSensors(
        useSensor(MouseSensor, { activationConstraint: { distance: 8 } }),
        useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
    );
    const [error, setError] = useState('');
    const requested = search.get('woche');
    const wide = useWide();

    const reload = useCallback(async () => {
        const loaded = await fetchWeek(requested);
        setWeek(loaded);
        setVersion((v) => v + 1);
        return loaded;
    }, [requested]);

    useEffect(() => {
        let current = true;
        fetchWeek(requested)
            .then((loaded) => {
                if (!current) return;
                setWeek(loaded);
                setVersion((v) => v + 1);
            })
            .catch((err) => current && setError(errorMessage(err)));
        api.get<FamilySettings>('/api/settings')
            .then((r) => setFamilySize(r.data.family_size))
            .catch(() => {});
        return () => {
            current = false;
        };
    }, [requested]);

    useEffect(() => {
        const cancel = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                setPicked(null);
                setMoving(null);
            }
        };
        window.addEventListener('keydown', cancel);
        return () => window.removeEventListener('keydown', cancel);
    }, []);

    const run = async (action: () => Promise<unknown>) => {
        setError('');
        try {
            await action();
            const loaded = await reload();
            // Keep the open menu showing the entry as it is now
            setMenuEntry((open) => (open ? (loaded.entries.find((e) => e.id === open.id) ?? null) : null));
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    const onCell = (day: string, slot: Slot) => {
        if (moving) {
            const entry = moving;
            setMoving(null);
            run(() => updateEntry(entry.id, { date: day, slot }));
        } else if (picked) {
            // The pick stays, so the same dish can go into several days quickly
            run(() => addEntry({ date: day, slot, recipe_id: picked.id }));
        } else {
            setNoteCell({ day, slot });
        }
    };

    const dragTitle = (id: string) => {
        const [kind, key, title] = id.split('|');
        if (kind === 'recipe') return title;
        const entry = week?.entries.find((e) => e.id === Number(key));
        return entry?.recipe?.title ?? entry?.note ?? '';
    };

    const onDragStart = (event: DragStartEvent) => setDragging(String(event.active.id));
    const onDragEnd = (event: DragEndEvent) => {
        setDragging(null);
        if (!event.over) return;
        const [kind, key] = String(event.active.id).split('|');
        const [, day, slot] = String(event.over.id).split('|') as [string, string, Slot];
        if (kind === 'recipe') run(() => addEntry({ date: day, slot, recipe_id: Number(key) }));
        else run(() => updateEntry(Number(key), { date: day, slot }));
    };

    if (!week) return error ? <p className={ERROR}>{error}</p> : <p className="text-slate-400">{t('common.loading')}</p>;

    const mode = moving ? 'move' : picked ? 'plan' : 'idle';
    const place = (day: string, slot: Slot) =>
        t('plan.place', { day: t(`weekdays.${weekdayKey(day)}`), slot: t(`plan.slots.${slot}`) });

    return (
        <div className="space-y-4">
            <WeekHeader week={week} onWeek={(start) => setSearch({ woche: start })} />
            {error && <p className={ERROR}>{error}</p>}
            {moving && (
                <p className="text-sm text-cyan-300">
                    {t('plan.movingHint', { title: moving.recipe?.title ?? moving.note })}{' '}
                    <button type="button" className="underline" onClick={() => setMoving(null)}>
                        {t('common.cancel')}
                    </button>
                </p>
            )}
            {wide ? (
                <DndContext
                    sensors={sensors}
                    onDragStart={onDragStart}
                    onDragEnd={onDragEnd}
                    onDragCancel={() => setDragging(null)}
                >
                    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_17rem]">
                        <WeekGrid week={week} mode={mode} familySize={familySize} onCell={onCell} onOpenEntry={setMenuEntry} />
                        <SuggestionPanel
                            selectedId={picked?.id ?? null}
                            version={version}
                            onPick={(recipe) => {
                                setMoving(null);
                                setPicked(picked?.id === recipe.id ? null : recipe);
                            }}
                        />
                    </div>
                    <DragOverlay dropAnimation={null}>
                        {dragging && (
                            <div className="rounded-md border border-fuchsia-300 bg-slate-900/90 px-2 py-1 text-xs shadow-lg">
                                {dragTitle(dragging)}
                            </div>
                        )}
                    </DragOverlay>
                </DndContext>
            ) : (
                <DayView
                    week={week}
                    familySize={familySize}
                    version={version}
                    onOpenEntry={setMenuEntry}
                    onNote={(day, slot) => setNoteCell({ day, slot })}
                    onPlan={(day, slot, recipe) => run(() => addEntry({ date: day, slot, recipe_id: recipe.id }))}
                />
            )}
            {noteCell && (
                <NoteDialog
                    place={place(noteCell.day, noteCell.slot)}
                    onClose={() => setNoteCell(null)}
                    onAdd={(note) => {
                        const cell = noteCell;
                        setNoteCell(null);
                        run(() => addEntry({ date: cell.day, slot: cell.slot, note }));
                    }}
                />
            )}
            {menuEntry && (
                <EntryMenu
                    entry={menuEntry}
                    past={menuEntry.date < week.today}
                    onClose={() => setMenuEntry(null)}
                    onPeople={(people) => run(() => updateEntry(menuEntry.id, { people }))}
                    onEaten={(eaten) => run(() => updateEntry(menuEntry.id, { eaten }))}
                    onMove={() => {
                        setPicked(null);
                        setMoving(menuEntry);
                        setMenuEntry(null);
                    }}
                    onRemove={() => {
                        const id = menuEntry.id;
                        setMenuEntry(null);
                        run(() => removeEntry(id));
                    }}
                />
            )}
        </div>
    );
}
