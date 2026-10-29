import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import api, { errorMessage } from '../api';
import i18next from '../i18n';
import IngredientEditor from '../components/recipes/IngredientEditor';
import PhotoPicker, { type PhotoChoice } from '../components/recipes/PhotoPicker';
import type { Language } from '../i18n';
import { fetchItem, type InboxItemDetail } from '../inbox';
import { emptyRow, ingredientsFrom, rowInvalid, rowsFrom, type Row } from '../ingredientRows';
import { isWebLink } from '../links';
import { fetchRecipe, type Recipe, type RecipeInput } from '../recipes';
import { BUTTON, BUTTON_SECONDARY, CARD, ERROR, FIELD, INPUT } from '../ui';

interface Form {
    title: string;
    servings: string;
    servingsUnit: string;
    prep: string;
    cook: string;
    tags: string;
    steps: string;
    notes: string;
    source: string;
}

const EMPTY: Form = { title: '', servings: '4', servingsUnit: '', prep: '', cook: '', tags: '', steps: '', notes: '', source: '' };
const minutes = (text: string) => (text.trim() === '' ? null : Math.max(0, Math.round(Number(text))));

export default function RecipeEdit() {
    const { t } = useTranslation();
    const { id } = useParams();
    const [search] = useSearchParams();
    // A draft from the inbox: prefilled, with what the AI wasn't sure about listed on top
    const draftId = id ? null : search.get('entwurf');
    const [draftItem, setDraftItem] = useState<InboxItemDetail | null>(null);
    const navigate = useNavigate();
    const [form, setForm] = useState<Form>(EMPTY);
    const [rows, setRows] = useState<Row[]>(() => [emptyRow()]);
    const [original, setOriginal] = useState<Recipe | null>(null);
    const [units, setUnits] = useState<string[]>([]);
    const [knownTags, setKnownTags] = useState<string[]>([]);
    const [photo, setPhoto] = useState<PhotoChoice>({ kind: 'keep' });
    // A new recipe saved while its photo failed: saving again updates it instead of making a second one
    const [createdId, setCreatedId] = useState<number | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        api.get<string[]>('/api/units').then((r) => setUnits(r.data)).catch(() => {});
        api.get<{ name: string }[]>('/api/tags').then((r) => setKnownTags(r.data.map((tag) => tag.name))).catch(() => {});
    }, []);

    useEffect(() => {
        if (!id) return;
        // A late answer must not overwrite what someone already typed
        let current = true;
        fetchRecipe(id)
            .then((recipe) => {
                if (!current) return;
                setOriginal(recipe);
                setForm({
                    title: recipe.title,
                    servings: String(recipe.servings),
                    servingsUnit: recipe.servings_unit ?? '',
                    prep: recipe.prep_minutes === null ? '' : String(recipe.prep_minutes),
                    cook: recipe.cook_minutes === null ? '' : String(recipe.cook_minutes),
                    tags: recipe.tags.join(', '),
                    steps: recipe.steps.join('\n'),
                    notes: recipe.notes,
                    source: recipe.source_url ?? '',
                });
                setRows(rowsFrom(recipe.ingredients, i18next.language as Language));
            })
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, [id]);

    useEffect(() => {
        if (!draftId) return;
        let current = true;
        fetchItem(draftId)
            .then((item) => {
                const draft = item.draft;
                if (!draft || !current) return;
                setDraftItem(item);
                setForm({
                    title: draft.title,
                    servings: String(draft.servings),
                    servingsUnit: draft.servings_unit ?? '',
                    prep: draft.prep_minutes == null ? '' : String(draft.prep_minutes),
                    cook: draft.cook_minutes == null ? '' : String(draft.cook_minutes),
                    tags: draft.tags.join(', '),
                    steps: draft.steps.join('\n'),
                    notes: draft.notes ?? '',
                    source: draft.source_url ?? '',
                });
                setRows(
                    rowsFrom(
                        draft.ingredients.map((i, n) => ({ ...i, id: n, group: null, scaled_amount: i.amount })),
                        i18next.language as Language,
                    ),
                );
            })
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, [draftId]);

    const set = (key: keyof Form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });
    const servings = Number(form.servings.replace(',', '.'));
    const invalid =
        !form.title.trim() ||
        !(servings > 0 && servings <= 100) ||
        rows.some(rowInvalid) ||
        (photo.kind === 'link' && !isWebLink(photo.url)) ||
        (form.source.trim() !== '' && !isWebLink(form.source));

    const save = async (e: FormEvent) => {
        e.preventDefault();
        if (invalid) return;
        setBusy(true);
        setError('');
        const body: RecipeInput = {
            title: form.title.trim(),
            servings,
            servings_unit: form.servingsUnit.trim() || null,
            prep_minutes: minutes(form.prep),
            cook_minutes: minutes(form.cook),
            ingredients: ingredientsFrom(rows),
            steps: form.steps.split('\n').map((s) => s.trim()).filter(Boolean),
            tags: form.tags.split(',').map((s) => s.trim()).filter(Boolean),
            notes: form.notes,
            // Kept as they were: an imported recipe stays imported
            source_kind: original?.source_kind ?? 'manual',
            source_url: form.source.trim() || null,
            language: original?.language ?? draftItem?.draft?.language ?? null,
            ...(draftItem && !createdId ? { inbox_item_id: draftItem.id } : {}),
        };
        try {
            const target = id ?? createdId;
            const saved = target
                ? (await api.put<Recipe>(`/api/recipes/${target}`, body)).data
                : (await api.post<Recipe>('/api/recipes', body)).data;
            setCreatedId(saved.id);
            if (photo.kind === 'file') {
                const data = new FormData();
                data.append('file', photo.file);
                await api.post(`/api/recipes/${saved.id}/photo`, data);
            } else if (photo.kind === 'link') {
                await api.post(`/api/recipes/${saved.id}/photo-url`, { url: photo.url.trim() });
            } else if (photo.kind === 'remove' && saved.photo_url) {
                await api.delete(`/api/recipes/${saved.id}/photo`);
            }
            navigate(`/rezepte/${saved.id}`, { replace: true });
        } catch (err) {
            setError(errorMessage(err));
            setBusy(false);
        }
    };

    // Editing a recipe that didn't load would save an empty one over it
    if ((id && !original) || (draftId && !draftItem)) return error ? <p className={ERROR}>{error}</p> : <p className="text-slate-400">{t('common.loading')}</p>;

    const label = 'mb-1 block text-sm text-slate-300';
    return (
        <form onSubmit={save} className="mx-auto max-w-4xl space-y-6">
            <h1 className="text-2xl">{id ? t('recipes.editTitle') : draftItem ? t('inbox.draftTitle') : t('recipes.newTitle')}</h1>
            {draftItem && draftItem.draft!.uncertain.length > 0 && (
                <section className="glass-card space-y-2 border-amber-300/40 p-4">
                    <h2 className="text-base text-amber-100">{t('inbox.pleaseCheck')}</h2>
                    <ul aria-label={t('inbox.pleaseCheck')} className="list-disc space-y-1 pl-5 text-sm text-amber-50">
                        {draftItem.draft!.uncertain.map((text) => (
                            <li key={text}>{text}</li>
                        ))}
                    </ul>
                </section>
            )}
            <section className={`${CARD} grid gap-4 sm:grid-cols-2`}>
                <div className="sm:col-span-2">
                    <label htmlFor="title" className={label}>
                        {t('recipes.title')}
                    </label>
                    <input id="title" className={INPUT} value={form.title} maxLength={200} onChange={set('title')} />
                </div>
                <div className="flex gap-3">
                    <div>
                        <label htmlFor="servings" className={label}>
                            {t('recipes.servings')}
                        </label>
                        <input id="servings" className={`${FIELD} w-20`} inputMode="decimal" value={form.servings} onChange={set('servings')} />
                    </div>
                    <div className="flex-1">
                        <label htmlFor="servings-unit" className={label}>
                            {t('recipes.servingsUnit')}
                        </label>
                        <input
                            id="servings-unit"
                            className={INPUT}
                            placeholder={t('recipes.servingsUnitPlaceholder')}
                            value={form.servingsUnit}
                            maxLength={30}
                            onChange={set('servingsUnit')}
                        />
                    </div>
                </div>
                <div className="flex gap-3">
                    <div>
                        <label htmlFor="prep" className={label}>
                            {t('recipes.prepMinutes')}
                        </label>
                        <input id="prep" type="number" min={0} className={`${FIELD} w-24`} value={form.prep} onChange={set('prep')} />
                    </div>
                    <div>
                        <label htmlFor="cook" className={label}>
                            {t('recipes.cookMinutes')}
                        </label>
                        <input id="cook" type="number" min={0} className={`${FIELD} w-24`} value={form.cook} onChange={set('cook')} />
                    </div>
                </div>
                <div className="sm:col-span-2">
                    <label htmlFor="tags" className={label}>
                        {t('recipes.tags')}
                    </label>
                    <input id="tags" list="known-tags" className={INPUT} placeholder={t('recipes.tagsPlaceholder')} value={form.tags} onChange={set('tags')} />
                    <datalist id="known-tags">
                        {knownTags.map((tag) => (
                            <option key={tag} value={tag} />
                        ))}
                    </datalist>
                </div>
                <div className="sm:col-span-2">
                    <label htmlFor="source" className={label}>
                        {t('recipes.sourceUrl')}
                    </label>
                    <input
                        id="source"
                        className={INPUT}
                        inputMode="url"
                        placeholder={t('recipes.sourceUrlPlaceholder')}
                        value={form.source}
                        maxLength={1000}
                        onChange={set('source')}
                    />
                    {form.source.trim() && !isWebLink(form.source) && <p className="mt-1 text-sm text-amber-200">{t('errors.not_a_web_link')}</p>}
                </div>
                <div className="sm:col-span-2">
                    <PhotoPicker
                        current={original?.photo_url ?? (draftItem?.draft?.photo ? `/api/photos/${draftItem.draft.photo}` : null)}
                        choice={photo}
                        onChange={setPhoto}
                    />
                </div>
            </section>
            <section className={`${CARD} space-y-3`}>
                <h2 className="text-lg">{t('recipes.ingredients')}</h2>
                <IngredientEditor rows={rows} units={units} onChange={setRows} />
            </section>
            <section className={`${CARD} space-y-3`}>
                <label htmlFor="steps" className="block text-lg font-bold">
                    {t('recipes.steps')}
                </label>
                <p className="text-xs text-slate-400">{t('recipes.stepsHint')}</p>
                <textarea id="steps" rows={8} className={INPUT} value={form.steps} onChange={set('steps')} />
                <label htmlFor="notes" className={label}>
                    {t('recipes.notes')}
                </label>
                <textarea id="notes" rows={3} className={INPUT} value={form.notes} onChange={set('notes')} />
            </section>
            {error && <p className={ERROR}>{error}</p>}
            <div className="flex gap-3">
                <button type="submit" className={BUTTON} disabled={invalid || busy}>
                    {t('recipes.save')}
                </button>
                <button type="button" className={BUTTON_SECONDARY} onClick={() => navigate(-1)}>
                    {t('common.cancel')}
                </button>
            </div>
        </form>
    );
}
