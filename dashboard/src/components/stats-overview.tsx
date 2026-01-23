import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Channel, Video } from "@/types/database";

interface StatsOverviewProps {
  channels: Channel[];
  videos: Video[];
}

export function StatsOverview({ channels, videos }: StatsOverviewProps) {
  const activeVideos = videos.filter(v => v.tracking_status === "active").length;
  const totalSubscribers = channels.reduce((sum, ch) => sum + (ch.subscriber_count || 0), 0);

  const stats = [
    {
      title: "Tracked Channels",
      value: channels.length,
    },
    {
      title: "Total Subscribers",
      value: totalSubscribers >= 1_000_000
        ? `${(totalSubscribers / 1_000_000).toFixed(1)}M`
        : `${(totalSubscribers / 1_000).toFixed(0)}K`,
    },
    {
      title: "Videos Discovered",
      value: videos.length,
    },
    {
      title: "Active Tracking",
      value: activeVideos,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map((stat) => (
        <Card key={stat.title}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {stat.title}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stat.value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
