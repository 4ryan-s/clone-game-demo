import { Logo } from "./Logo";
import { Button } from "./ui";

export function ByeStep({ title, text, onRestart }) {
  return (
    <div className="stage grid h-screen w-screen place-items-center bg-paper px-6">
      <div className="rise max-w-xl text-center">
        <Logo className="mx-auto h-16 w-16" />
        <p className="mt-6 text-[12px] font-semibold uppercase tracking-[0.18em] text-accent">That's a wrap</p>
        <h1 className="mt-2 font-display text-6xl">{title}</h1>
        <p className="mt-4 text-lg leading-relaxed text-muted">{text}</p>
        <Button primary className="mt-8" onClick={onRestart}>Start again</Button>
      </div>
    </div>
  );
}
