import { Logo } from "./Logo";
import { Button } from "./ui";

export function Boot({ error, onRetry }) {
  return (
    <div className="stage grid h-screen w-screen place-items-center bg-paper px-6">
      <div className="rise max-w-lg text-center">
        <Logo className="mx-auto h-16 w-16" />
        {error ? (
          <>
            <h1 className="mt-6 font-display text-4xl leading-tight">The demo server is not responding</h1>
            <p className="mt-3 text-lg text-muted">{error}</p>
            <Button primary className="mt-7" onClick={onRetry}>Try again</Button>
          </>
        ) : (
          <>
            <h1 className="mt-6 font-display text-4xl">Setting the stage</h1>
            <p className="mt-3 text-lg text-muted">Getting the quiz ready.</p>
            <div className="mt-5 flex justify-center gap-1.5" aria-hidden="true">
              {[0, 1, 2].map((i) => (
                <span key={i} className="blink h-2 w-2 rounded-full bg-accent" style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
