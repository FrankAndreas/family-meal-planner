import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { fetchAiEnabled } from "../ai";
import { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import IngredientList from "../components/recipes/IngredientList";
import PlanRecipeDialog from "../components/recipes/PlanRecipeDialog";
import { RecipeThumb } from "../components/recipes/RecipeCard";
import RecipeFacts from "../components/recipes/RecipeFacts";
import RecipeSteps from "../components/recipes/RecipeSteps";
import Stars from "../components/recipes/Stars";
import { usePlaceText } from "../hooks/usePlaceText";
import { useRecipe, useRecipeDates } from "../hooks/useRecipe";
import type { PlanEntry } from "../plan";
import {
  categorize,
  deleteRecipe,
  favoriteRecipe,
  rateRecipe,
  translateRecipe,
} from "../recipes";
import { withOriginal } from "../recipeView";
import { BUTTON, BUTTON_SECONDARY, CARD, ERROR, PAGE } from "../ui";

export default function RecipeView() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const { user } = useAuth();
  const { recipe, people, setPeople, error, setError, reload, change } =
    useRecipe(id!, Number(search.get("personen")) || null);
  const { eatenOn, planned, refreshPlanned } = useRecipeDates(id!);
  const place = usePlaceText();
  const [showOriginal, setShowOriginal] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [aiOn, setAiOn] = useState(false);
  const [categorizing, setCategorizing] = useState(false);
  const [planning, setPlanning] = useState(false);
  const [justPlanned, setJustPlanned] = useState<PlanEntry | null>(null);
  const planButton = useRef<HTMLButtonElement>(null);

  const closePlanning = () => {
    setPlanning(false);
    planButton.current?.focus();
  };

  const remove = async () => {
    if (!confirm(t("recipes.confirmDelete", { title: recipe!.title }))) return;
    try {
      await deleteRecipe(recipe!.id);
      navigate("/rezepte");
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  useEffect(() => {
    if (user?.role !== "PARENT") return;
    fetchAiEnabled()
      .then(setAiOn)
      .catch(() => {});
  }, [user?.role]);

  const suggestCategories = async () => {
    setCategorizing(true);
    setError("");
    try {
      await categorize(recipe!.id);
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setCategorizing(false);
    }
  };

  const translate = async () => {
    setTranslating(true);
    setError("");
    try {
      await translateRecipe(recipe!.id);
      await reload();
      setShowOriginal(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setTranslating(false);
    }
  };

  if (!recipe)
    return error ? (
      <p className={ERROR}>{error}</p>
    ) : (
      <p className="text-slate-400">{t("common.loading")}</p>
    );

  const shown = showOriginal ? withOriginal(recipe) : recipe;
  // Not in the family's language (or unknown, from outside; the backend knows DEFAULT_LANGUAGE): parents can have
  // it translated
  const canTranslate = user?.role === "PARENT" && !recipe.deleted && recipe.translate_into !== null;
  const canCategorize = user?.role === "PARENT" && aiOn && !recipe.deleted && recipe.categories.length === 0;

  return (
    <article className={`${PAGE} space-y-6`}>
      {recipe.deleted && <p className={ERROR}>{t("recipes.deletedBanner")}</p>}
      <div className={`${CARD} grid gap-5 md:grid-cols-[16rem_1fr]`}>
        <RecipeThumb
          recipe={recipe}
          className="h-56 w-full rounded-xl md:h-64"
        />
        <div className="space-y-3">
          <h1 className="text-3xl">{shown.title}</h1>
          <RecipeFacts recipe={recipe} eatenOn={eatenOn} planned={planned} />
          {!recipe.deleted && (
            <div className="flex flex-wrap items-center gap-3">
              <Stars
                value={recipe.my_rating}
                size="lg"
                onChange={(stars) =>
                  change(() => rateRecipe(recipe.id, stars))
                }
              />
              <button
                type="button"
                aria-pressed={recipe.my_favorite}
                aria-label={t("recipes.favorite")}
                onClick={() =>
                  change(() => favoriteRecipe(recipe.id, !recipe.my_favorite))
                }
                className={`text-3xl ${recipe.my_favorite ? "text-fuchsia-300" : "text-slate-600 hover:text-fuchsia-200"}`}
              >
                ♥
              </button>
            </div>
          )}
          {recipe.ratings.length > 0 && (
            <ul
              className="flex flex-wrap gap-x-4 text-sm text-slate-300"
              aria-label={t("recipes.ratingsBy")}
            >
              {recipe.ratings.map((r) => (
                <li key={r.user_id}>
                  {r.name}: {r.stars}★
                </li>
              ))}
            </ul>
          )}
          {!recipe.deleted && (
            <div className="flex flex-wrap gap-2 pt-2">
              <button
                ref={planButton}
                type="button"
                className={BUTTON}
                onClick={() => setPlanning(true)}
              >
                {t("plan.planRecipe")}
              </button>
              <Link
                to={`/rezepte/${recipe.id}/bearbeiten`}
                className={BUTTON_SECONDARY}
              >
                {t("common.edit")}
              </Link>
              {recipe.inbox_item_id && (
                <Link
                  to={`/posteingang/${recipe.inbox_item_id}`}
                  className={BUTTON_SECONDARY}
                >
                  {t("recipes.viewOriginal")}
                </Link>
              )}
              {recipe.original && (
                <button
                  type="button"
                  className={BUTTON_SECONDARY}
                  onClick={() => setShowOriginal(!showOriginal)}
                >
                  {showOriginal
                    ? t("recipes.showTranslation")
                    : t("recipes.showOriginal")}
                </button>
              )}
              {canTranslate && (
                <button
                  type="button"
                  className={BUTTON_SECONDARY}
                  onClick={translate}
                  disabled={translating}
                >
                  {translating
                    ? t("recipes.translating")
                    : t(`recipes.translateInto.${recipe.translate_into ?? "de"}`)}
                </button>
              )}
              {canCategorize && (
                <button
                  type="button"
                  className={BUTTON_SECONDARY}
                  onClick={suggestCategories}
                  disabled={categorizing}
                >
                  {categorizing ? t("recipes.categorizing") : t("recipes.categorizeOne")}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
      {/* Always there, so screen readers announce the text when it comes */}
      <div role="status">
        {justPlanned?.recipe?.id === recipe.id && (
          <p className="rounded-lg border border-emerald-400/30 bg-emerald-900/30 p-3 text-sm text-emerald-100">
            {t("plan.plannedAt", {
              place: place(justPlanned.date, justPlanned.slot),
            })}{" "}
            <Link to={`/?woche=${justPlanned.date}`} className="underline">
              {t("plan.showWeek")}
            </Link>
          </p>
        )}
      </div>
      {error && <p className={ERROR}>{error}</p>}
      {planning && people !== null && (
        <PlanRecipeDialog
          recipeId={recipe.id}
          title={recipe.title}
          people={people}
          onClose={closePlanning}
          onPlanned={(entry) => {
            closePlanning();
            setJustPlanned(entry);
            refreshPlanned();
          }}
        />
      )}
      <div className="grid gap-6 md:grid-cols-[minmax(16rem,1fr)_2fr]">
        <IngredientList
          ingredients={shown.ingredients}
          people={people}
          onPeople={setPeople}
        />
        <RecipeSteps steps={shown.steps} notes={shown.notes} />
      </div>
      {/* Rarely needed, so away from the everyday actions at the top */}
      {user?.role === "PARENT" && !recipe.deleted && (
        <div className="flex justify-end">
          <button
            type="button"
            className="rounded-lg px-3 py-2 text-sm text-red-300/80 hover:bg-red-900/30 hover:text-red-200"
            onClick={remove}
          >
            {t("recipes.delete")}
          </button>
        </div>
      )}
    </article>
  );
}
