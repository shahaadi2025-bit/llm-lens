import type { ReactNode } from "react";

/** A small, safe Markdown renderer for reports: headings, paragraphs, lists, tables, quotes, code fences, **bold**, `code`.
 *  It builds React elements only (never raw HTML), so hostile text inside a report cannot inject markup or scripts. */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("**")) out.push(<strong key={k++}>{t.slice(2, -2)}</strong>);
    else if (t.startsWith("`")) out.push(<code key={k++} className="rounded bg-bench px-1 text-[0.85em]">{t.slice(1, -1)}</code>);
    else out.push(<em key={k++}>{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const cells = (line: string) => line.replace(/^\||\|$/g, "").split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));

export function Markdown({ source }: { source: string }) {
  const lines = source.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (line.startsWith("```")) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) body.push(lines[i++]);
      i++;
      blocks.push(<pre key={key++} className="overflow-x-auto rounded bg-bench p-3 text-xs">{body.join("\n")}</pre>);
    } else if (/^#{1,3} /.test(line)) {
      const level = line.match(/^#+/)![0].length;
      const text = line.replace(/^#+ /, "");
      const cls = level === 1 ? "text-3xl font-semibold" : level === 2 ? "mt-6 text-xl font-semibold" : "mt-4 text-lg font-semibold";
      blocks.push(level === 1 ? <h1 key={key++} className={cls}>{inline(text)}</h1> : level === 2 ? <h2 key={key++} className={cls}>{inline(text)}</h2> : <h3 key={key++} className={cls}>{inline(text)}</h3>);
      i++;
    } else if (line.startsWith("|") && lines[i + 1]?.startsWith("|---")) {
      const head = cells(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) rows.push(cells(lines[i++]));
      blocks.push(
        <div key={key++} className="overflow-x-auto">
          <table className="my-2 w-full min-w-[28rem] text-left text-sm">
            <thead className="border-b border-rule text-ink-faint"><tr>{head.map((h, j) => <th key={j} className="py-1 pr-3">{inline(h)}</th>)}</tr></thead>
            <tbody className="divide-y divide-rule align-top">{rows.map((r, a) => <tr key={a}>{r.map((c, j) => <td key={j} className="py-1 pr-3">{inline(c)}</td>)}</tr>)}</tbody>
          </table>
        </div>,
      );
    } else if (line.startsWith("> ")) {
      const q: string[] = [];
      while (i < lines.length && lines[i].startsWith("> ")) q.push(lines[i++].slice(2));
      blocks.push(<blockquote key={key++} className="my-3 rounded bg-demo-wash p-3 text-sm text-demo">{inline(q.join(" "))}</blockquote>);
    } else if (/^- /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^- /.test(lines[i])) items.push(lines[i++].slice(2));
      blocks.push(<ul key={key++} className="my-2 list-disc space-y-1 pl-5 text-sm">{items.map((t, j) => <li key={j}>{inline(t)}</li>)}</ul>);
    } else {
      const p: string[] = [];
      while (i < lines.length && lines[i].trim() && !/^(#{1,3} |\||> |- |```)/.test(lines[i])) p.push(lines[i++]);
      if (!p.length) { p.push(line); i++; }
      blocks.push(<p key={key++} className="my-2 text-sm leading-relaxed">{inline(p.join(" "))}</p>);
    }
  }
  return <article>{blocks}</article>;
}
