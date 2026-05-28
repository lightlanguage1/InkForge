import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { Spinner } from "../components/ui/Spinner";
import { compile, summarize, generateTitles } from "../api/compile";

export function CompilePage() {
  const { id } = useParams<{ id: string }>();
  const [format, setFormat] = useState("markdown");
  const [content, setContent] = useState("");
  const [titles, setTitles] = useState<string[]>([]);

  const compileMut = useMutation({ mutationFn: () => compile(id!, { format }), onSuccess: (d) => setContent(d.content) });
  const summaryMut = useMutation({ mutationFn: () => summarize(id!), onSuccess: (d) => setContent(d.content) });
  const titleMut = useMutation({ mutationFn: () => generateTitles(id!, { count: 10 }), onSuccess: (d) => setTitles(d.titles) });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-zinc-900 tracking-tight">Compile / Export</h1>
      <Card className="p-4">
        <div className="flex gap-3 items-end">
          <Select label="Format" value={format} onChange={setFormat}
            options={[{ value: "markdown", label: "Markdown" }, { value: "html", label: "HTML" }, { value: "prose", label: "Prose" }]} />
          <Button onClick={() => compileMut.mutate()} loading={compileMut.isPending}>Compile</Button>
          <Button variant="ghost" onClick={() => summaryMut.mutate()} loading={summaryMut.isPending}>Summary</Button>
          <Button variant="ghost" onClick={() => titleMut.mutate()} loading={titleMut.isPending}>Titles</Button>
        </div>
      </Card>

      {titles.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-2">Title Suggestions</h3>
          <div className="grid grid-cols-2 gap-1">
            {titles.map((t, i) => <p key={i} className="text-sm text-zinc-700">{i + 1}. {t}</p>)}
          </div>
        </Card>
      )}

      {(compileMut.isPending || summaryMut.isPending) ? <Spinner /> : (
        content && (
          <Card className="p-4">
            <div className="flex justify-between mb-2">
              <h3 className="font-semibold">Output</h3>
              <Button variant="ghost" size="sm" onClick={() => navigator.clipboard.writeText(content)}>Copy</Button>
            </div>
            <pre className="text-sm whitespace-pre-wrap bg-zinc-50 border border-zinc-100 p-4 rounded-lg max-h-96 overflow-auto text-zinc-700">{content}</pre>
          </Card>
        )
      )}
    </div>
  );
}
