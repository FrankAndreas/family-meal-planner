import { useEffect, useMemo, useState, type ClipboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { apiUrl } from '../../api';
import { isWebLink } from '../../recipes';
import { BUTTON_DANGER, BUTTON_SECONDARY, INPUT } from '../../ui';

// What saving does with the photo: nothing, a picked or pasted picture, a link to load it from, or no photo
export type PhotoChoice = { kind: 'keep' } | { kind: 'file'; file: File } | { kind: 'link'; url: string } | { kind: 'remove' };

const imageIn = (files: Iterable<File> | ArrayLike<File>) => Array.from(files).find((f) => f.type.startsWith('image/'));

interface Props {
    // The photo the recipe (or the draft) has now, as an /api/photos/… path
    current: string | null;
    choice: PhotoChoice;
    onChange: (choice: PhotoChoice) => void;
}

export default function PhotoPicker({ current, choice, onChange }: Props) {
    const { t } = useTranslation();
    const preview = useMemo(() => (choice.kind === 'file' ? URL.createObjectURL(choice.file) : null), [choice]);
    const [clipboardEmpty, setClipboardEmpty] = useState(false);
    // Reading the clipboard by button needs HTTPS; pasting into the link field works everywhere
    const canReadClipboard = typeof navigator !== 'undefined' && !!navigator.clipboard?.read && window.isSecureContext;

    useEffect(() => () => {
        if (preview) URL.revokeObjectURL(preview);
    }, [preview]);

    const pick = (file: File | undefined) => {
        setClipboardEmpty(false);
        if (file) onChange({ kind: 'file', file });
    };

    const pasteFromClipboard = async () => {
        try {
            for (const item of await navigator.clipboard.read()) {
                const type = item.types.find((kind) => kind.startsWith('image/'));
                if (type) return pick(new File([await item.getType(type)], 'clipboard', { type }));
            }
        } catch {
            // Refused by the person or the browser: same as nothing there
        }
        setClipboardEmpty(true);
    };

    // A copied picture pasted into the field becomes the photo instead of text
    const onPaste = (e: ClipboardEvent<HTMLInputElement>) => {
        const file = imageIn(e.clipboardData.files);
        if (!file) return;
        e.preventDefault();
        pick(file);
    };

    const link = choice.kind === 'link' ? choice.url : '';
    const shown = preview ?? (choice.kind === 'keep' && current ? apiUrl(current) : null);
    const hasPhoto = shown !== null || choice.kind === 'link';
    const label = 'mb-1 block text-sm text-slate-300';

    return (
        <div className="space-y-3">
            <span className={label}>{t('recipes.photo')}</span>
            <div className="flex flex-wrap items-start gap-4">
                {shown ? (
                    <img src={shown} alt={t('recipes.photoPreview')} className="h-32 w-44 rounded-xl object-cover" />
                ) : (
                    <div className="flex h-32 w-44 items-center justify-center rounded-xl border border-dashed border-white/20 p-3 text-center text-sm text-slate-400">
                        {choice.kind === 'link' && isWebLink(link) ? t('recipes.photoFromLink') : t('recipes.photoNone')}
                    </div>
                )}
                <div className="flex flex-wrap gap-2">
                    <label className={`${BUTTON_SECONDARY} cursor-pointer`}>
                        {shown ? t('recipes.photoChange') : t('recipes.photoChoose')}
                        <input
                            type="file"
                            accept="image/*"
                            className="sr-only"
                            onChange={(e) => {
                                pick(e.target.files?.[0]);
                                e.target.value = '';
                            }}
                        />
                    </label>
                    {canReadClipboard && (
                        <button type="button" className={BUTTON_SECONDARY} onClick={pasteFromClipboard}>
                            {t('recipes.photoPaste')}
                        </button>
                    )}
                    {hasPhoto && (
                        <button type="button" className={BUTTON_DANGER} onClick={() => onChange(current ? { kind: 'remove' } : { kind: 'keep' })}>
                            {t('recipes.photoRemove')}
                        </button>
                    )}
                </div>
            </div>
            {clipboardEmpty && <p className="text-sm text-amber-200">{t('recipes.photoClipboardEmpty')}</p>}
            <div>
                <label htmlFor="photo-link" className={label}>
                    {t('recipes.photoLink')}
                </label>
                <input
                    id="photo-link"
                    className={INPUT}
                    inputMode="url"
                    placeholder={t('recipes.photoLinkPlaceholder')}
                    value={link}
                    maxLength={1000}
                    onPaste={onPaste}
                    onChange={(e) => onChange(e.target.value.trim() ? { kind: 'link', url: e.target.value } : { kind: 'keep' })}
                />
                {link.trim() && !isWebLink(link) && <p className="mt-1 text-sm text-amber-200">{t('errors.not_a_web_link')}</p>}
            </div>
        </div>
    );
}
