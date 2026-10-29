import api from './api';
import type { RecipeInput } from './recipes';

// Mirrors backend/app/schemas.py (InboxItemOut, InboxItemDetail)
export type InboxStatus = 'waiting' | 'processing' | 'draft' | 'failed' | 'done';

export interface Attachment {
    index: number;
    name: string;
    type: string;
    size: number;
}

export interface InboxItem {
    id: number;
    kind: 'mail' | 'url';
    status: InboxStatus;
    user_name: string | null;
    from_addr: string;
    subject: string;
    url: string | null;
    received_at: string;
    attachments: Attachment[];
    error: string | null;
    recipe_id: number | null;
}

export type Draft = Omit<RecipeInput, 'ingredients'> & {
    ingredients: { amount: number | null; unit: string | null; name: string; note: string }[];
    uncertain: string[];
    photo?: string | null;
    image_attachment?: number | null;
};

export interface InboxItemDetail extends InboxItem {
    draft: Draft | null;
    ai_raw: string | null;
}

export const fetchInbox = async () => (await api.get<InboxItem[]>('/api/inbox')).data;
export const fetchItem = async (id: number | string) => (await api.get<InboxItemDetail>(`/api/inbox/${id}`)).data;
export const fetchInboxCount = async () => (await api.get<{ waiting: number }>('/api/inbox/count')).data.waiting;
export const processItem = (id: number) => api.post(`/api/inbox/${id}/process`);
export const discardItem = (id: number) => api.delete(`/api/inbox/${id}`);
export const addUrl = (url: string) => api.post<InboxItem>('/api/inbox/urls', { url });
// The photos of one recipe, as one inbox item
export const addScan = (photos: Blob[]) => {
    const body = new FormData();
    photos.forEach((photo, n) => body.append('files', photo, `scan-${n + 1}.jpg`));
    return api.post<InboxItem>('/api/inbox/scans', body);
};
export const isImage = (a: Attachment) => a.type.startsWith('image/');
