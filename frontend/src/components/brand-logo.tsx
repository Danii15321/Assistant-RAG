/** Two interlocking quotation ribbons: documents and conversation. */
export function BrandLogo({ className = "" }: { className?: string }) {
  return <svg className={`brand-logo ${className}`} width="36" height="36" viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <path d="M22 5H14A10 10 0 0 0 4 15v12l8-6h6a8 8 0 0 0 8-8V9a4 4 0 0 0-4-4Z" fill="currentColor" />
    <path d="M18 35h8a10 10 0 0 0 10-10V13l-8 6h-6a8 8 0 0 0-8 8v4a4 4 0 0 0 4 4Z" fill="currentColor" opacity=".55" />
    <path d="m13 16 5-5m4 18 5-5" stroke="var(--background)" strokeWidth="3" strokeLinecap="round" />
  </svg>;
}
