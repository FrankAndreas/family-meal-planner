import { useEffect, useState } from 'react';
import api from '../api';

// An image only logged-in people may see: <img src> can't send the token, so it is fetched and shown as a blob
export default function AuthImage({ src, alt, className }: { src: string; alt: string; className?: string }) {
    const [url, setUrl] = useState<string | null>(null);
    useEffect(() => {
        let current = true;
        let made: string | null = null;
        api.get<Blob>(src, { responseType: 'blob' })
            .then((response) => {
                if (!current) return;
                made = URL.createObjectURL(response.data);
                setUrl(made);
            })
            .catch(() => {});
        return () => {
            current = false;
            if (made) URL.revokeObjectURL(made);
        };
    }, [src]);
    return url ? <img src={url} alt={alt} className={className} /> : <div className={`${className} bg-white/5`} aria-hidden />;
}
