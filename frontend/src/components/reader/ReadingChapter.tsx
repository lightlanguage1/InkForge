import { useState } from "react";
import { ReadScene } from "../../api/community";
import { CommentBubble } from "../community/CommentBubble";
import { QuickComment } from "../community/QuickComment";

export function ReadingChapter({ scene, comments, projectId, onCommented, fontSize, theme }: {
  scene: ReadScene; comments: any[]; projectId: string; onCommented: () => void;
  fontSize?: number; theme?: string;
}) {
  const [activePara, setActivePara] = useState<number | null>(null);
  const topComments = comments.filter((c: any) => !c.parent_id);
  const paraComments = (p: number) => topComments.filter((c: any) => c.paragraph === p);
  const fs = fontSize || 15;
  const isDark = theme === "dark" || theme === "custom";
  const textColor = theme === "light" ? "#3a3228" : theme === "sepia" ? "#4a3f2a" : "#b0a590";
  const titleColor = theme === "light" ? "#4a4030" : theme === "sepia" ? "#5a4a30" : "#b0a080";
  const accentColor = theme === "light" ? "#a06828" : theme === "sepia" ? "#8a5820" : "#b89860";

  return (
    <div className="mb-12">
      <h3 className="text-lg font-semibold mb-6 text-center"
        style={{ color: titleColor, fontFamily: "'Cormorant Garamond', serif", letterSpacing: "0.03em" }}>
        {scene.title || `第 ${scene.tick} 章`}
      </h3>
      <div className="space-y-0">
        {scene.paragraphs.map((para, pi) => {
          const pc = paraComments(pi);
          const isActive = activePara === pi;
          return (
            <div key={pi} className="group relative">
              <p onClick={() => setActivePara(isActive ? null : pi)}
                className="cursor-pointer transition-colors rounded px-2 py-1.5 -mx-2"
                style={{ fontSize: fs, lineHeight: 2.2, color: textColor, textIndent: "2em", fontFamily: "'Georgia', 'Noto Serif SC', serif",
                  background: isActive ? (isDark ? "rgba(200,151,90,0.04)" : "rgba(180,130,60,0.06)") : "transparent" }}>
                {pc.length > 0 && (
                  <span className="inline-flex items-center mr-1.5 px-1.5 py-0.5 rounded-full text-[10px] align-middle"
                    style={{ background: isDark ? "rgba(200,151,90,0.12)" : "rgba(180,130,60,0.08)", color: accentColor, cursor: "pointer", textIndent: 0 }}>
                    💬{pc.length}
                  </span>
                )}
                {para}
              </p>
              {isActive && (
                <div className="ml-4 my-1 pl-4" style={{ borderLeft: "2px solid rgba(200,151,90,0.15)" }}>
                  {pc.map((c: any) => (
                    <CommentBubble key={c.id} comment={c} onUpdated={onCommented} />
                  ))}
                  <QuickComment tick={scene.tick} paragraph={pi} projectId={projectId}
                    onSent={() => { setActivePara(null); onCommented(); }} placeholder="评论此段落…" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
