/** Mark: a doorway (adobe arch) with a small sage window — "a home, and its past". */
export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden focusable="false">
      <rect x="1" y="1" width="30" height="30" rx="8" fill="var(--adobe-soft)" />
      <path d="M9 26V15a7 7 0 0 1 14 0v11" fill="none" stroke="var(--adobe)" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M13.5 26v-6.5a2.5 2.5 0 0 1 5 0V26" fill="var(--accent)" opacity="0.9" />
      <path d="M6 26h20" stroke="var(--adobe)" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}
