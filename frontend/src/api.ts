import axios from 'axios';
import i18n from './i18n';

// Same origin: Vite (dev, browser tests) or nginx (Docker) forwards /api to the backend, and the login is the family
// hub's cookie, which the browser sends by itself. The backend takes changes made with the cookie only with this header
// (another site can make a browser send the cookie, but not the header)
const api = axios.create({ withCredentials: true, headers: { 'X-Requested-With': 'meals' } });

// A backend path for <img src> and links, which don't go through axios (photos are served without login)
export const apiUrl = (path: string) => path;

// The login ended (logged out in the hub, a new PIN): log in at the hub, which sends the browser back here
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (axios.isAxiosError(error) && error.response?.status === 401 && !error.config?.url?.endsWith('/api/hub')) {
            void goToHub();
        }
        return Promise.reject(error);
    },
);

// Where the family hub is (HUB_PUBLIC_URL), and where "Log out" goes (at home the hub, outside Cloudflare Access)
async function hubLinks(): Promise<{ login_url: string; logout_url: string }> {
    return (await api.get<{ login_url: string; logout_url: string }>('/api/hub')).data;
}

async function hubUrl(): Promise<string> {
    return (await hubLinks()).login_url;
}

// To the hub's login; with next=, the hub sends the browser back here afterwards
export async function goToHub(next: string | null = window.location.href): Promise<void> {
    const login = await hubUrl();
    window.location.href = next ? `${login}/?next=${encodeURIComponent(next)}` : login;
}

// "Log out": the hub ends the login, for the planner and every other family app, then shows its login (back here after)
export async function goToHubLogout(): Promise<void> {
    const { logout_url } = await hubLinks();
    // Outside, Cloudflare's logout (an address on this site) ends the e-mail-code login; at home the hub's page does,
    // and leads back here after the next login
    window.location.href = logout_url.startsWith('/')
        ? logout_url
        : `${logout_url}?next=${encodeURIComponent(window.location.origin)}`;
}

// The code of an error the app acts on (no_access, hub_unavailable)
export function errorCode(error: unknown): string | undefined {
    const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
    return typeof detail === 'string' ? detail : undefined;
}

// The backend sends a code (errors.<code> in the locales), alone or with the values the text needs
export function errorMessage(error: unknown): string {
    if (axios.isAxiosError(error)) {
        let detail = error.response?.data?.detail;
        // Validation errors (422) come as a list; a check of ours names its code in the message ("Value error, x")
        if (Array.isArray(detail)) detail = /Value error, (\w+)/.exec(detail.map((d) => d.msg).join(' '))?.[1];
        const { code, ...params } = typeof detail === 'string' ? { code: detail } : (detail ?? {});
        if (typeof code === 'string' && i18n.exists(`errors.${code}`)) return i18n.t(`errors.${code}`, params);
        if (!error.response) return i18n.t('errors.network');
    }
    return i18n.t('errors.generic');
}

export default api;
