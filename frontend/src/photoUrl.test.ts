import { describe, expect, it } from 'vitest';
import { photoSrc } from './photoUrl';

describe('photoSrc', () => {
    it('a card asks for the small version, a recipe page for the whole photo', () => {
        expect(photoSrc('/api/photos/abc.jpg', 'card')).toBe('/api/photos/abc.jpg?size=card');
        expect(photoSrc('/api/photos/abc.jpg', 'full')).toBe('/api/photos/abc.jpg');
    });

    it('a draft photo with a query of its own keeps it', () => {
        expect(photoSrc('/api/photos/abc.jpg?v=2', 'card')).toBe('/api/photos/abc.jpg?v=2&size=card');
    });
});
