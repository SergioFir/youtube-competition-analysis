"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { LayoutGrid, Flame } from "lucide-react";

interface ViewToggleProps {
  currentView: "videos" | "trends";
  hasTrends: boolean;
}

export function ViewToggle({ currentView, hasTrends }: ViewToggleProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleToggle = (view: "videos" | "trends") => {
    const params = new URLSearchParams(searchParams.toString());
    if (view === "videos") {
      params.delete("view");
    } else {
      params.set("view", view);
    }
    router.push(`?${params.toString()}`);
  };

  return (
    <div className="inline-flex rounded-lg border bg-muted p-1">
      <button
        onClick={() => handleToggle("videos")}
        className={`
          flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all
          ${currentView === "videos"
            ? "bg-background shadow-sm text-foreground"
            : "text-muted-foreground hover:text-foreground"
          }
        `}
      >
        <LayoutGrid className="h-4 w-4" />
        Videos
      </button>
      <button
        onClick={() => handleToggle("trends")}
        className={`
          flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all
          ${currentView === "trends"
            ? "bg-background shadow-sm text-foreground"
            : "text-muted-foreground hover:text-foreground"
          }
          ${hasTrends ? "" : "opacity-50"}
        `}
      >
        <Flame className={`h-4 w-4 ${currentView === "trends" ? "text-orange-500" : ""}`} />
        Trends
        {hasTrends && (
          <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-orange-500/20 text-orange-600">
            !
          </span>
        )}
      </button>
    </div>
  );
}
