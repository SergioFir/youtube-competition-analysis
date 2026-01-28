"use client";

import { useState } from "react";
import Image from "next/image";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getSnapshotByWindow, formatNumber } from "@/lib/data";
import type { TrendingTopic, Video, Channel, Snapshot, ChannelBaseline } from "@/types/database";
import { ChevronDown, ChevronUp, Flame, Users, Video as VideoIcon, TrendingUp, ExternalLink } from "lucide-react";

interface TrendCardProps {
  trend: TrendingTopic;
  videos: (Video & { channel: Channel; snapshots: Snapshot[] })[];
  baselines: ChannelBaseline[];
}

export function TrendCard({ trend, videos, baselines }: TrendCardProps) {
  const [expanded, setExpanded] = useState(false);

  const topicName = trend.topic_clusters?.normalized_name || "Unknown Topic";

  // Calculate performance for each video
  const videosWithPerformance = videos.map(video => {
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

  // Get unique channels
  const uniqueChannels = [...new Set(videos.map(v => v.channel?.channel_name))].filter(Boolean);

  // Performance color
  const getPerformanceColor = (ratio: number | null) => {
    if (!ratio) return "text-muted-foreground";
    if (ratio >= 3) return "text-green-500";
    if (ratio >= 2) return "text-emerald-500";
    if (ratio >= 1.5) return "text-blue-500";
    return "text-muted-foreground";
  };

  return (
    <Card className="overflow-hidden">
      <CardHeader className="bg-gradient-to-r from-orange-500/10 to-red-500/10 border-b">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Flame className="h-5 w-5 text-orange-500" />
              <CardTitle className="text-xl capitalize">{topicName}</CardTitle>
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Users className="h-4 w-4" />
                {trend.channel_count} channels
              </span>
              <span className="flex items-center gap-1">
                <VideoIcon className="h-4 w-4" />
                {trend.video_count} videos
              </span>
              <span className="flex items-center gap-1">
                <TrendingUp className="h-4 w-4" />
                {trend.avg_performance?.toFixed(1)}x avg performance
              </span>
            </div>
          </div>
          <Badge variant="secondary" className="bg-orange-500/20 text-orange-700 border-orange-500/30">
            Trending
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="p-4">
        {/* Channels involved */}
        <div className="mb-4">
          <h4 className="text-sm font-medium text-muted-foreground mb-2">Channels covering this topic:</h4>
          <div className="flex flex-wrap gap-2">
            {uniqueChannels.map(name => (
              <Badge key={name} variant="outline" className="text-xs">
                {name}
              </Badge>
            ))}
          </div>
        </div>

        {/* Toggle videos */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(!expanded)}
          className="w-full justify-between"
        >
          <span>{expanded ? "Hide" : "Show"} videos</span>
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </Button>

        {/* Videos list */}
        {expanded && (
          <div className="mt-4 space-y-3">
            {videosWithPerformance.map(video => (
              <a
                key={video.video_id}
                href={`https://youtube.com/watch?v=${video.video_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors group"
              >
                {/* Thumbnail */}
                <div className="relative w-32 h-18 flex-shrink-0 rounded overflow-hidden bg-muted">
                  <Image
                    src={`https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg`}
                    alt={video.title || "Video thumbnail"}
                    fill
                    className="object-cover"
                  />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <h5 className="font-medium text-sm line-clamp-2 group-hover:text-primary transition-colors">
                      {video.title}
                    </h5>
                    <ExternalLink className="h-4 w-4 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {video.channel?.channel_name}
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-xs">
                    <span>{formatNumber(video.snapshot24h?.views || 0)} views</span>
                    {video.performance && (
                      <span className={`font-semibold ${getPerformanceColor(video.performance)}`}>
                        {video.performance.toFixed(1)}x
                      </span>
                    )}
                  </div>
                </div>
              </a>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
