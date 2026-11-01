// A pick from the suggestion list replaces the input's text at once. iPhone autocorrect does that too, so only a
// replacement that is one of the offered words counts as a pick (else a half-typed word would become a chip).
export function isPickedSuggestion(inputType: string | undefined, value: string, offered: string[]): boolean {
    return inputType === 'insertReplacementText' && offered.includes(value);
}
