import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { hubLinks } from '../../api';
import { CARD } from '../../ui';

// Language, PIN and logging out everywhere live in the family hub now (spec 2026-10-30)
export default function MySettings() {
    const { t } = useTranslation();
    const [hub, setHub] = useState<string | null>(null);

    useEffect(() => {
        hubLinks()
            .then((links) => setHub(links.login_url))
            .catch(() => setHub(null));
    }, []);

    return (
        <section className={`${CARD} space-y-3`}>
            <h2 className="text-lg">{t('settings.mine')}</h2>
            <p className="text-sm text-slate-300">{t('settings.inHub')}</p>
            {hub && (
                <a href={`${hub}/settings`} className="inline-block text-sm text-blue-300 hover:underline">
                    {t('settings.toHub')}
                </a>
            )}
        </section>
    );
}
