import { Suspense } from "react";
import {
  getChannels,
  getRecentVideos,
  getAllBaselines,
  getSnapshotByWindow,
  getBuckets,
  getBucketChannels,
  getChannelIdsForBucket,
  getTrendsForChannels,
  getVideosByIds,
} from "@/lib/data";
import { VideoCard } from "@/components/video-card";
import { ChannelFilter } from "@/components/channel-filter";
import { PerformanceFilter } from "@/components/performance-filter";
import { BucketFilter } from "@/components/bucket-filter";
import { BucketManager } from "@/components/bucket-manager";
import { AddChannelDialog } from "@/components/add-channel-dialog";
import { StatsOverview } from "@/components/stats-overview";
import { ViewToggle } from "@/components/view-toggle";
import { TrendsView } from "@/components/trends-view";
import { Separator } from "@/components/ui/separator";
import type { Video, Snapshot, ChannelBaseline } from "@/types/database";

interface PageProps {
  searchParams: Promise<{ channels?: string; performance?: string; bucket?: string; view?: string }>;
}

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getVideoPerformanceRatio(
  video: Video & { snapshots: Snapshot[] },
  baselines: ChannelBaseline[]
): number | null {
  const snapshot24h = getSnapshotByWindow(video.snapshots, "24h");
  if (!snapshot24h) return null;

  const baseline = baselines.find(
    b => b.channel_id === video.channel_id &&
         b.is_short === video.is_short &&
         b.window_type === "24h"
  );

  if (!baseline?.median_views || baseline.median_views === 0) return null;

  return snapshot24h.views / baseline.median_views;
}

export default async function Home({ searchParams }: PageProps) {
  const params = await searchParams;
  const selectedChannelIds = params.channels?.split(",").filter(Boolean) || [];
  const performanceFilter = params.performance || "all";
  const selectedBucketId = params.bucket || null;
  const currentView = (params.view === "trends" ? "trends" : "videos") as "videos" | "trends";

  const [channels, allVideos, baselines, buckets, bucketChannels] = await Promise.all([
    getChannels(),
    getRecentVideos(30),  // Last 30 days, no shorts
    getAllBaselines(),
    getBuckets(),
    getBucketChannels(),
  ]);

  // Determine which channel IDs to filter by
  let filterChannelIds: string[] = [];
  let selectedBucket = null;

  if (selectedBucketId) {
    filterChannelIds = getChannelIdsForBucket(selectedBucketId, bucketChannels);
    selectedBucket = buckets.find(b => b.id === selectedBucketId);
  } else if (selectedChannelIds.length > 0) {
    filterChannelIds = selectedChannelIds;
  }

  // Filter videos by channels
  let videos = filterChannelIds.length > 0
    ? allVideos.filter(v => filterChannelIds.includes(v.channel_id))
    : allVideos;

  // Filter by performance
  if (performanceFilter !== "all") {
    videos = videos.filter(video => {
      const ratio = getVideoPerformanceRatio(video, baselines);
      if (ratio === null) return false;

      switch (performanceFilter) {
        case "above":
          return ratio >= 1;
        case "hits":
          return ratio >= 2;
        case "below":
          return ratio < 1;
        default:
          return true;
      }
    });
  }

  // Get trends for selected channels (only when in trends view or to check if trends exist)
  const trends = filterChannelIds.length > 0
    ? await getTrendsForChannels(filterChannelIds)
    : [];

  // Get videos for trends if in trends view
  let trendVideos: (Video & { channel: typeof channels[0]; snapshots: Snapshot[] })[] = [];
  if (currentView === "trends" && trends.length > 0) {
    const trendVideoIds = [...new Set(trends.flatMap(t => t.video_ids || []))];
    trendVideos = await getVideosByIds(trendVideoIds);
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">YouTube Competition Analysis</h1>
            <p className="text-muted-foreground">
              Track competitor videos and detect breakout content
            </p>
          </div>
          <AddChannelDialog buckets={buckets} />
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Stats Overview */}
        <StatsOverview channels={channels} videos={allVideos} />

        <Separator />

        {/* Buckets Section */}
        <div className="rounded-xl bg-gradient-to-r from-muted/50 to-muted/30 p-6 border">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold">Your Buckets</h2>
              <p className="text-sm text-muted-foreground">Group channels by category</p>
            </div>
            <BucketManager
              buckets={buckets}
              bucketChannels={bucketChannels}
              channels={channels}
            />
          </div>
          <Suspense fallback={<div>Loading...</div>}>
            <BucketFilter
              buckets={buckets}
              bucketChannels={bucketChannels}
              selectedBucketId={selectedBucketId}
            />
          </Suspense>
        </div>

        {/* View Toggle + Filters */}
        <div className="flex flex-wrap items-start gap-6">
          {/* View Toggle */}
          <div>
            <h2 className="text-sm font-semibold mb-2 text-muted-foreground uppercase tracking-wide">View</h2>
            <Suspense fallback={<div>Loading...</div>}>
              <ViewToggle currentView={currentView} hasTrends={trends.length > 0} />
            </Suspense>
          </div>

          {/* Channels (only show when no bucket selected and videos view) */}
          {!selectedBucketId && currentView === "videos" && (
            <div className="flex-1 min-w-[200px]">
              <h2 className="text-sm font-semibold mb-2 text-muted-foreground uppercase tracking-wide">Channels</h2>
              <Suspense fallback={<div>Loading...</div>}>
                <ChannelFilter
                  channels={channels}
                  selectedChannelIds={selectedChannelIds}
                />
              </Suspense>
            </div>
          )}

          {/* Performance (only in videos view) */}
          {currentView === "videos" && (
            <div className="flex-1 min-w-[200px]">
              <h2 className="text-sm font-semibold mb-2 text-muted-foreground uppercase tracking-wide">Performance</h2>
              <Suspense fallback={<div>Loading...</div>}>
                <PerformanceFilter currentFilter={performanceFilter} />
              </Suspense>
            </div>
          )}
        </div>

        <Separator />

        {/* Content Area - Videos or Trends */}
        {currentView === "videos" ? (
          /* Video Grid */
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">
                Recent Videos
                <span className="font-normal text-muted-foreground ml-2">
                  ({videos.length} videos)
                </span>
              </h2>
            </div>

            {videos.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <p>No videos match the current filters.</p>
                <p className="text-sm mt-1">
                  Try adjusting your filters or wait for more data to be collected.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                {videos.map((video) => (
                  <VideoCard
                    key={video.video_id}
                    video={video}
                    baselines={baselines}
                  />
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Trends View */
          <TrendsView
            trends={trends}
            videos={trendVideos}
            baselines={baselines}
            bucketName={selectedBucket?.name}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t mt-12">
        <div className="container mx-auto px-4 py-6 text-center text-sm text-muted-foreground">
          <p>
            Baselines marked with <span className="font-mono bg-muted px-1 rounded">Est</span> are estimated from VidIQ data.
            Real baselines will replace them as the system collects data.
          </p>
        </div>
      </footer>
    </div>
  );
}
