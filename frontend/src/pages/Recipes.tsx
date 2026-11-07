import { useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../AuthContext';
import AddRecipeMenu from '../components/recipes/AddRecipeMenu';
import RecipeSearch from '../components/recipes/RecipeSearch';
import UseUp from '../components/recipes/UseUp';
import { useRecipeSearch } from '../hooks/useRecipeSearch';
import { loadUseUp, saveUseUp, type UseUpState } from '../useUp';

const TABS = ['search', 'use_up'] as const;

export default function Recipes() {
    const { t } = useTranslation();
    const { user } = useAuth();
    const search = useRecipeSearch(user?.role === 'PARENT');
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

    return (
        <div className="space-y-5">
            <AddRecipeMenu title={t('nav.recipes')} />
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
                    <RecipeSearch search={search} />
                )}
            </div>
        </div>
    );
}
