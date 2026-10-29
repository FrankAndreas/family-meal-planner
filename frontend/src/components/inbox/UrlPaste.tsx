import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { errorMessage } from '../../api';
import { addUrl } from '../../inbox';
import { BUTTON, ERROR, INPUT } from '../../ui';

export default function UrlPaste({ onAdded }: { onAdded: () => void }) {
    const { t } = useTranslation();
    const [url, setUrl] = useState('');
    const [error, setError] = useState('');
    const submit = async (e: FormEvent) => {
        e.preventDefault();
        setError('');
        try {
            await addUrl(url.trim());
            setUrl('');
            onAdded();
        } catch (err) {
            setError(errorMessage(err));
        }
    };
    return (
        <form onSubmit={submit} className="glass-card space-y-2 p-4">
            <div className="flex flex-wrap gap-2">
                <input
                    className={`${INPUT} min-w-60 flex-1`}
                    type="url"
                    inputMode="url"
                    aria-label={t('inbox.link')}
                    placeholder={t('inbox.linkPlaceholder')}
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                />
                <button type="submit" className={BUTTON} disabled={!url.trim()}>
                    {t('inbox.addLink')}
                </button>
            </div>
            {error && <p className={ERROR}>{error}</p>}
        </form>
    );
}
