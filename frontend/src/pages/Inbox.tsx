import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { errorMessage } from '../api';
import { useAuth } from '../AuthContext';
import InboxItemCard from '../components/inbox/InboxItemCard';
import UrlPaste from '../components/inbox/UrlPaste';
import { discardItem, fetchInbox, type InboxItem, processItem } from '../inbox';
import { ERROR } from '../ui';

const POLL_MS = 2000;

export default function Inbox() {
    const { t } = useTranslation();
    const { user } = useAuth();
    const [items, setItems] = useState<InboxItem[] | null>(null);
    const [error, setError] = useState('');
    const parent = user?.role === 'PARENT';

    const load = useCallback(async () => {
        try {
            setItems(await fetchInbox());
        } catch (err) {
            setError(errorMessage(err));
        }
    }, []);

    useEffect(() => {
        let current = true;
        fetchInbox()
            .then((found) => current && setItems(found))
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, []);

    // While something is being read, look again every two seconds
    const busy = items?.some((i) => i.status === 'processing') ?? false;
    useEffect(() => {
        if (!busy) return;
        const timer = setInterval(load, POLL_MS);
        return () => clearInterval(timer);
    }, [busy, load]);

    const run = async (action: () => Promise<unknown>) => {
        setError('');
        try {
            await action();
        } catch (err) {
            setError(errorMessage(err));
        }
        await load();
    };

    return (
        <div className="mx-auto max-w-4xl space-y-5">
            <div>
                <h1 className="text-2xl">{t('nav.inbox')}</h1>
                <p className="text-sm text-slate-400">{parent ? t('inbox.introParent') : t('inbox.introChild')}</p>
            </div>
            <UrlPaste onAdded={load} />
            {error && <p className={ERROR}>{error}</p>}
            {items?.length === 0 && <p className="text-slate-400">{t('inbox.empty')}</p>}
            {items?.map((item) => (
                <InboxItemCard
                    key={item.id}
                    item={item}
                    parent={parent}
                    onProcess={() => run(() => processItem(item.id))}
                    onDiscard={() => {
                        if (confirm(t('inbox.confirmDiscard', { subject: item.subject }))) run(() => discardItem(item.id));
                    }}
                />
            ))}
        </div>
    );
}
