import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api";
import CategoryPicker from "../components/recipes/CategoryPicker";
import IngredientEditor from "../components/recipes/IngredientEditor";
import PhotoPicker, {
  type PhotoChoice,
} from "../components/recipes/PhotoPicker";
import { useRecipeToEdit } from "../hooks/useRecipeToEdit";
import { isOtherLink } from "../links";
import {
  formInvalid,
  recipeInputFrom,
  type RecipeForm,
} from "../recipeForm";
import {
  fetchTags,
  fetchUnits,
  photoFromLink,
  photoPath,
  removePhoto,
  saveRecipe,
  uploadPhoto,
  type RecipeInput,
} from "../recipes";
import { BUTTON, BUTTON_SECONDARY, CARD, ERROR, FIELD, INPUT, PAGE } from "../ui";

export default function RecipeEdit() {
  const { t } = useTranslation();
  const { id } = useParams();
  const [search] = useSearchParams();
  // A draft from the inbox: prefilled, with what the AI wasn't sure about listed on top
  const draftId = id ? null : search.get("entwurf");
  const navigate = useNavigate();
  const {
    original,
    draftItem,
    form,
    setForm,
    rows,
    setRows,
    categories,
    setCategories,
    error,
    setError,
  } = useRecipeToEdit(id, draftId);
  const [units, setUnits] = useState<string[]>([]);
  const [knownTags, setKnownTags] = useState<string[]>([]);
  const [photo, setPhoto] = useState<PhotoChoice>({ kind: "keep" });
  // A new recipe saved while its photo failed: saving again updates it instead of making a second one
  const [createdId, setCreatedId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchUnits()
      .then(setUnits)
      .catch(() => {});
    fetchTags()
      .then((tags) => setKnownTags(tags.map((tag) => tag.name)))
      .catch(() => {});
  }, []);

  const set = (key: keyof RecipeForm) => (e: { target: { value: string } }) =>
    setForm({ ...form, [key]: e.target.value });
  const invalid = formInvalid(form, rows, photo);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (invalid) return;
    setBusy(true);
    setError("");
    const body: RecipeInput = {
      ...recipeInputFrom(form, rows, categories),
      // Kept as they were: an imported recipe stays imported
      source_kind: original?.source_kind ?? "manual",
      language: original?.language ?? draftItem?.draft?.language ?? null,
      ...(draftItem && !createdId ? { inbox_item_id: draftItem.id } : {}),
    };
    try {
      const target = id ?? createdId;
      const saved = await saveRecipe(target, body);
      setCreatedId(saved.id);
      if (photo.kind === "file") {
        await uploadPhoto(saved.id, photo.file);
      } else if (photo.kind === "link") {
        await photoFromLink(saved.id, photo.url.trim());
      } else if (photo.kind === "remove" && saved.photo_url) {
        await removePhoto(saved.id);
      }
      navigate(`/rezepte/${saved.id}`, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  // Editing a recipe that didn't load would save an empty one over it
  if ((id && !original) || (draftId && !draftItem))
    return error ? (
      <p role="alert" className={ERROR}>{error}</p>
    ) : (
      <p className="text-slate-400">{t("common.loading")}</p>
    );

  const label = "mb-1 block text-sm text-slate-300";
  return (
    <form onSubmit={save} className={`${PAGE} space-y-6`}>
      <h1 className="text-2xl">
        {id
          ? t("recipes.editTitle")
          : draftItem
            ? t("inbox.draftTitle")
            : t("recipes.newTitle")}
      </h1>
      {draftItem && draftItem.draft!.uncertain.length > 0 && (
        <section className="glass-card space-y-2 border-amber-300/40 p-4">
          <h2 className="text-base text-amber-100">{t("inbox.pleaseCheck")}</h2>
          <ul
            aria-label={t("inbox.pleaseCheck")}
            className="list-disc space-y-1 pl-5 text-sm text-amber-50"
          >
            {draftItem.draft!.uncertain.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </section>
      )}
      <section className={`${CARD} grid gap-4 sm:grid-cols-2`}>
        <div className="sm:col-span-2">
          <label htmlFor="title" className={label}>
            {t("recipes.title")}
          </label>
          <input
            id="title"
            className={INPUT}
            value={form.title}
            maxLength={200}
            onChange={set("title")}
          />
        </div>
        <div className="flex gap-3">
          <div>
            <label htmlFor="servings" className={label}>
              {t("recipes.servings")}
            </label>
            <input
              id="servings"
              className={`${FIELD} w-20`}
              inputMode="decimal"
              value={form.servings}
              onChange={set("servings")}
            />
          </div>
          <div className="flex-1">
            <label htmlFor="servings-unit" className={label}>
              {t("recipes.servingsUnit")}
            </label>
            <input
              id="servings-unit"
              className={INPUT}
              placeholder={t("recipes.servingsUnitPlaceholder")}
              value={form.servingsUnit}
              maxLength={30}
              onChange={set("servingsUnit")}
            />
          </div>
        </div>
        <div className="flex gap-3">
          <div>
            <label htmlFor="prep" className={label}>
              {t("recipes.prepMinutes")}
            </label>
            <input
              id="prep"
              type="number"
              min={0}
              className={`${FIELD} w-24`}
              value={form.prep}
              onChange={set("prep")}
            />
          </div>
          <div>
            <label htmlFor="cook" className={label}>
              {t("recipes.cookMinutes")}
            </label>
            <input
              id="cook"
              type="number"
              min={0}
              className={`${FIELD} w-24`}
              value={form.cook}
              onChange={set("cook")}
            />
          </div>
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="tags" className={label}>
            {t("recipes.tags")}
          </label>
          <input
            id="tags"
            list="known-tags"
            className={INPUT}
            placeholder={t("recipes.tagsPlaceholder")}
            value={form.tags}
            onChange={set("tags")}
          />
          <datalist id="known-tags">
            {knownTags.map((tag) => (
              <option key={tag} value={tag} />
            ))}
          </datalist>
        </div>
        <CategoryPicker
          value={categories}
          onChange={setCategories}
          labelClass={label}
        />
        <div className="sm:col-span-2">
          <label htmlFor="source" className={label}>
            {t("recipes.source")}
          </label>
          <input
            id="source"
            className={INPUT}
            placeholder={t("recipes.sourcePlaceholder")}
            value={form.source}
            maxLength={1000}
            onChange={set("source")}
          />
          {isOtherLink(form.source) && (
            <p className="mt-1 text-sm text-amber-200">
              {t("errors.not_a_web_link")}
            </p>
          )}
        </div>
        <div className="sm:col-span-2">
          <PhotoPicker
            current={
              original?.photo_url ??
              (draftItem?.draft?.photo ? photoPath(draftItem.draft.photo) : null)
            }
            choice={photo}
            onChange={setPhoto}
          />
        </div>
      </section>
      <section className={`${CARD} space-y-3`}>
        <h2 className="text-lg">{t("recipes.ingredients")}</h2>
        <IngredientEditor rows={rows} units={units} onChange={setRows} />
      </section>
      <section className={`${CARD} space-y-3`}>
        <label htmlFor="steps" className="block text-lg font-bold">
          {t("recipes.steps")}
        </label>
        <p className="text-xs text-slate-400">{t("recipes.stepsHint")}</p>
        <textarea
          id="steps"
          rows={8}
          className={INPUT}
          value={form.steps}
          onChange={set("steps")}
        />
        <label htmlFor="notes" className={label}>
          {t("recipes.notes")}
        </label>
        <textarea
          id="notes"
          rows={3}
          className={INPUT}
          value={form.notes}
          onChange={set("notes")}
        />
      </section>
      {error && <p role="alert" className={ERROR}>{error}</p>}
      <div className="flex gap-3">
        <button type="submit" className={BUTTON} disabled={invalid || busy}>
          {t("recipes.save")}
        </button>
        <button
          type="button"
          className={BUTTON_SECONDARY}
          onClick={() => navigate(-1)}
        >
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}
