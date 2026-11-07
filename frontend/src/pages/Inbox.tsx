import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { errorMessage } from '../api';
import { useAuth } from '../AuthContext';
import InboxItemCard from '../components/inbox/InboxItemCard';
import PasteText from '../components/inbox/PasteText';
import UrlPaste from '../components/inbox/UrlPaste';
import { discardItem, fetchInbox, type InboxItem, processItem } from '../inbox';
import { BUTTON_SECONDARY, ERROR, PAGE } from '../ui';

const POLL_MS = 2000;

export default function Inbox() {
    const { t } = useTranslation();
    const { user } = useAuth();
    const [items, setItems] = useState<InboxItem[] | null>(null);
    const [error, setError] = useState('');
    // The form for a pasted recipe text (a Facebook post's caption), open or not
    const [pasting, setPasting] = useState(false);
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
        <div className={`${PAGE} space-y-5`}>
            <div>
                <h1 className="text-2xl">{t('nav.inbox')}</h1>
                <p className="text-sm text-slate-400">{parent ? t('inbox.introParent') : t('inbox.introChild')}</p>
            </div>
            <UrlPaste onAdded={load} />
            <button type="button" className={BUTTON_SECONDARY} aria-expanded={pasting} onClick={() => setPasting(!pasting)}>
                {t('recipes.pasteText')}
            </button>
            {pasting && (
                <PasteText
                    onAdded={() => {
                        setPasting(false);
                        load();
                    }}
                />
            )}
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
