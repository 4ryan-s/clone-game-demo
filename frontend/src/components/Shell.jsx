import { Logo } from "./Logo";
import { CheckIcon } from "./ui";
import { cx } from "../lib/cx";

const ROUNDS = [
  { id: "consent", n: "01", label: "Briefing" },
  { id: "record", n: "02", label: "Your line" },
  { id: "making", n: "03", label: "The copies" },
  { id: "game", n: "04", label: "The question" },
  { id: "result", n: "05", label: "Reward" },
];

export function Shell({ phase, children }) {
  const current = ROUNDS.findIndex((round) => round.id === phase);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-paper text-ink">
      <aside className="flex w-[300px] shrink-0 flex-col border-r border-line bg-mist px-7 py-8">
        <div className="flex items-center gap-3">
          <Logo />
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent">Listening quiz</p>
            <p className="font-display text-[26px] leading-none">Real or Clone?</p>
          </div>
        </div>

        <nav className="mt-10" aria-label="Quiz progress">
          <ol className="relative flex flex-col gap-1">
            <span className="absolute bottom-4 left-[15px] top-4 w-px bg-line" aria-hidden="true" />
            {ROUNDS.map((round, index) => {
              const past = index < current;
              const on = index === current;
              return (
                <li key={round.id} className="relative" aria-current={on ? "step" : undefined}>
                  <div className={cx(
                    "flex items-center gap-3 rounded-2xl px-1.5 py-2.5 transition-colors",
                    on && "bg-card shadow-[0_8px_24px_-18px_rgba(40,30,10,0.7)]",
                  )}>
                    <span className={cx(
                      "relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-semibold",
                      past && "bg-good text-white",
                      on && "bg-accent text-white",
                      !past && !on && "bg-card text-muted ring-1 ring-line",
                    )}>
                      {past ? <CheckIcon className="h-4 w-4" /> : round.n}
                    </span>
                    <span>
                      <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">Round {round.n}</span>
                      <span className={cx("block text-[15px]", on ? "font-semibold text-ink" : "text-muted")}>{round.label}</span>
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>
        </nav>

        <p className="mt-auto text-sm leading-relaxed text-muted">
          One sentence. A handful of copies. Can you hear which voice is yours?
        </p>
      </aside>

      <div className="stage relative min-w-0 flex-1">
        <main className="flex h-full min-h-0 flex-col overflow-auto p-8 xl:p-10">
          <div key={phase} className="rise flex min-h-0 w-full flex-1 flex-col">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
