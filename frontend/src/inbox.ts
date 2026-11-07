import api, { fetchBlob } from './api';
import type { Schemas } from './apiTypes';
import type { Category } from './categories';
import type { RecipeInput } from './recipes';

export type InboxItem = Schemas['InboxItemOut'];
export type InboxStatus = InboxItem['status'];
export type Attachment = Schemas['Attachment'];

export type Draft = Omit<RecipeInput, 'ingredients' | 'categories'> & {
    // Missing in drafts made before there were categories
    categories?: Category[];
    ingredients: { amount: number | null; unit: string | null; name: string; note: string }[];
    uncertain: string[];
    photo?: string | null;
    image_attachment?: number | null;
};

// The draft is kept as the importer made it (a JSON column), so the backend describes it only as an object
export type InboxItemDetail = Omit<Schemas['InboxItemDetail'], 'draft'> & { draft: Draft | null };

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
// A picture of a mail or scan, or its small preview; for AuthImage (only logged-in people may see them)
export const attachmentPath = (id: number, index: number, thumb = false) =>
    `/api/inbox/${id}/attachments/${index}${thumb ? '/thumb' : ''}`;
export const isImage = (a: Attachment) => a.type.startsWith('image/');
