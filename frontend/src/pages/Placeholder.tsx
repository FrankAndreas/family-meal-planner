import { useTranslation } from 'react-i18next';
import { CARD } from '../ui';

// A page that later plans fill (week plan, recipes)
export default function Placeholder({ titleKey }: { titleKey: 'nav.plan' | 'nav.recipes' | 'nav.settings' }) {
    const { t } = useTranslation();
    return (
        <section className={CARD}>
            <h1 className="text-xl">{t(titleKey)}</h1>
            <p className="mt-2 text-slate-400">{t('common.comingSoon')}</p>
        </section>
    );
}
