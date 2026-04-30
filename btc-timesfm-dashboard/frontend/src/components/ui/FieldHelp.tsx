import { useState } from "react";
import { Info } from "lucide-react";

interface FieldHelpProps {
  text: string;
}

export function FieldHelp({ text }: FieldHelpProps) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-flex items-center">
      <button
        type="button"
        className="text-muted/70 transition hover:text-text focus:text-text focus:outline-none"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setOpen((value) => !value);
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        aria-label="More info"
      >
        <Info size={11} />
      </button>
      {open ? (
        <span
          role="tooltip"
          className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 w-56 -translate-x-1/2 whitespace-normal rounded-md border border-line bg-ink p-2 text-[11px] leading-4 text-muted shadow-glow"
        >
          {text}
        </span>
      ) : null}
    </span>
  );
}
