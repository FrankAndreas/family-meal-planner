// The site's name for a source link: "swissmilk.ch" for https://www.swissmilk.ch/de/…
export function siteName(url: string): string {
    try {
        return new URL(url).hostname.replace(/^www\./, '');
    } catch {
        return url;
    }
}

// What the backend takes as a link (http/https); anything else is said at once instead of on saving
export const isWebLink = (text: string) => /^https?:\/\/\S+$/i.test(text.trim());
