import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

interface SectionProps {
  title: string;
  description?: string;
  defaultOpen?: boolean;
  icon?: ReactNode;
  trailing?: ReactNode;
  children: ReactNode;
}

export function Section({
  title,
  description,
  defaultOpen = true,
  icon,
  trailing,
  children,
}: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-line bg-mutedPanel/40">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 rounded-t-lg px-3 py-2 text-left transition hover:bg-mutedPanel/70"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-text">
          <ChevronDown
            size={14}
            className={`text-muted transition-transform ${open ? "rotate-0" : "-rotate-90"}`}
          />
          {icon}
          {title}
        </span>
        {trailing}
      </button>
      {open ? (
        <div className="grid gap-3 px-3 pb-3">
          {description ? <p className="text-[11px] leading-4 text-muted">{description}</p> : null}
          {children}
        </div>
      ) : null}
    </div>
  );
}
