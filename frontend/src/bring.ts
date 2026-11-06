import api from './api';

// The Bring! account the planner sends shopping lists to (spec 2026-11-06); the password never comes back
export interface BringLogin {
    email: string | null;
    list_uuid: string | null;
    list_name: string | null;
}

export interface BringList {
    uuid: string;
    name: string;
}

export const fetchBring = async () => (await api.get<BringLogin>('/api/bring')).data;

export const bringLogin = async (email: string, password: string) =>
    (await api.post<{ lists: BringList[] }>('/api/bring/login', { email, password })).data.lists;

export const fetchBringLists = async () => (await api.get<{ lists: BringList[] }>('/api/bring/lists')).data.lists;

export const chooseBringList = async (uuid: string) => (await api.put<BringLogin>('/api/bring/list', { uuid })).data;

export const bringLogout = async () => {
    await api.delete('/api/bring');
};

/** Signed in and a list chosen: the shopping list can be sent. */
export const bringReady = (login: BringLogin | null) => Boolean(login?.email && login.list_uuid);
