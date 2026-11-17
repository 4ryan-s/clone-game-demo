import { Logo } from "./Logo";
import { Button } from "./ui";

export function ByeStep({ title, text, onRestart }) {
  return (
    <div className="stage page-gutter grid h-dvh w-full place-items-center overflow-auto bg-paper py-8">
      <div className="rise w-full max-w-xl text-center">
        <Logo className="mx-auto h-14 w-14 sm:h-16 sm:w-16" />
        <h1 className="mt-6 font-display text-4xl sm:text-5xl">{title}</h1>
        <p className="mt-3 text-muted">{text}</p>
        <Button primary className="mt-8" onClick={onRestart}>Start again</Button>
      </div>
    </div>
  );
}
