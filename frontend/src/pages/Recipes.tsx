import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { fetchAiEnabled } from '../ai';
import { errorMessage } from '../api';
import PasteText from '../components/inbox/PasteText';
import ScanRecipe from '../components/inbox/ScanRecipe';
import UrlPaste from '../components/inbox/UrlPaste';
import RecipeCard from '../components/recipes/RecipeCard';
import UseUp from '../components/recipes/UseUp';
import { CATEGORIES, type Category } from '../categories';
import { useAuth } from '../AuthContext';
import { categorize, fetchRecipes, fetchTags, fetchUncategorized, type RecipeSummary } from '../recipes';
import { BUTTON, BUTTON_SECONDARY, ERROR, INPUT } from '../ui';
import { loadUseUp, saveUseUp, type UseUpState } from '../useUp';

const TABS = ['search', 'use_up'] as const;
const ADD_LABELS = {
    scan: 'recipes.scan',
    link: 'recipes.importFromLink',
    text: 'recipes.pasteText',
} as const;
// On the phone the filters are one row each that scrolls sideways; wider screens show them all
const CHIP_ROW = 'flex gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:overflow-visible sm:pb-0';

export default function Recipes() {
    const { t } = useTranslation();
    const navigate = useNavigate();
    // Getting a recipe in other than typing it: from a link, photographed, or a pasted text
    const [panel, setPanel] = useState<'link' | 'scan' | 'text' | null>(null);
    const [adding, setAdding] = useState(false);
    const addMenu = useRef<HTMLDivElement>(null);
    // The menu closes on Escape or a tap anywhere else, as menus do
    useEffect(() => {
        if (!adding) return;
        const close = (e: Event) => {
            if (e instanceof globalThis.KeyboardEvent ? e.key === 'Escape' : !addMenu.current?.contains(e.target as Node)) setAdding(false);
        };
        document.addEventListener('pointerdown', close);
        document.addEventListener('keydown', close);
        return () => {
            document.removeEventListener('pointerdown', close);
            document.removeEventListener('keydown', close);
        };
    }, [adding]);
    const open = (which: 'link' | 'scan' | 'text') => {
        setPanel(which);
        setAdding(false);
    };
    const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);
    const [tags, setTags] = useState<{ name: string; count: number }[]>([]);
    const [q, setQ] = useState('');
    const [tag, setTag] = useState('');
    const [category, setCategory] = useState<Category | 'none' | ''>('');
    const { user } = useAuth();
    // Parents, with the AI on, can have it sort the recipes without a category ("Ohne Kategorie")
    const [aiOn, setAiOn] = useState(false);
    const [unsorted, setUnsorted] = useState(0);
    const [sorting, setSorting] = useState<{ done: number; total: number } | null>(null);
    const [reloads, setReloads] = useState(0);
    const [onlyMine, setOnlyMine] = useState(false);
    const [error, setError] = useState('');
    // Search, or "Was habe ich?"; kept on this device with what was typed there
    const [useUp, setUseUp] = useState<UseUpState>(loadUseUp);
    const changeUseUp = (next: UseUpState) => {
        setUseUp(next);
        saveUseUp(next);
    };
    // Arrow keys move between the two tabs, as in any tab list
    const onTabKey = (e: KeyboardEvent<HTMLDivElement>) => {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        e.preventDefault();
        const next = TABS[(TABS.indexOf(useUp.tab) + 1) % TABS.length];
        changeUseUp({ ...useUp, tab: next });
        document.getElementById(`recipes-tab-${next}`)?.focus();
    };

    useEffect(() => {
        fetchTags()
            .then(setTags)
            .catch(() => {});
    }, []);

    useEffect(() => {
        if (user?.role !== 'PARENT') return;
        fetchAiEnabled()
            .then(setAiOn)
            .catch(() => {});
    }, [user?.role]);

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

    const chip = (active: boolean) =>
        `shrink-0 whitespace-nowrap rounded-full border px-3 py-1 text-sm ${
            active ? 'border-cyan-400 bg-cyan-400/15 text-white' : 'border-white/10 text-slate-300 hover:bg-white/5'
        }`;

    return (
        <div className="space-y-5">
            {/* One button for the ways of adding a recipe, so the phone starts with recipes (UX review) */}
            <div className="flex items-center gap-3">
                <h1 className="mr-auto text-2xl">{t('nav.recipes')}</h1>
                <div ref={addMenu} className="relative">
                    <button
                        type="button"
                        className={BUTTON}
                        aria-expanded={adding}
                        aria-controls={adding ? 'add-recipe' : undefined}
                        onClick={() => setAdding(!adding)}
                    >
                        {t('recipes.add')}
                    </button>
                    {adding && (
                        <div id="add-recipe" className="glass-card absolute right-0 top-full z-20 mt-2 flex w-64 flex-col gap-2 p-3">
                            <Link to="/rezepte/neu" className={BUTTON}>
                                {t('recipes.new')}
                            </Link>
                            {(['scan', 'link', 'text'] as const).map((which) => (
                                <button key={which} type="button" className={BUTTON_SECONDARY} onClick={() => open(which)}>
                                    {t(ADD_LABELS[which])}
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>
            {panel && (
                <div className="flex justify-end">
                    <button type="button" className="text-sm text-slate-400 hover:text-white" onClick={() => setPanel(null)}>
                        {t('recipes.closePanel')}
                    </button>
                </div>
            )}
            {/* Same as in the inbox: the draft shows up there (a parent's link is read at once) */}
            {panel === 'link' && <UrlPaste onAdded={() => navigate('/posteingang')} />}
            {panel === 'scan' && <ScanRecipe onDone={() => navigate('/posteingang')} />}
            {panel === 'text' && <PasteText onAdded={() => navigate('/posteingang')} />}
            <div role="tablist" className="flex gap-2" onKeyDown={onTabKey}>
                {TABS.map((key) => (
                    <button
                        key={key}
                        id={`recipes-tab-${key}`}
                        type="button"
                        role="tab"
                        aria-selected={useUp.tab === key}
                        aria-controls="recipes-panel"
                        tabIndex={useUp.tab === key ? 0 : -1}
                        onClick={() => changeUseUp({ ...useUp, tab: key })}
                        className={`rounded-lg px-3 py-1.5 text-sm ${
                            useUp.tab === key ? 'bg-fuchsia-400/20 text-fuchsia-100' : 'text-slate-400 hover:bg-white/5'
                        }`}
                    >
                        {t(`useUp.tabs.${key}`)}
                    </button>
                ))}
            </div>
            <div role="tabpanel" id="recipes-panel" aria-labelledby={`recipes-tab-${useUp.tab}`} className="space-y-5">
                {useUp.tab === 'use_up' ? (
                    <UseUp have={useUp.have} mode={useUp.mode} onChange={(have, mode) => changeUseUp({ ...useUp, have, mode })} />
                ) : (
                    <>
                        <div className="flex flex-wrap items-center gap-3">
                            <input
                                className={`${INPUT} max-w-sm`}
                                type="search"
                                aria-label={t('recipes.search')}
                                placeholder={t('recipes.searchPlaceholder')}
                                value={q}
                                onChange={(e) => setQ(e.target.value)}
                            />
                            <label className="flex items-center gap-2 text-sm text-slate-300">
                                <input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} />
                                {t('recipes.onlyMyFavorites')}
                            </label>
                        </div>
                        <div className={CHIP_ROW} role="group" aria-label={t('recipes.filterCategory')}>
                            <button
                                type="button"
                                className={chip(category === '')}
                                aria-pressed={category === ''}
                                onClick={() => setCategory('')}
                            >
                                {t('recipes.allCategories')}
                            </button>
                            {[...CATEGORIES, 'none' as const].map((key) => (
                                <button
                                    key={key}
                                    type="button"
                                    className={chip(category === key)}
                                    aria-pressed={category === key}
                                    onClick={() => setCategory(category === key ? '' : key)}
                                >
                                    {key === 'none' ? t('recipes.noCategory') : t(`recipes.category.${key}`)}
                                </button>
                            ))}
                        </div>
                        {aiOn && category === 'none' && (unsorted > 0 || sorting) && (
                            <div className="flex items-center gap-3">
                                <button type="button" className={BUTTON_SECONDARY} disabled={sorting !== null} onClick={sortWithAi}>
                                    {t('recipes.categorizeAll', { count: unsorted })}
                                </button>
                                {sorting && (
                                    <span role="status" className="text-sm text-slate-300">
                                        {t('recipes.categorizeProgress', sorting)}
                                    </span>
                                )}
                            </div>
                        )}
                        {tags.length > 0 && (
                            <div className={CHIP_ROW}>
                                <button type="button" className={chip(tag === '')} onClick={() => setTag('')}>
                                    {t('recipes.allTags')}
                                </button>
                                {tags.map((item) => (
                                    <button
                                        key={item.name}
                                        type="button"
                                        className={chip(tag === item.name)}
                                        onClick={() => setTag(tag === item.name ? '' : item.name)}
                                    >
                                        {item.name} <span className="text-slate-500">{item.count}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                        {error && <p className={ERROR}>{error}</p>}
                        {recipes && recipes.length === 0 && <p className="text-slate-400">{t('recipes.none')}</p>}
                        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                            {recipes?.map((recipe) => (
                                <RecipeCard key={recipe.id} recipe={recipe} />
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
