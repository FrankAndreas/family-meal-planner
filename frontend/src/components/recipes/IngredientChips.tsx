import { useEffect, useId, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { FIELD } from '../../ui';

interface IngredientChipsProps {
    values: string[];
    onChange: (values: string[]) => void;
    // The input's name for screen readers and tests
    label: string;
    placeholder?: string;
    // Words to offer while typing (the ingredient names of the collection)
    suggest?: (q: string) => Promise<string[]>;
    // As many as the server takes: then the input makes way for a note
    max: number;
}

// Words as chips: Enter or a suggestion adds one, × removes it. The same word twice (any case) is kept once.
export default function IngredientChips({ values, onChange, label, placeholder, suggest, max }: IngredientChipsProps) {
    const { t } = useTranslation();
    const listId = useId();
    const [text, setText] = useState('');
    const [offered, setOffered] = useState<string[]>([]);

    useEffect(() => {
        if (!suggest) return;
        let current = true;
        const timer = setTimeout(() => {
            (text.trim() ? suggest(text.trim()) : Promise.resolve([]))
                .then((names) => current && setOffered(names))
                .catch(() => {});
        }, 150);
        return () => {
            current = false;
            clearTimeout(timer);
        };
    }, [text, suggest]);

    const add = (word: string) => {
        const clean = word.trim();
        setText('');
        if (!clean || values.length >= max || values.some((v) => v.toLocaleLowerCase() === clean.toLocaleLowerCase())) return;
        onChange([...values, clean]);
    };
    const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            add(text);
        } else if (e.key === 'Backspace' && !text && values.length) {
            onChange(values.slice(0, -1));
        }
    };

    return (
        <div className={`${FIELD} flex flex-wrap items-center gap-2`}>
            {values.map((value) => (
                <span key={value} className="inline-flex items-center gap-1 rounded-full bg-cyan-400/15 py-1 pl-3 pr-1 text-sm text-cyan-100">
                    {value}
                    <button
                        type="button"
                        aria-label={t('useUp.remove', { name: value })}
                        onClick={() => onChange(values.filter((v) => v !== value))}
                        className="h-6 w-6 rounded-full hover:bg-white/10"
                    >
                        ×
                    </button>
                </span>
            ))}
            {values.length >= max ? (
                <span className="p-1 text-sm text-slate-400">{t('useUp.full', { max })}</span>
            ) : (
                <input
                    role="combobox"
                    aria-label={label}
                    list={suggest ? listId : undefined}
                    className="min-w-32 flex-1 bg-transparent p-1 focus:outline-none"
                    placeholder={placeholder}
                    maxLength={40}
                    value={text}
                    onChange={(e) => {
                        // Picking from the list replaces the text at once: that's a choice, add it
                        if ((e.nativeEvent as InputEvent).inputType === 'insertReplacementText') add(e.target.value);
                        else setText(e.target.value);
                    }}
                    onKeyDown={onKey}
                    onBlur={() => add(text)}
                />
            )}
            {suggest && (
                <datalist id={listId}>
                    {offered.map((name) => (
                        <option key={name} value={name} />
                    ))}
                </datalist>
            )}
        </div>
    );
}
