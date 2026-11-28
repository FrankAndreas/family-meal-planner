import { format, parseISO } from 'date-fns';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { attachmentPath, type InboxItem, isImage } from '../../inbox';
import { BUTTON, BUTTON_DANGER, BUTTON_SECONDARY } from '../../ui';
import AuthImage from '../AuthImage';

interface InboxItemCardProps {
    item: InboxItem;
    parent: boolean;
    onProcess: () => void;
    onDiscard: () => void;
}

const CHIP: Record<InboxItem['status'], string> = {
    waiting: 'bg-pressed text-ink',
    processing: 'bg-accent/15 text-accent',
    draft: 'bg-success/15 text-success',
    failed: 'bg-danger/15 text-danger',
    done: 'bg-pressed text-ink',
};

export default function InboxItemCard({ item, parent, onProcess, onDiscard }: InboxItemCardProps) {
    const { t } = useTranslation();
    const status =
        item.status === 'waiting' && !parent
            ? t('inbox.waitingForParent')
            : item.status === 'failed'
              ? t('inbox.failed', { reason: t(`errors.${item.error ?? 'generic'}` as 'errors.generic') })
              : t(`inbox.status.${item.status}`);
    return (
        <article className="glass-card space-y-3 p-4">
            <div className="flex flex-wrap items-start gap-2">
                <div className="mr-auto min-w-0">
                    <h2 className="truncate text-base">{item.subject}</h2>
                    <p className="text-xs text-muted">
                        {item.user_name ?? item.from_addr} · {format(parseISO(`${item.received_at}Z`), 'd.M. HH:mm')}
                        {item.url && (
                            <>
                                {' · '}
                                <a href={item.url} target="_blank" rel="noreferrer" className="text-accent underline">
                                    {t('inbox.openLink')}
                                </a>
                            </>
                        )}
                    </p>
                </div>
                <span className={`rounded-full px-2.5 py-0.5 text-xs ${CHIP[item.status]}`}>{status}</span>
            </div>
            {item.attachments.some(isImage) && (
                <div className="flex flex-wrap gap-2">
                    {item.attachments.filter(isImage).map((a) => (
                        <AuthImage
                            key={a.index}
                            src={attachmentPath(item.id, a.index, true)}
                            alt={a.name}
                            className="h-24 w-24 rounded-lg object-cover"
                        />
                    ))}
                </div>
            )}
            <div className="flex flex-wrap gap-2">
                {item.status === 'draft' && (
                    <Link to={`/rezepte/neu?entwurf=${item.id}`} className={BUTTON}>
                        {t('inbox.review')}
                    </Link>
                )}
                {parent && (item.status === 'waiting' || item.status === 'failed') && (
                    <button type="button" className={item.status === 'waiting' ? BUTTON : BUTTON_SECONDARY} onClick={onProcess}>
                        {item.status === 'failed' ? t('inbox.retry') : t('inbox.process')}
                    </button>
                )}
                <Link to={`/posteingang/${item.id}`} className={BUTTON_SECONDARY}>
                    {t('inbox.details')}
                </Link>
                {parent && item.status !== 'processing' && (
                    <button type="button" className={BUTTON_DANGER} onClick={onDiscard}>
                        {t('inbox.discard')}
                    </button>
                )}
            </div>
        </article>
    );
}
