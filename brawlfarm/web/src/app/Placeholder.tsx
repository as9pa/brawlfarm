/** A page that is not built yet: its name, and one sentence saying when it arrives. */
export interface PlaceholderProps {
  title: string;
  body: string;
}

export function Placeholder({ title, body }: PlaceholderProps) {
  return (
    <section className="max-w-[560px]">
      <h1 className="text-[28px] font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 text-[13px] text-muted">{body}</p>
    </section>
  );
}
