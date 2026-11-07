import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { ShoppingLine, ShoppingList } from '../../shopping';
import type { Placement } from '../../shoppingView';
import { BUTTON_SECONDARY, CARD, FIELD } from '../../ui';

interface ShoppingLinesProps {
    list: ShoppingList;
    placed: Placement;
    // After a refused send: the lines that changed meanwhile, and the names no longer on the list
    changed: { keys: Set<string>; gone: string[] };
    busy: boolean;
    spec: (line: ShoppingLine) => string;
    onChoose: (line: ShoppingLine, buy: boolean) => void;
    // True if it was added: then the fields are emptied (else what was typed stays, to try again)
    onAdd: (name: string, amount: string) => Promise<boolean>;
    onRemoveExtra: (id: number) => void;
}

// What to buy: the lines from the ticked meals (to buy first, the rest at the end), and things added by hand
export default function ShoppingLines({ list, placed, changed, busy, spec, onChoose, onAdd, onRemoveExtra }: ShoppingLinesProps) {
    const { t } = useTranslation();
    const [name, setName] = useState('');
    const [amount, setAmount] = useState('');
    const top = (line: ShoppingLine) => placed.top.get(line.key) ?? line.buy;
    const toBuyFirst = list.lines.filter(top);
    const atTheEnd = list.lines.filter((line) => !top(line));

    const add = async (e: FormEvent) => {
        e.preventDefault();
        if (await onAdd(name.trim(), amount.trim())) {
            setName('');
            setAmount('');
        }
    };

    const lineItem = (line: ShoppingLine) => (
        <li key={line.key} className={changed.keys.has(line.key) ? '-mx-2 rounded-lg bg-amber-400/15 px-2' : ''}>
            <label className="flex items-start gap-2">
                <input
                    type="checkbox"
                    className="mt-1"
                    checked={line.buy}
                    disabled={busy}
                    onChange={(e) => onChoose(line, e.target.checked)}
                />
                <span className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-2">
                    <span className={line.buy ? '' : 'text-slate-500 line-through'}>
                        {spec(line) ? `${spec(line)} ${line.name}` : line.name}
                    </span>
                    {/* The meals go on the next line rather than squeeze the item */}
                    <span className="text-sm text-slate-400">
                        {line.meals.length > 0 && t('shopping.from', { meals: line.meals.join(', ') })}
                        {line.staple && !line.buy && ` ${t('shopping.usuallyAtHome')}`}
                    </span>
                </span>
                {changed.keys.has(line.key) && (
                    <span className="shrink-0 rounded-full bg-amber-400/20 px-2 text-xs text-amber-100">
                        {t('shopping.changed')}
                    </span>
                )}
            </label>
        </li>
    );

    return (
        <section className={`${CARD} space-y-3`} aria-labelledby="shopping-items">
            <h2 id="shopping-items" className="text-lg">
                {t('shopping.items')}
            </h2>
            {list.lines.length === 0 && <p className="text-sm text-slate-400">{t('shopping.noItems')}</p>}
            <ul className="space-y-1">{toBuyFirst.map(lineItem)}</ul>
            {atTheEnd.length > 0 && (
                <>
                    <h3 className="pt-2 text-sm font-semibold text-slate-400">{t('shopping.notBuying')}</h3>
                    <ul className="space-y-1">{atTheEnd.map(lineItem)}</ul>
                </>
            )}
            {changed.gone.length > 0 && (
                <p className="text-sm text-amber-100">{t('shopping.gone', { names: changed.gone.join(', ') })}</p>
            )}
            <form className="flex flex-wrap items-end gap-2" onSubmit={add}>
                <label className="min-w-0 flex-1 space-y-1">
                    <span className="block text-sm text-slate-300">{t('shopping.addName')}</span>
                    <input
                        className={`${FIELD} w-full`}
                        maxLength={100}
                        required
                        placeholder={t('shopping.addNamePlaceholder')}
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                    />
                </label>
                <label className="w-32 space-y-1">
                    <span className="block text-sm text-slate-300">{t('shopping.addAmount')}</span>
                    <input
                        className={`${FIELD} w-full`}
                        maxLength={50}
                        placeholder={t('shopping.addAmountPlaceholder')}
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                    />
                </label>
                <button type="submit" className={BUTTON_SECONDARY} disabled={busy || !name.trim()}>
                    {t('shopping.add')}
                </button>
            </form>
            {list.extras.length > 0 && (
                <ul className="flex flex-wrap gap-2">
                    {list.extras.map((extra) => (
                        <li key={extra.id}>
                            <button
                                type="button"
                                className="rounded-full border border-white/15 px-3 py-1 text-sm hover:bg-white/10"
                                aria-label={t('shopping.removeExtra', { name: extra.name })}
                                disabled={busy}
                                onClick={() => onRemoveExtra(extra.id)}
                            >
                                {extra.amount ? `${extra.amount} ${extra.name}` : extra.name} ✕
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </section>
    );
}
