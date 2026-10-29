import axios from 'axios';
import i18n from './i18n';

// Same origin: Vite (dev) or nginx (Docker) forwards /api to the backend; the browser tests set VITE_API_URL
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || undefined });

// A backend path for <img src> and links, which don't go through axios (photos are served without login)
export const apiUrl = (path: string) => (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '') + path;

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Expired or invalid token: drop it and go back to the login page
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const isLogin = error.config?.url?.endsWith('/api/token');
        if (error.response?.status === 401 && !isLogin && localStorage.getItem('token')) {
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    },
);

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
