import type { PropsWithChildren, ReactNode } from "react";

type SectionPanelProps = PropsWithChildren<{
  title: string;
  subtitle: string;
  aside?: ReactNode;
}>;

export function SectionPanel({ title, subtitle, aside, children }: SectionPanelProps) {
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        {aside ? <div className="panel-aside">{aside}</div> : null}
      </header>
      {children}
    </section>
  );
}
