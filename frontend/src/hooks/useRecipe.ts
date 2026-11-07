import { useCallback, useEffect, useState } from 'react';
import { errorMessage } from '../api';
import type { Slot } from '../plan';
import { defaultPeople, fetchEatenOn, fetchPlannedFor, fetchRecipe, type Recipe } from '../recipes';
import { fetchSettings } from '../settings';

// A recipe scaled for `people`. Without people asked for (null), first its own yield (or the family's size for
// "1 Blech"); every change of people loads it again, scaled
export function useRecipe(id: string, initialPeople: number | null) {
    const [recipe, setRecipe] = useState<Recipe | null>(null);
    const [people, setPeople] = useState<number | null>(initialPeople);
    const [error, setError] = useState('');

    useEffect(() => {
        let current = true;
        const load = async () => {
            let wanted = people;
            if (wanted === null) {
                const [plain, settings] = await Promise.all([fetchRecipe(id), fetchSettings()]);
                wanted = defaultPeople(plain, settings.family_size);
                if (!current) return;
                setPeople(wanted);
            }
            const scaled = await fetchRecipe(id, wanted);
            if (current) setRecipe(scaled);
        };
        load().catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, [id, people]);

    // Loaded again as shown (after the AI changed it)
    const reload = useCallback(async () => setRecipe(await fetchRecipe(id, people)), [id, people]);

    // A change whose answer is the recipe, unscaled: the amounts of whatever people the view shows by now are kept
    const change = useCallback(async (action: () => Promise<{ data: Recipe }>) => {
        setError('');
        try {
            const changed = (await action()).data;
            setRecipe((shown) =>
                shown ? { ...changed, ingredients: shown.ingredients, people: shown.people, factor: shown.factor } : changed,
            );
        } catch (err) {
            setError(errorMessage(err));
        }
    }, []);

    return { recipe, people, setPeople, error, setError, reload, change };
}

// The days the recipe was eaten, and where it's planned from today on (so nobody plans it twice by accident);
// `refreshPlanned` asks again after planning
export function useRecipeDates(id: string) {
    const [eatenOn, setEatenOn] = useState<string[]>([]);
    const [planned, setPlanned] = useState<{ date: string; slot: Slot }[]>([]);
    const [plannedVersion, setPlannedVersion] = useState(0);

    useEffect(() => {
        let current = true;
        fetchEatenOn(id)
            .then((days) => current && setEatenOn(days))
            .catch(() => {});
        return () => {
            current = false;
        };
    }, [id]);

    useEffect(() => {
        let current = true;
        fetchPlannedFor(id)
            .then((found) => current && setPlanned(found))
            .catch(() => {});
        return () => {
            current = false;
        };
    }, [id, plannedVersion]);

    const refreshPlanned = useCallback(() => setPlannedVersion((v) => v + 1), []);
    return { eatenOn, planned, refreshPlanned };
}
