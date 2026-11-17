import { cx } from "../lib/cx";

export function Button({ primary, className = "", children, ...props }) {
  return (
    <button
      type="button"
      className={cx(
        "inline-flex cursor-pointer items-center justify-center gap-2 rounded-2xl px-6 py-3.5 text-base font-semibold transition duration-150",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        "disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100",
        primary
          ? "bg-accent text-white hover:bg-accent-deep active:scale-[0.98]"
          : "border border-line bg-card text-ink hover:bg-white",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function ErrorNote({ children }) {
  if (!children) return null;
  return (
    <p role="alert" className="text-sm font-semibold text-bad">
      {children}
    </p>
  );
}

export function StepHead({ kicker, title, lede }) {
  return (
    <header className="max-w-3xl">
      <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-accent">{kicker}</p>
      <h1 className="mt-2 font-display text-[44px] leading-[1.08] text-balance text-ink">{title}</h1>
      {lede ? <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted">{lede}</p> : null}
    </header>
  );
}

export function CheckIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2.6" aria-hidden="true">
      <path d="M5 12.5 9.2 17 19 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
