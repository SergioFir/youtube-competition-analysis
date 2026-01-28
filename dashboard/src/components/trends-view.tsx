"use client";

import { useState } from "react";
import Image from "next/image";
import { TrendBubbles } from "@/components/trend-bubbles";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getSnapshotByWindow, formatNumber } from "@/lib/data";
import type { TrendingTopic, Video, Channel, Snapshot, ChannelBaseline } from "@/types/database";
import { Flame, Users, TrendingUp, Video as VideoIcon, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";

interface TrendsViewProps {
  trends: TrendingTopic[];
  videos: (Video & { channel: Channel; snapshots: Snapshot[] })[];
  baselines: ChannelBaseline[];
  bucketName?: string;
}

// Generate consistent random color based on topic name
function getColorForTopic(name: string): string {
  const colors = [
    "bg-red-500",
    "bg-orange-500",
    "bg-amber-500",
    "bg-lime-500",
    "bg-emerald-500",
    "bg-cyan-500",
    "bg-blue-500",
    "bg-indigo-500",
    "bg-violet-500",
    "bg-pink-500",
  ];

  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }

  return colors[Math.abs(hash) % colors.length];
}

function TrendCardItem({
  trend,
  videos,
  baselines
}: {
  trend: TrendingTopic & { videos: (Video & { channel: Channel; snapshots: Snapshot[] })[] };
  videos: (Video & { channel: Channel; snapshots: Snapshot[] })[];
  baselines: ChannelBaseline[];
}) {
  const [expanded, setExpanded] = useState(false);
  const name = trend.topic_clusters?.normalized_name || "Unknown";
  const color = getColorForTopic(name);

  // Get unique channels
  const uniqueChannels = [...new Set(trend.videos.map(v => v.channel?.channel_name))].filter(Boolean);

  // Calculate performance for videos
  const videosWithPerformance = trend.videos.map(video => {
    const snapshot24h = getSnapshotByWindow(video.snapshots, "24h");
    const baseline = baselines.find(
      b => b.channel_id === video.channel_id &&
           b.is_short === video.is_short &&
           b.window_type === "24h"
    );
    const performance = snapshot24h && baseline?.median_views
      ? snapshot24h.views / baseline.median_views
      : null;
    return { ...video, snapshot24h, performance };
  }).sort((a, b) => (b.performance || 0) - (a.performance || 0));

  return (
    <Card className="overflow-hidden hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          {/* Color indicator */}
          <div className={`w-3 h-3 rounded-full ${color} mt-1.5 flex-shrink-0`} />

          <div className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="font-semibold capitalize text-base">{name}</h3>
                <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Users className="h-3.5 w-3.5" />
                    {trend.channel_count} channels
                  </span>
                  <span className="flex items-center gap-1">
                    <VideoIcon className="h-3.5 w-3.5" />
                    {trend.video_count} videos
                  </span>
                  <span className="flex items-center gap-1">
                    <TrendingUp className="h-3.5 w-3.5" />
                    {trend.avg_performance?.toFixed(1)}x avg
                  </span>
                </div>
              </div>
              <Badge variant="secondary" className="bg-orange-500/10 text-orange-600 border-orange-500/20 flex-shrink-0">
                <Flame className="h-3 w-3 mr-1" />
                Trending
              </Badge>
            </div>

            {/* Channels */}
            <div className="flex flex-wrap gap-1.5 mt-3">
              {uniqueChannels.map(ch => (
                <Badge key={ch} variant="outline" className="text-xs font-normal">
                  {ch}
                </Badge>
              ))}
            </div>

            {/* Expand/Collapse */}
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mt-3 transition-colors"
            >
              {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              {expanded ? "Hide videos" : "Show videos"}
            </button>

            {/* Videos list */}
            {expanded && (
              <div className="mt-3 space-y-2 pt-3 border-t">
                {videosWithPerformance.map(video => (
                  <a
                    key={video.video_id}
                    href={`https://youtube.com/watch?v=${video.video_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors group"
                  >
                    <div className="relative w-24 h-14 flex-shrink-0 rounded overflow-hidden bg-muted">
                      <Image
                        src={`https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg`}
                        alt={video.title || "Video"}
                        fill
                        className="object-cover"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h5 className="text-sm font-medium line-clamp-1 group-hover:text-primary transition-colors">
                        {video.title}
                      </h5>
                      <p className="text-xs text-muted-foreground">{video.channel?.channel_name}</p>
                      <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
                        <span>{formatNumber(video.snapshot24h?.views || 0)} views</span>
                        {video.performance && (
                          <span className={`font-semibold ${video.performance >= 2 ? "text-green-500" : "text-blue-500"}`}>
                            {video.performance.toFixed(1)}x
                          </span>
                        )}
                      </div>
                    </div>
                    <ExternalLink className="h-4 w-4 opacity-0 group-hover:opacity-50 transition-opacity flex-shrink-0" />
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function TrendsView({ trends, videos, baselines, bucketName }: TrendsViewProps) {
  // Create video lookup
  const videoMap = new Map(videos.map(v => [v.video_id, v]));

  // Enrich trends with video data
  const trendsWithVideos = trends.map(trend => ({
    ...trend,
    videos: (trend.video_ids || [])
      .map(id => videoMap.get(id))
      .filter(Boolean) as (Video & { channel: Channel; snapshots: Snapshot[] })[]
  }));

  if (trends.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="text-6xl mb-4">🔍</div>
        <h2 className="text-xl font-semibold mb-2">No Trends Found</h2>
        <p className="text-muted-foreground max-w-md mx-auto">
          {bucketName ? (
            <>
              No trending topics detected for <strong>{bucketName}</strong> channels yet.
              Trends appear when 2+ channels post about the same topic with above-average performance.
            </>
          ) : (
            <>
              Select a bucket to see trends for those channels.
              Trends appear when 2+ channels post about the same topic.
            </>
          )}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Bubble Visualization */}
      <div className="rounded-xl bg-gradient-to-br from-slate-900 to-slate-800 border border-slate-700 overflow-hidden">
        <div className="p-4 border-b border-slate-700">
          <h2 className="text-lg font-semibold text-white">
            Topic Heatmap
            {bucketName && (
              <span className="font-normal text-slate-400 ml-2">
                for {bucketName}
              </span>
            )}
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Hover over bubbles to see details
          </p>
        </div>
        <TrendBubbles trends={trends} />
      </div>

      {/* Trend Cards */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">
          Trending Topics
          <span className="font-normal text-muted-foreground ml-2">
            ({trends.length} topic{trends.length !== 1 ? "s" : ""})
          </span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {trendsWithVideos.map((trend) => (
            <TrendCardItem
              key={trend.id}
              trend={trend}
              videos={videos}
              baselines={baselines}
            />
          ))}
        </div>
      </div>

      {/* How it works */}
      <div className="p-4 bg-muted/50 rounded-lg border">
        <h3 className="font-semibold mb-2 text-sm">How trends are detected:</h3>
        <ul className="text-xs text-muted-foreground space-y-1">
          <li>- Topic must appear in videos from <strong>2+ different channels</strong> in this bucket</li>
          <li>- Only counts videos performing <strong>1.5x+ above baseline</strong></li>
          <li>- Looking at videos from the <strong>last 14 days</strong></li>
        </ul>
      </div>
    </div>
  );
}
