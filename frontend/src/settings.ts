import api from './api';
import type { FamilySettings } from './types';

export const fetchSettings = async () => (await api.get<FamilySettings>('/api/settings')).data;
export const saveSettings = async (fields: Partial<FamilySettings>) =>
    (await api.patch<FamilySettings>('/api/settings', fields)).data;

// The same, sent while the page closes or hides: a request that outlives the page (axios can't ask for that)
export async function saveSettingsOnLeave(fields: Partial<FamilySettings>): Promise<FamilySettings> {
    const response = await fetch('/api/settings', {
        method: 'PATCH',
        keepalive: true,
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'meals' },
        body: JSON.stringify(fields),
    });
    if (!response.ok) throw new Error(`${response.status}`);
    return (await response.json()) as FamilySettings;
}
