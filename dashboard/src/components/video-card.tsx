"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Video, Snapshot, Channel, ChannelBaseline } from "@/types/database";
import { getSnapshotByWindow, calculatePerformance, formatNumber, formatTimeAgo } from "@/lib/data";

interface VideoCardProps {
  video: Video & { channel?: Channel; snapshots: Snapshot[] };
  baselines: ChannelBaseline[];
}

export function VideoCard({ video, baselines }: VideoCardProps) {
  const thumbnail = `https://i.ytimg.com/vi/${video.video_id}/mqdefault.jpg`;

  // Get snapshots for different windows
  const snapshot24h = getSnapshotByWindow(video.snapshots, "24h");
  const snapshot1h = getSnapshotByWindow(video.snapshots, "1h");
  const snapshot48h = getSnapshotByWindow(video.snapshots, "48h");

  // Get baseline for this video type (short vs long)
  const baseline24h = baselines.find(
    b => b.channel_id === video.channel_id &&
         b.is_short === video.is_short &&
         b.window_type === "24h"
  );

  // Calculate performance vs baseline
  const performance = snapshot24h && baseline24h?.median_views
    ? calculatePerformance(snapshot24h.views, baseline24h.median_views)
    : null;

  const isEstimatedBaseline = baseline24h?.source === "manual";

  return (
    <Card className="overflow-hidden hover:border-primary/50 transition-colors">
      <a
        href={`https://youtube.com/watch?v=${video.video_id}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        <div className="relative aspect-video">
          <img
            src={thumbnail}
            alt={video.title || "Video thumbnail"}
            className="object-cover w-full h-full"
          />
          {video.is_short && (
            <Badge className="absolute top-2 left-2 bg-red-600">Short</Badge>
          )}
          {performance && (
            <Badge
              className={`absolute top-2 right-2 ${
                performance.ratio >= 2
                  ? "bg-green-600"
                  : performance.ratio >= 1.2
                  ? "bg-green-500"
                  : performance.ratio >= 0.8
                  ? "bg-yellow-500"
                  : "bg-red-500"
              }`}
            >
              {performance.ratio.toFixed(1)}x
            </Badge>
          )}
        </div>
      </a>
      <CardContent className="p-3">
        <h3 className="font-medium text-sm line-clamp-2 mb-2" title={video.title || undefined}>
          {video.title || "Untitled"}
        </h3>

        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
          <span>{video.channel?.channel_name || "Unknown"}</span>
          <span>•</span>
          <span>{formatTimeAgo(video.published_at)}</span>
        </div>

        {/* Metrics Row */}
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="text-center p-1 bg-muted rounded">
            <div className="text-muted-foreground">1h</div>
            <div className="font-medium">
              {snapshot1h ? formatNumber(snapshot1h.views) : "-"}
            </div>
          </div>
          <div className="text-center p-1 bg-muted rounded">
            <div className="text-muted-foreground">24h</div>
            <div className="font-medium">
              {snapshot24h ? formatNumber(snapshot24h.views) : "-"}
            </div>
          </div>
          <div className="text-center p-1 bg-muted rounded">
            <div className="text-muted-foreground">48h</div>
            <div className="font-medium">
              {snapshot48h ? formatNumber(snapshot48h.views) : "-"}
            </div>
          </div>
        </div>

        {/* Baseline comparison */}
        {baseline24h && (
          <div className="mt-2 text-xs text-muted-foreground flex items-center gap-1">
            <span>Baseline: {formatNumber(baseline24h.median_views || 0)}</span>
            {isEstimatedBaseline && (
              <Badge variant="outline" className="text-[10px] px-1 py-0">
                Est
              </Badge>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
