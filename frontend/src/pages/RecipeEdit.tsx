import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import api, { errorMessage } from '../api';
import i18next from '../i18n';
import IngredientEditor from '../components/recipes/IngredientEditor';
import type { Language } from '../i18n';
import { emptyRow, ingredientsFrom, rowInvalid, rowsFrom, type Row } from '../ingredientRows';
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
}

const EMPTY: Form = { title: '', servings: '4', servingsUnit: '', prep: '', cook: '', tags: '', steps: '', notes: '' };
const minutes = (text: string) => (text.trim() === '' ? null : Math.max(0, Math.round(Number(text))));

export default function RecipeEdit() {
    const { t } = useTranslation();
    const { id } = useParams();
    const navigate = useNavigate();
    const [form, setForm] = useState<Form>(EMPTY);
    const [rows, setRows] = useState<Row[]>(() => [emptyRow()]);
    const [original, setOriginal] = useState<Recipe | null>(null);
    const [units, setUnits] = useState<string[]>([]);
    const [knownTags, setKnownTags] = useState<string[]>([]);
    const [photo, setPhoto] = useState<File | null>(null);
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
        fetchRecipe(id)
            .then((recipe) => {
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
                });
                setRows(rowsFrom(recipe.ingredients, i18next.language as Language));
            })
            .catch((err) => setError(errorMessage(err)));
    }, [id]);

    const set = (key: keyof Form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });
    const servings = Number(form.servings.replace(',', '.'));
    const invalid = !form.title.trim() || !(servings > 0 && servings <= 100) || rows.some(rowInvalid);

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
            source_url: original?.source_url ?? null,
            language: original?.language ?? null,
        };
        try {
            const target = id ?? createdId;
            const saved = target
                ? (await api.put<Recipe>(`/api/recipes/${target}`, body)).data
                : (await api.post<Recipe>('/api/recipes', body)).data;
            setCreatedId(saved.id);
            if (photo) {
                const data = new FormData();
                data.append('file', photo);
                await api.post(`/api/recipes/${saved.id}/photo`, data);
            }
            navigate(`/rezepte/${saved.id}`, { replace: true });
        } catch (err) {
            setError(errorMessage(err));
            setBusy(false);
        }
    };

    // Editing a recipe that didn't load would save an empty one over it
    if (id && !original) return error ? <p className={ERROR}>{error}</p> : <p className="text-slate-400">{t('common.loading')}</p>;

    const label = 'mb-1 block text-sm text-slate-300';
    return (
        <form onSubmit={save} className="mx-auto max-w-4xl space-y-6">
            <h1 className="text-2xl">{id ? t('recipes.editTitle') : t('recipes.newTitle')}</h1>
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
                    <label htmlFor="photo" className={label}>
                        {t('recipes.photo')}
                    </label>
                    <input id="photo" type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
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
