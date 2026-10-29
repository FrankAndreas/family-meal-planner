import { useAuth } from '../AuthContext';
import FamilyMembers from '../components/settings/FamilyMembers';
import FamilySettings from '../components/settings/FamilySettings';
import MySettings from '../components/settings/MySettings';

// Everyone sees their own settings; the family's are for parents only (the backend enforces this too)
export default function SettingsPage() {
    const { user } = useAuth();
    return (
        <div className="mx-auto max-w-3xl space-y-6">
            <MySettings />
            {user?.role === 'PARENT' && (
                <>
                    <FamilySettings />
                    <FamilyMembers />
                </>
            )}
        </div>
    );
}
