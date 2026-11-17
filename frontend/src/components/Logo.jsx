export function Logo({ className = "h-12 w-12" }) {
  return (
    <span className={`grid place-items-center rounded-2xl bg-accent text-white ${className}`} aria-hidden="true">
      <svg viewBox="0 0 32 32" className="h-7 w-7 fill-current">
        <rect x="4" y="13" width="3" height="6" rx="1.5" />
        <rect x="9.5" y="8" width="3" height="16" rx="1.5" />
        <rect x="15" y="5" width="3" height="22" rx="1.5" />
        <rect x="20.5" y="9" width="3" height="14" rx="1.5" />
        <rect x="26" y="12" width="3" height="8" rx="1.5" />
      </svg>
    </span>
  );
}
