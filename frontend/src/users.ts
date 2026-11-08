import api, { renewsAtHub } from './api';
import type { User } from './types';

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
