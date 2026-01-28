import { Suspense } from "react";
import Link from "next/link";
import {
  getLatestTrendingTopics,
  getVideosByIds,
  getAllBaselines,
  getSnapshotByWindow,
} from "@/lib/data";
import { TrendCard } from "@/components/trend-card";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function TrendsPage() {
  const [trends, baselines] = await Promise.all([
    getLatestTrendingTopics(),
    getAllBaselines(),
  ]);

  // Fetch videos for all trends
  const allVideoIds = trends.flatMap(t => t.video_ids || []);
  const uniqueVideoIds = [...new Set(allVideoIds)];
  const allVideos = await getVideosByIds(uniqueVideoIds);

  // Create a map for quick lookup
  const videoMap = new Map(allVideos.map(v => [v.video_id, v]));

  // Enrich trends with video data
  const trendsWithVideos = trends.map(trend => ({
    ...trend,
    videos: (trend.video_ids || [])
      .map(id => videoMap.get(id))
      .filter(Boolean)
  }));

  const latestDetection = trends[0]?.detected_at
    ? new Date(trends[0].detected_at).toLocaleString()
    : "Never";

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center gap-4 mb-2">
            <Link href="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Videos
              </Button>
            </Link>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Trending Topics</h1>
              <p className="text-muted-foreground">
                Topics performing well across multiple channels
              </p>
            </div>
            <div className="text-right text-sm text-muted-foreground">
              <p>Last detection: {latestDetection}</p>
              <p>{trends.length} trending topic{trends.length !== 1 ? "s" : ""} found</p>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        {/* Trend Rules Explanation */}
        <div className="mb-6 p-4 bg-muted/50 rounded-lg border">
          <h3 className="font-semibold mb-2">How trends are detected:</h3>
          <ul className="text-sm text-muted-foreground space-y-1">
            <li>- Topic must appear in videos from <strong>3+ different channels</strong></li>
            <li>- Only counts videos performing <strong>1.5x+ above baseline</strong></li>
            <li>- Looking at videos from the <strong>last 14 days</strong></li>
          </ul>
        </div>

        {/* Trends List */}
        {trends.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">🔍</div>
            <h2 className="text-xl font-semibold mb-2">No Trending Topics Yet</h2>
            <p className="text-muted-foreground max-w-md mx-auto">
              Trends are detected when 3+ channels post about the same topic
              and those videos perform above 1.5x their baseline.
              Keep tracking videos and check back later!
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {trendsWithVideos.map((trend) => (
              <TrendCard
                key={trend.id}
                trend={trend}
                videos={trend.videos as any}
                baselines={baselines}
              />
            ))}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t mt-12">
        <div className="container mx-auto px-4 py-6 text-center text-sm text-muted-foreground">
          <p>
            Topics are extracted using AI from video titles and transcripts.
            Similar topics are clustered together automatically.
          </p>
        </div>
      </footer>
    </div>
  );
}
