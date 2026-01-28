"use client";

import { useMemo } from "react";
import type { TrendingTopic } from "@/types/database";

interface TrendBubblesProps {
  trends: TrendingTopic[];
}

// Generate consistent random color based on topic name
function getColorForTopic(name: string): string {
  const colors = [
    "bg-red-500",
    "bg-orange-500",
    "bg-amber-500",
    "bg-yellow-500",
    "bg-lime-500",
    "bg-green-500",
    "bg-emerald-500",
    "bg-teal-500",
    "bg-cyan-500",
    "bg-sky-500",
    "bg-blue-500",
    "bg-indigo-500",
    "bg-violet-500",
    "bg-purple-500",
    "bg-fuchsia-500",
    "bg-pink-500",
    "bg-rose-500",
  ];

  // Hash the name to get a consistent index
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }

  return colors[Math.abs(hash) % colors.length];
}

function getBubbleSize(trend: TrendingTopic): number {
  // Calculate a score based on multiple factors
  const channelScore = trend.channel_count * 20;
  const videoScore = trend.video_count * 10;
  const performanceScore = (trend.avg_performance || 1) * 15;

  const totalScore = channelScore + videoScore + performanceScore;

  // Map to pixel size (min 80px, max 200px)
  const minSize = 80;
  const maxSize = 200;
  const size = Math.min(maxSize, Math.max(minSize, totalScore));

  return size;
}

export function TrendBubbles({ trends }: TrendBubblesProps) {
  const bubblesData = useMemo(() => {
    return trends.map(trend => {
      const name = trend.topic_clusters?.normalized_name || "Unknown";
      return {
        trend,
        name,
        size: getBubbleSize(trend),
        color: getColorForTopic(name),
      };
    }).sort((a, b) => b.size - a.size); // Largest first
  }, [trends]);

  if (trends.length === 0) {
    return null;
  }

  return (
    <div className="relative w-full min-h-[250px] flex flex-wrap items-center justify-center gap-4 p-4">
      {bubblesData.map(({ trend, name, size, color }) => (
        <div
          key={trend.id}
          className={`
            ${color}
            rounded-full
            flex items-center justify-center
            text-white font-semibold
            shadow-lg
            hover:scale-110 hover:shadow-xl
            transition-all duration-300
            p-3
            group
          `}
          style={{
            width: size,
            height: size,
          }}
        >
          <div className="text-center">
            <div className="text-xs opacity-0 group-hover:opacity-80 transition-opacity mb-1">
              {trend.channel_count} ch / {trend.video_count} vid
            </div>
            <div
              className="font-bold leading-tight capitalize"
              style={{
                fontSize: Math.max(10, Math.min(14, size / 9)),
              }}
            >
              {name.length > 20 ? name.slice(0, 18) + "..." : name}
            </div>
            <div className="text-xs opacity-0 group-hover:opacity-80 transition-opacity mt-1">
              {trend.avg_performance?.toFixed(1)}x
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
