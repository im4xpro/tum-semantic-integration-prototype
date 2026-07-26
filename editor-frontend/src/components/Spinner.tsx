export function Spinner({ className = '' }: { className?: string }) {
  return (
    <span className={`w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin ${className}`} />
  );
}
