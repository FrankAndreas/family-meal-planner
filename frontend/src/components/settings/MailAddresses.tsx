import { useTranslation } from 'react-i18next';
import { useAuth } from '../../AuthContext';
import { CARD } from '../../ui';

// Recipes mailed to rezepte@… are taken only from the address each person confirmed in the family hub, when the hub
// shares it with the planner (security review 2026-11-08): shown here, changed in the hub. Parents see everyone's in
// the family members
export default function MailAddresses() {
    const { t } = useTranslation();
    const { user } = useAuth();
    return (
        <section className={`${CARD} space-y-3`} aria-labelledby="mail-addresses">
            <div>
                <h2 id="mail-addresses" className="text-lg">
                    {t('settings.mailAddresses')}
                </h2>
                <p className="text-sm text-slate-400">{t('settings.mailAddressesHint')}</p>
            </div>
            <p className="text-sm">
                {user?.email ? t('settings.mailAddressMine', { address: user.email }) : t('settings.mailAddressMissing')}
            </p>
        </section>
    );
}
