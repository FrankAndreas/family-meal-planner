import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { errorMessage } from '../../api';
import { addText } from '../../inbox';
import { BUTTON, ERROR, INPUT } from '../../ui';

const MAX_CHARS = 20_000;

// A recipe's text copied from a post (Facebook, Instagram: pages that show nothing without a login), with the link
// it came from. A parent's is read at once, a child's waits for a parent; the link is only kept as the source.
export default function PasteText({ onAdded }: { onAdded: () => void }) {
    const { t } = useTranslation();
    const [text, setText] = useState('');
    const [url, setUrl] = useState('');
    const [sending, setSending] = useState(false);
    const [error, setError] = useState('');
    const submit = async (e: FormEvent) => {
        e.preventDefault();
        setSending(true);
        setError('');
        try {
            await addText(text.trim(), url.trim());
            setText('');
            setUrl('');
            onAdded();
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setSending(false);
        }
    };
    return (
        <form onSubmit={submit} className="glass-card space-y-3 p-4">
            <p className="text-sm text-slate-400">{t('inbox.pasteIntro')}</p>
            <textarea
                className={`${INPUT} min-h-48`}
                aria-label={t('inbox.text')}
                placeholder={t('inbox.textPlaceholder')}
                maxLength={MAX_CHARS}
                value={text}
                onChange={(e) => setText(e.target.value)}
            />
            <input
                className={INPUT}
                type="url"
                inputMode="url"
                aria-label={t('inbox.sourceLink')}
                placeholder={t('inbox.sourceLink')}
                value={url}
                onChange={(e) => setUrl(e.target.value)}
            />
            <button type="submit" className={BUTTON} disabled={!text.trim() || sending}>
                {t('inbox.sendText')}
            </button>
            {error && <p className={ERROR}>{error}</p>}
        </form>
    );
}
