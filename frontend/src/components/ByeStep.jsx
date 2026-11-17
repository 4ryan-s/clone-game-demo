import { Logo } from "./Logo";
import { Button } from "./ui";

export function ByeStep({ title, text, onRestart }) {
  return (
    <div className="stage grid h-screen w-screen place-items-center bg-paper px-[5.5cm]">
      <div className="rise max-w-xl text-center">
        <Logo className="mx-auto h-16 w-16" />
        <h1 className="mt-6 font-display text-5xl">{title}</h1>
        <p className="mt-3 text-muted">{text}</p>
        <Button primary className="mt-8" onClick={onRestart}>Start again</Button>
      </div>
    </div>
  );
}
