import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { BUTTON, BUTTON_SECONDARY } from '../../ui';
import PasteText from '../inbox/PasteText';
import ScanRecipe from '../inbox/ScanRecipe';
import UrlPaste from '../inbox/UrlPaste';

const ADD_LABELS = {
    scan: 'recipes.scan',
    link: 'recipes.importFromLink',
    text: 'recipes.pasteText',
} as const;

// One button for the ways of adding a recipe, so the phone starts with recipes (UX review): typing it, or getting it
// in from a link, a photo or a pasted text (shown below the heading, `title`)
export default function AddRecipeMenu({ title }: { title: string }) {
    const { t } = useTranslation();
    const navigate = useNavigate();
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

    return (
        <>
            <div className="flex items-center gap-3">
                <h1 className="mr-auto text-2xl">{title}</h1>
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
        </>
    );
}
