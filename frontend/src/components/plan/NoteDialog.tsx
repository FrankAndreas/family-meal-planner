import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { BUTTON, BUTTON_SECONDARY, INPUT } from '../../ui';

const QUICK = ['leftovers', 'eatingOut', 'pizza', 'schoolWork'] as const;

interface NoteDialogProps {
    // What the note is for, e.g. "Sunday, Lunch"
    place: string;
    onAdd: (note: string) => void;
    onClose: () => void;
}

export default function NoteDialog({ place, onAdd, onClose }: NoteDialogProps) {
    const { t } = useTranslation();
    const [text, setText] = useState('');
    const submit = (e: FormEvent) => {
        e.preventDefault();
        if (text.trim()) onAdd(text.trim());
    };
    return (
        <div className="fixed inset-0 z-30 flex items-end justify-center bg-black/50 p-4 sm:items-center" onClick={onClose}>
            <form
                role="dialog"
                aria-label={t('plan.addNote')}
                onSubmit={submit}
                onClick={(e) => e.stopPropagation()}
                className="glass-card w-full max-w-md space-y-4 bg-slate-900/90 p-5"
            >
                <div>
                    <h2 className="text-lg">{t('plan.addNote')}</h2>
                    <p className="text-sm text-slate-400">{place}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                    {QUICK.map((key) => (
                        <button
                            key={key}
                            type="button"
                            className="rounded-full border border-white/15 px-3 py-1.5 text-sm hover:bg-white/10"
                            onClick={() => onAdd(t(`plan.quickNotes.${key}`))}
                        >
                            {t(`plan.quickNotes.${key}`)}
                        </button>
                    ))}
                </div>
                <input
                    className={INPUT}
                    aria-label={t('plan.noteText')}
                    placeholder={t('plan.notePlaceholder')}
                    maxLength={200}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    autoFocus
                />
                <div className="flex gap-2">
                    <button type="submit" className={BUTTON} disabled={!text.trim()}>
                        {t('common.add')}
                    </button>
                    <button type="button" className={BUTTON_SECONDARY} onClick={onClose}>
                        {t('common.cancel')}
                    </button>
                </div>
            </form>
        </div>
    );
}
