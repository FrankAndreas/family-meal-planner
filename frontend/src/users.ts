import api, { renewsAtHub } from './api';
import type { User } from './types';

// Mirrors backend/app/schemas.py (EmailOut)
export interface MailAddress {
    id: number;
    user_id: number;
    user_name: string;
    address: string;
}

export const fetchMe = async () => (await api.get<User>('/api/me')).data;
// Who is logged in, on loading the page; null while on the way through the hub, which renews a login in its last week
// (renewsAtHub)
export const fetchMeOrRenew = async (): Promise<User | null> => {
    const found = await api.get<User>('/api/me');
    return renewsAtHub(found.headers) ? null : found.data;
};
export const fetchUsers = async () => (await api.get<User[]>('/api/users')).data;
// Those the family hub no longer lists, hidden with their data until a parent deletes them
export const fetchRemovedUsers = async () => (await api.get<User[]>('/api/users/removed')).data;
export const deleteUser = (id: number) => api.delete(`/api/users/${id}`);

// The addresses recipes may be mailed from; `all`: everybody's (parents), else the person's own
export const fetchMailAddresses = async (all: boolean) =>
    (await api.get<MailAddress[]>('/api/emails', { params: all ? { all: 1 } : {} })).data;
export const addMailAddress = (address: string, userId?: number) =>
    api.post<MailAddress>('/api/emails', { address, ...(userId ? { user_id: userId } : {}) });
export const deleteMailAddress = (id: number) => api.delete(`/api/emails/${id}`);
