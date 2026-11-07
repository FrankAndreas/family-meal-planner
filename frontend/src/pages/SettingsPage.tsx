import { useTranslation } from 'react-i18next';
import { useAuth } from '../AuthContext';
import AiUsage from '../components/settings/AiUsage';
import BringSettings from '../components/settings/BringSettings';
import FamilyMembers from '../components/settings/FamilyMembers';
import FamilySettings from '../components/settings/FamilySettings';
import MailAddresses from '../components/settings/MailAddresses';
import MySettings from '../components/settings/MySettings';
import { PAGE } from '../ui';

// Everyone sees their own settings; the family's are for parents only (the backend enforces this too)
export default function SettingsPage() {
    const { t } = useTranslation();
    const { user } = useAuth();
    return (
        <div className={`${PAGE} space-y-6`}>
            <h1 className="text-2xl">{t('nav.settings')}</h1>
            <MySettings />
            <MailAddresses />
            {user?.role === 'PARENT' && (
                <>
                    <FamilySettings />
                    <FamilyMembers />
                    <BringSettings />
                    <AiUsage />
                </>
            )}
        </div>
    );
}
