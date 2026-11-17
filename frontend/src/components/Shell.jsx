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
    <div className="stage flex h-screen w-screen flex-col overflow-hidden bg-paper text-ink">
      <header className="flex shrink-0 items-center justify-center gap-8 px-[5.5cm] pt-8">
        <div className="flex items-center gap-3">
          <Logo className="h-10 w-10" />
          <p className="font-display text-2xl leading-none">Real or Clone?</p>
        </div>
        <nav className="flex items-center gap-3" aria-label="Quiz progress">
          <ol className="flex items-center gap-2">
            {ROUNDS.map((item, index) => {
              const past = index < current;
              const on = index === current;
              return (
                <li key={item.id} aria-current={on ? "step" : undefined}>
                  <span className={cx(
                    "block h-2.5 w-2.5 rounded-full",
                    past && "bg-good",
                    on && "bg-accent",
                    !past && !on && "bg-line",
                  )} />
                  <span className="sr-only">{item.label}</span>
                </li>
              );
            })}
          </ol>
          <p className="text-sm font-semibold text-muted">{round.label}</p>
        </nav>
      </header>

      <main className="mx-auto flex min-h-0 w-full flex-1 flex-col overflow-auto px-[5.5cm] py-8">
        <div key={phase} className="rise flex min-h-0 w-full flex-1 flex-col">
          {children}
        </div>
      </main>
    </div>
  );
}
