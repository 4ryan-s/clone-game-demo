import { Logo } from "./Logo";
import { cx } from "../lib/cx";

const ROUNDS = [
  { id: "consent", label: "Agree" },
  { id: "record", label: "Record" },
  { id: "making", label: "Hang on" },
  { id: "game", label: "Pick" },
  { id: "result", label: "Reward" },
];

export function Shell({ phase, children }) {
  const current = ROUNDS.findIndex((round) => round.id === phase);
  const round = ROUNDS[current] || ROUNDS[0];

  return (
    <div className="stage flex h-dvh w-full max-w-full flex-col overflow-hidden bg-paper text-ink">
      <header className="page-gutter flex shrink-0 flex-col items-center gap-3 pt-[max(0.75rem,env(safe-area-inset-top))] sm:gap-3.5 sm:pt-6">
        <div className="flex items-center gap-3">
          <Logo className="h-8 w-8 sm:h-10 sm:w-10" />
          <p className="font-display text-xl leading-none sm:text-2xl">Real or Clone?</p>
        </div>
        <nav className="flex w-full max-w-md items-center gap-3 sm:max-w-lg" aria-label="Quiz progress">
          <ol className="relative flex min-w-0 flex-1 items-center justify-between">
            <span className="absolute left-2 right-2 top-1/2 h-1 -translate-y-1/2 rounded-full bg-[#d9d0c2]" aria-hidden="true" />
            <span
              className="absolute left-2 top-1/2 h-1 -translate-y-1/2 rounded-full bg-good transition-[width] duration-500 ease-out"
              style={{ width: `calc((100% - 1rem) * ${Math.max(current, 0) / (ROUNDS.length - 1)})` }}
              aria-hidden="true"
            />
            {ROUNDS.map((item, index) => {
              const past = index < current;
              const on = index === current;
              return (
                <li key={item.id} className="relative z-10" aria-current={on ? "step" : undefined}>
                  <span className={cx(
                    "block rounded-full border-2 transition duration-300",
                    on ? "h-4 w-4 border-accent bg-accent ring-4 ring-accent/25 sm:h-[1.125rem] sm:w-[1.125rem]" : "h-3.5 w-3.5 sm:h-4 sm:w-4",
                    past && "border-good bg-good",
                    !past && !on && "border-[#c9bead] bg-white",
                  )} />
                  <span className="sr-only">{item.label}</span>
                </li>
              );
            })}
          </ol>
          <p className="shrink-0 text-sm font-semibold text-ink">{round.label}</p>
        </nav>
      </header>

      <main className="w-full min-w-0 flex-1 overflow-y-auto">
        <div key={phase} className="page-gutter rise mx-auto flex min-h-full w-full min-w-0 flex-col justify-center py-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:py-7">
          {children}
        </div>
      </main>
    </div>
  );
}
