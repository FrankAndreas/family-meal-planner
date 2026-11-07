import { useEffect, useState } from 'react';
import { fetchAiEnabled } from '../ai';
import { errorMessage } from '../api';
import type { Category } from '../categories';
import { categorize, fetchRecipes, fetchTags, fetchUncategorized, type RecipeSummary } from '../recipes';

export interface SearchFilter {
    q: string;
    tag: string;
    category: Category | 'none' | '';
    onlyMine: boolean;
}

// The recipe list for a filter, the tags to filter by, and (parents, with the AI on) sorting the recipes without a
// category with the AI. Kept by the page, so switching to "Was habe ich?" and back keeps the search
export function useRecipeSearch(isParent: boolean) {
    const [filter, setFilter] = useState<SearchFilter>({ q: '', tag: '', category: '', onlyMine: false });
    const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);
    const [tags, setTags] = useState<{ name: string; count: number }[]>([]);
    const [aiOn, setAiOn] = useState(false);
    const [unsorted, setUnsorted] = useState(0);
    const [sorting, setSorting] = useState<{ done: number; total: number } | null>(null);
    const [reloads, setReloads] = useState(0);
    const [error, setError] = useState('');
    const { q, tag, category, onlyMine } = filter;

    useEffect(() => {
        fetchTags()
            .then(setTags)
            .catch(() => {});
    }, []);

    useEffect(() => {
        if (!isParent) return;
        fetchAiEnabled()
            .then(setAiOn)
            .catch(() => {});
    }, [isParent]);

    useEffect(() => {
        if (!aiOn || category !== 'none') return;
        let current = true;
        fetchUncategorized()
            .then((count) => current && setUnsorted(count))
            .catch(() => {});
        return () => {
            current = false;
        };
    }, [aiOn, category, reloads]);

    useEffect(() => {
        let current = true;
        // A short pause while typing, so not every letter asks the server
        const timer = setTimeout(() => {
            fetchRecipes({ q, tag, category, favorites: onlyMine ? 'mine' : '' })
                .then((found) => current && setRecipes(found))
                .catch((err) => current && setError(errorMessage(err)));
        }, 200);
        return () => {
            current = false;
            clearTimeout(timer);
        };
    }, [q, tag, category, onlyMine, reloads]);

    const sortWithAi = async () => {
        setError('');
        const total = unsorted;
        setSorting({ done: 0, total });
        try {
            let left = total;
            for (;;) {
                const result = await categorize();
                setSorting({ done: Math.max(0, total - result.remaining), total });
                // Done, or nothing moved (recipes being added as fast): stop instead of asking forever
                if (result.remaining === 0 || result.remaining >= left) break;
                left = result.remaining;
            }
        } catch (err) {
            // What was sorted so far stays sorted
            setError(errorMessage(err));
        } finally {
            setSorting(null);
            setReloads((n) => n + 1);
        }
    };

    const change = (fields: Partial<SearchFilter>) => setFilter((now) => ({ ...now, ...fields }));
    return { filter, change, recipes, tags, error, aiOn, unsorted, sorting, sortWithAi };
}
