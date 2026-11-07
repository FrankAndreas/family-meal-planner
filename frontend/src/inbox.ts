import api, { fetchBlob } from './api';
import type { Category } from './categories';
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
    kind: 'mail' | 'url' | 'scan' | 'text';
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

export type Draft = Omit<RecipeInput, 'ingredients' | 'categories'> & {
    // Missing in drafts made before there were categories
    categories?: Category[];
    ingredients: { amount: number | null; unit: string | null; name: string; note: string }[];
    uncertain: string[];
    photo?: string | null;
    image_attachment?: number | null;
};

export interface InboxItemDetail extends InboxItem {
    draft: Draft | null;
    ai_raw: string | null;
    // A pasted text, as it was pasted
    text: string | null;
}

export const fetchInbox = async () => (await api.get<InboxItem[]>('/api/inbox')).data;
export const fetchItem = async (id: number | string) => (await api.get<InboxItemDetail>(`/api/inbox/${id}`)).data;
export const fetchInboxCount = async () => (await api.get<{ waiting: number }>('/api/inbox/count')).data.waiting;
export const processItem = (id: number) => api.post(`/api/inbox/${id}/process`);
export const discardItem = (id: number) => api.delete(`/api/inbox/${id}`);
export const addUrl = (url: string) => api.post<InboxItem>('/api/inbox/urls', { url });
// A recipe's text (a Facebook post's caption) and, if known, the link it came from: only kept as the source
export const addText = (text: string, url: string) => api.post<InboxItem>('/api/inbox/texts', { text, url: url || null });
// The photos of one recipe, as one inbox item
export const addScan = (photos: Blob[]) => {
    const body = new FormData();
    photos.forEach((photo, n) => body.append('files', photo, `scan-${n + 1}.jpg`));
    return api.post<InboxItem>('/api/inbox/scans', body);
};
// The mail as it arrived, to download (parents)
export const fetchRawMail = (id: number | string) => fetchBlob(`/api/inbox/${id}/raw`);
export const isImage = (a: Attachment) => a.type.startsWith('image/');
