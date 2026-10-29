import { useDraggable } from '@dnd-kit/core';
import type { ReactNode } from 'react';

// Only the pointer listeners: the wrapped card or chip stays the one button people (and screen readers) use.
// Keyboard users plan by tap-tap (Enter on the card, then on a cell).
export default function Draggable({ id, children }: { id: string; children: ReactNode }) {
    const { setNodeRef, listeners, isDragging } = useDraggable({ id });
    return (
        <div ref={setNodeRef} {...listeners} className={`touch-manipulation ${isDragging ? 'opacity-40' : ''}`}>
            {children}
        </div>
    );
}
