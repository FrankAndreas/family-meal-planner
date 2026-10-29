import { useAuth } from '../AuthContext';
import AiUsage from '../components/settings/AiUsage';
import FamilyMembers from '../components/settings/FamilyMembers';
import FamilySettings from '../components/settings/FamilySettings';
import MailAddresses from '../components/settings/MailAddresses';
import MySettings from '../components/settings/MySettings';

// Everyone sees their own settings; the family's are for parents only (the backend enforces this too)
export default function SettingsPage() {
    const { user } = useAuth();
    return (
        <div className="mx-auto max-w-3xl space-y-6">
            <MySettings />
            <MailAddresses />
            {user?.role === 'PARENT' && (
                <>
                    <FamilySettings />
                    <FamilyMembers />
                    <AiUsage />
                </>
            )}
        </div>
    );
}
