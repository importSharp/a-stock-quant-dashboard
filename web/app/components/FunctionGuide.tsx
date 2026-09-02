export type GuideItem = {
  title: string;
  watch: string;
  purpose: string;
  impact: string;
};

export function FunctionGuide({ eyebrow, title, summary, items }: { eyebrow: string; title: string; summary: string; items: GuideItem[] }) {
  return <section className="function-guide">
    <header><span className="asd-kicker">{eyebrow}</span><h2>{title}</h2><p>{summary}</p></header>
    <div>{items.map((item, index) => <article key={item.title}>
      <span>{String(index + 1).padStart(2, "0")}</span>
      <h3>{item.title}</h3>
      <dl><div><dt>看什么</dt><dd>{item.watch}</dd></div><div><dt>有什么用</dt><dd>{item.purpose}</dd></div><div><dt>如何影响建议</dt><dd>{item.impact}</dd></div></dl>
    </article>)}</div>
  </section>;
}
