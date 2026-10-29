import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { errorMessage } from '../../api';
import { addScan } from '../../inbox';
import { shrink } from '../../scan';
import { BUTTON, BUTTON_SECONDARY, ERROR } from '../../ui';

const MAX_PHOTOS = 10;

interface Shot {
    key: number;
    url: string;
    blob: Blob;
}

// Photos of one recipe taken in the app (the back of a pack, a cookbook page), sent together to the inbox:
// a parent's are read at once, a child's wait for a parent
export default function ScanRecipe({ onDone }: { onDone: () => void }) {
    const { t } = useTranslation();
    const camera = useRef<HTMLInputElement>(null);
    const library = useRef<HTMLInputElement>(null);
    const [shots, setShots] = useState<Shot[]>([]);
    const [sending, setSending] = useState(false);
    const [error, setError] = useState('');
    const urls = useRef<string[]>([]);
    useEffect(() => () => urls.current.forEach((url) => URL.revokeObjectURL(url)), []);

    const taken = async (event: ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(event.target.files ?? []);
        event.target.value = '';
        const added: Shot[] = [];
        for (const file of files) {
            // A photo the browser can't shrink (HEIC outside Safari) goes up as it is: the server reads those too
            const blob = await shrink(file).catch(() => file);
            const url = URL.createObjectURL(blob);
            urls.current.push(url);
            added.push({ key: Date.now() + Math.random(), url, blob });
        }
        setShots((list) => [...list, ...added].slice(0, MAX_PHOTOS));
    };

    const send = async () => {
        setSending(true);
        setError('');
        try {
            await addScan(shots.map((shot) => shot.blob));
            onDone();
        } catch (err) {
            setError(errorMessage(err));
            setSending(false);
        }
    };

    const full = shots.length >= MAX_PHOTOS;
    return (
        <section className="glass-card space-y-3 p-4">
            <p className="text-sm text-slate-400">{t('recipes.scanIntro')}</p>
            <input ref={camera} type="file" accept="image/*" capture="environment" aria-label={t('recipes.scanCamera')} onChange={taken} className="sr-only" />
            <input ref={library} type="file" accept="image/*" multiple aria-label={t('recipes.scanLibrary')} onChange={taken} className="sr-only" />
            {shots.length > 0 && (
                <ul className="flex flex-wrap gap-2">
                    {shots.map((shot, index) => (
                        <li key={shot.key} className="w-24 text-center text-xs">
                            <img src={shot.url} alt={t('recipes.scanPhoto', { n: index + 1 })} className="h-28 w-24 rounded-lg object-cover" />
                            <button
                                type="button"
                                className="mt-1 text-slate-400 underline disabled:opacity-50"
                                disabled={sending}
                                aria-label={t('recipes.scanRemove', { n: index + 1 })}
                                onClick={() => setShots((list) => list.filter((other) => other.key !== shot.key))}
                            >
                                ✕ {t('recipes.scanRemoveShort')}
                            </button>
                        </li>
                    ))}
                </ul>
            )}
            <div className="flex flex-wrap gap-2">
                <button type="button" className={BUTTON_SECONDARY} disabled={full || sending} onClick={() => camera.current?.click()}>
                    {shots.length === 0 ? t('recipes.scanFirst') : t('recipes.scanNext')}
                </button>
                <button type="button" className={BUTTON_SECONDARY} disabled={full || sending} onClick={() => library.current?.click()}>
                    {t('recipes.scanLibrary')}
                </button>
                <button type="button" className={BUTTON} disabled={shots.length === 0 || sending} onClick={send}>
                    {sending ? t('recipes.scanSending') : t('recipes.scanSend', { count: shots.length })}
                </button>
            </div>
            {error && <p className={ERROR}>{error}</p>}
        </section>
    );
}
