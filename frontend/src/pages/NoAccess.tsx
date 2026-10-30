import { useTranslation } from 'react-i18next';
import { useAuth } from '../AuthContext';
import { BUTTON, CARD } from '../ui';

// Logged in at the family hub, but the planner isn't ticked for this person; or the hub doesn't answer
export default function NoAccess({ hubDown = false }: { hubDown?: boolean }) {
    const { t } = useTranslation();
    const { logout, retry } = useAuth();
    return (
        <div className="mx-auto max-w-md p-6">
            <div className={`${CARD} space-y-4`}>
                <h1 className="text-xl font-semibold">{hubDown ? t('access.hubDownTitle') : t('access.noAccessTitle')}</h1>
                <p className="text-slate-300">{hubDown ? t('access.hubDown') : t('access.noAccess')}</p>
                {hubDown ? (
                    <button type="button" className={BUTTON} onClick={retry}>{t('access.retry')}</button>
                ) : (
                    <button type="button" className={BUTTON} onClick={() => void logout()}>{t('access.otherPerson')}</button>
                )}
            </div>
        </div>
    );
}
