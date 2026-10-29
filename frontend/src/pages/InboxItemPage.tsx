import { format, parseISO } from 'date-fns';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import api, { errorMessage } from '../api';
import { useAuth } from '../AuthContext';
import AuthImage from '../components/AuthImage';
import { fetchItem, type InboxItemDetail, isImage } from '../inbox';
import { BUTTON_SECONDARY, CARD, ERROR } from '../ui';

// The original of an import: what arrived, as it arrived
export default function InboxItemPage() {
    const { t } = useTranslation();
    const { id } = useParams();
    const { user } = useAuth();
    const [item, setItem] = useState<InboxItemDetail | null>(null);
    const [error, setError] = useState('');

    useEffect(() => {
        let current = true;
        fetchItem(id!)
            .then((found) => current && setItem(found))
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, [id]);

    const download = async () => {
        try {
            const response = await api.get<Blob>(`/api/inbox/${id}/raw`, { responseType: 'blob' });
            const href = URL.createObjectURL(response.data);
            const link = document.createElement('a');
            link.href = href;
            link.download = `rezept-${id}.eml`;
            link.click();
            setTimeout(() => URL.revokeObjectURL(href), 1000);
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    if (!item) return error ? <p className={ERROR}>{error}</p> : <p className="text-slate-400">{t('common.loading')}</p>;

    return (
        <div className="mx-auto max-w-4xl space-y-5">
            <section className={`${CARD} space-y-2`}>
                <h1 className="text-2xl">{item.subject}</h1>
                <p className="text-sm text-slate-400">
                    {[item.user_name, item.from_addr].filter(Boolean).join(' · ')} · {format(parseISO(`${item.received_at}Z`), 'd.M.yyyy HH:mm')}
                </p>
                {item.url && (
                    <a href={item.url} target="_blank" rel="noreferrer" className="break-all text-cyan-300 underline">
                        {item.url}
                    </a>
                )}
                <div className="flex flex-wrap gap-2 pt-2">
                    {item.recipe_id && (
                        <Link to={`/rezepte/${item.recipe_id}`} className={BUTTON_SECONDARY}>
                            {t('inbox.toRecipe')}
                        </Link>
                    )}
                    {item.kind === 'mail' && user?.role === 'PARENT' && (
                        <button type="button" className={BUTTON_SECONDARY} onClick={download}>
                            {t('inbox.downloadMail')}
                        </button>
                    )}
                </div>
            </section>
            {item.attachments.filter(isImage).map((a) => (
                <AuthImage key={a.index} src={`/api/inbox/${item.id}/attachments/${a.index}`} alt={a.name} className="w-full rounded-2xl" />
            ))}
            {item.ai_raw && (
                <details className={CARD}>
                    <summary className="cursor-pointer text-sm text-slate-300">{t('inbox.aiAnswer')}</summary>
                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-slate-400">{item.ai_raw}</pre>
                </details>
            )}
            {error && <p className={ERROR}>{error}</p>}
        </div>
    );
}
