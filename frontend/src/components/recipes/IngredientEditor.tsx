import { useTranslation } from 'react-i18next';
import { parseAmount } from '../../amounts';
import { emptyRow, type Row } from '../../ingredientRows';
import { BUTTON_SECONDARY, FIELD } from '../../ui';

interface IngredientEditorProps {
    rows: Row[];
    units: string[];
    onChange: (rows: Row[]) => void;
}

export default function IngredientEditor({ rows, units, onChange }: IngredientEditorProps) {
    const { t } = useTranslation();
    const update = (key: number, change: Partial<Row>) =>
        onChange(rows.map((row) => (row.key === key ? { ...row, ...change } : row)));
    const move = (index: number, by: number) => {
        const target = index + by;
        if (target < 0 || target >= rows.length) return;
        const next = [...rows];
        [next[index], next[target]] = [next[target], next[index]];
        onChange(next);
    };
    // Ingredients are numbered for the labels ("Amount 2"); headings don't count
    const numbers = rows.reduce<number[]>(
        (acc, row) => [...acc, (acc.at(-1) ?? 0) + (row.kind === 'ingredient' ? 1 : 0)],
        [],
    );

    return (
        <div className="space-y-2">
            {rows.map((row, index) => {
                const tools = (
                    <div className="flex gap-1">
                        <button type="button" className="px-2 text-slate-400 hover:text-white" aria-label={t('recipes.moveUp')} onClick={() => move(index, -1)}>
                            ↑
                        </button>
                        <button type="button" className="px-2 text-slate-400 hover:text-white" aria-label={t('recipes.moveDown')} onClick={() => move(index, 1)}>
                            ↓
                        </button>
                        <button
                            type="button"
                            className="px-2 text-red-300 hover:text-red-200"
                            aria-label={t('recipes.removeRow')}
                            onClick={() => onChange(rows.length > 1 ? rows.filter((r) => r.key !== row.key) : [emptyRow()])}
                        >
                            ✕
                        </button>
                    </div>
                );
                if (row.kind === 'group') {
                    return (
                        <div key={row.key} className="flex items-center gap-2 pt-2">
                            <input
                                className={`${FIELD} flex-1 font-semibold`}
                                aria-label={t('recipes.groupName')}
                                placeholder={t('recipes.groupPlaceholder')}
                                value={row.name}
                                onChange={(e) => update(row.key, { name: e.target.value })}
                            />
                            {tools}
                        </div>
                    );
                }
                const number = numbers[index];
                const badAmount = parseAmount(row.amountText) === 'invalid';
                return (
                    <div key={row.key} className="grid grid-cols-[5rem_6rem_1fr] gap-2 sm:grid-cols-[5rem_7rem_1fr_1fr_auto]">
                        <input
                            className={`${FIELD} ${badAmount ? 'border-red-400' : ''}`}
                            aria-label={t('recipes.amountN', { n: number })}
                            aria-invalid={badAmount}
                            placeholder={t('recipes.amountPlaceholder')}
                            inputMode="decimal"
                            value={row.amountText}
                            onChange={(e) => update(row.key, { amountText: e.target.value })}
                        />
                        <select
                            className={FIELD}
                            aria-label={t('recipes.unitN', { n: number })}
                            value={row.unit}
                            onChange={(e) => update(row.key, { unit: e.target.value })}
                        >
                            <option value="">–</option>
                            {units.map((unit) => (
                                <option key={unit} value={unit}>
                                    {t(`units.${unit}` as 'units.g')}
                                </option>
                            ))}
                        </select>
                        <input
                            className={FIELD}
                            aria-label={t('recipes.ingredientN', { n: number })}
                            placeholder={t('recipes.ingredientPlaceholder')}
                            value={row.name}
                            onChange={(e) => update(row.key, { name: e.target.value })}
                        />
                        <input
                            className={`${FIELD} col-span-2 sm:col-span-1`}
                            aria-label={t('recipes.noteN', { n: number })}
                            placeholder={t('recipes.notePlaceholder')}
                            value={row.note}
                            onChange={(e) => update(row.key, { note: e.target.value })}
                        />
                        {tools}
                    </div>
                );
            })}
            <div className="flex flex-wrap gap-2">
                <button type="button" className={BUTTON_SECONDARY} onClick={() => onChange([...rows, emptyRow()])}>
                    {t('recipes.addIngredient')}
                </button>
                <button type="button" className={BUTTON_SECONDARY} onClick={() => onChange([...rows, emptyRow('group')])}>
                    {t('recipes.addGroup')}
                </button>
            </div>
        </div>
    );
}
