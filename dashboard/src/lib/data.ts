import { supabase } from "./supabase";
import type { Channel, Video, Snapshot, ChannelBaseline, Bucket, BucketChannel, TrendingTopic, TrendingTopicWithDetails } from "@/types/database";

export async function getChannels(): Promise<Channel[]> {
  const { data, error } = await supabase
    .from("channels")
    .select("*")
    .eq("is_active", true)
    .order("subscriber_count", { ascending: false });

  if (error) {
    console.error("Error fetching channels:", error);
    return [];
  }

  return data || [];
}

export async function getRecentVideos(days: number = 30): Promise<(Video & { channel: Channel; snapshots: Snapshot[] })[]> {
  // Calculate cutoff date
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);

  const { data, error } = await supabase
    .from("videos")
    .select(`
      *,
      channel:channels(*),
      snapshots(*)
    `)
    .eq("is_short", false)  // Exclude shorts
    .gte("published_at", cutoff.toISOString())
    .order("published_at", { ascending: false });

  if (error) {
    console.error("Error fetching videos:", error);
    return [];
  }

  return (data || []) as (Video & { channel: Channel; snapshots: Snapshot[] })[];
}

export async function getChannelVideos(channelId: string, limit: number = 20): Promise<(Video & { snapshots: Snapshot[] })[]> {
  const { data, error } = await supabase
    .from("videos")
    .select(`
      *,
      snapshots(*)
    `)
    .eq("channel_id", channelId)
    .order("published_at", { ascending: false })
    .limit(limit);

  if (error) {
    console.error("Error fetching channel videos:", error);
    return [];
  }

  return (data || []) as (Video & { snapshots: Snapshot[] })[];
}

export async function getChannelBaselines(channelId: string): Promise<ChannelBaseline[]> {
  const { data, error } = await supabase
    .from("channel_baselines")
    .select("*")
    .eq("channel_id", channelId);

  if (error) {
    console.error("Error fetching baselines:", error);
    return [];
  }

  return data || [];
}

export async function getAllBaselines(): Promise<ChannelBaseline[]> {
  const { data, error } = await supabase
    .from("channel_baselines")
    .select("*");

  if (error) {
    console.error("Error fetching all baselines:", error);
    return [];
  }

  return data || [];
}

export function getSnapshotByWindow(snapshots: Snapshot[], windowType: string): Snapshot | undefined {
  return snapshots.find(s => s.window_type === windowType);
}

export function calculatePerformance(views: number, baseline: number | null): { ratio: number; label: string } | null {
  if (!baseline || baseline === 0) return null;

  const ratio = views / baseline;

  let label: string;
  if (ratio >= 2) {
    label = `${ratio.toFixed(1)}x above`;
  } else if (ratio >= 1.2) {
    label = `${ratio.toFixed(1)}x above`;
  } else if (ratio >= 0.8) {
    label = "average";
  } else {
    label = `${ratio.toFixed(1)}x below`;
  }

  return { ratio, label };
}

export function formatNumber(num: number): string {
  if (num >= 1_000_000) {
    return (num / 1_000_000).toFixed(1) + "M";
  }
  if (num >= 1_000) {
    return (num / 1_000).toFixed(1) + "K";
  }
  return num.toString();
}

export function formatTimeAgo(date: string): string {
  const now = new Date();
  const then = new Date(date);
  const diffMs = now.getTime() - then.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffHours < 1) {
    return "just now";
  }
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }
  if (diffDays < 7) {
    return `${diffDays}d ago`;
  }
  return then.toLocaleDateString();
}

// Bucket functions
export async function getBuckets(): Promise<Bucket[]> {
  const { data, error } = await supabase
    .from("buckets")
    .select("*")
    .order("name");

  if (error) {
    console.error("Error fetching buckets:", error);
    return [];
  }

  return data || [];
}

export async function getBucketChannels(): Promise<BucketChannel[]> {
  const { data, error } = await supabase
    .from("bucket_channels")
    .select("*");

  if (error) {
    console.error("Error fetching bucket channels:", error);
    return [];
  }

  return data || [];
}

export async function createBucket(name: string, color: string = "#6366f1"): Promise<Bucket | null> {
  const { data, error } = await supabase
    .from("buckets")
    .insert({ name, color } as any)
    .select()
    .single();

  if (error) {
    console.error("Error creating bucket:", error);
    return null;
  }

  return data;
}

export async function deleteBucket(bucketId: string): Promise<boolean> {
  const { error } = await supabase
    .from("buckets")
    .delete()
    .eq("id", bucketId);

  if (error) {
    console.error("Error deleting bucket:", error);
    return false;
  }

  return true;
}

export async function addChannelToBucket(bucketId: string, channelId: string): Promise<boolean> {
  const { error } = await supabase
    .from("bucket_channels")
    .insert({ bucket_id: bucketId, channel_id: channelId } as any);

  if (error) {
    console.error("Error adding channel to bucket:", error);
    return false;
  }

  return true;
}

export async function removeChannelFromBucket(bucketId: string, channelId: string): Promise<boolean> {
  const { error } = await supabase
    .from("bucket_channels")
    .delete()
    .eq("bucket_id", bucketId)
    .eq("channel_id", channelId);

  if (error) {
    console.error("Error removing channel from bucket:", error);
    return false;
  }

  return true;
}

export function getChannelIdsForBucket(bucketId: string, bucketChannels: BucketChannel[]): string[] {
  return bucketChannels
    .filter(bc => bc.bucket_id === bucketId)
    .map(bc => bc.channel_id);
}

// Trending Topics functions
export async function getTrendingTopics(): Promise<TrendingTopic[]> {
  const { data, error } = await supabase
    .from("trending_topics")
    .select(`
      *,
      topic_clusters(*)
    `)
    .order("detected_at", { ascending: false })
    .limit(50);

  if (error) {
    console.error("Error fetching trending topics:", error);
    return [];
  }

  return data || [];
}

export async function getLatestTrendingTopics(): Promise<TrendingTopic[]> {
  // Get only the most recent detection run
  const { data: latestRun, error: latestError } = await supabase
    .from("trending_topics")
    .select("detected_at")
    .order("detected_at", { ascending: false })
    .limit(1)
    .single();

  if (latestError || !latestRun) {
    // No trends yet or error
    if (latestError?.code !== "PGRST116") {
      console.error("Error fetching latest trend run:", latestError);
    }
    return [];
  }

  const detectedAt = (latestRun as { detected_at: string }).detected_at;

  const { data, error } = await supabase
    .from("trending_topics")
    .select(`
      *,
      topic_clusters(*)
    `)
    .eq("detected_at", detectedAt)
    .order("channel_count", { ascending: false });

  if (error) {
    console.error("Error fetching trending topics:", error);
    return [];
  }

  return data || [];
}

export async function getTrendingTopicWithVideos(trendId: number): Promise<TrendingTopicWithDetails | null> {
  // Get the trend
  const { data: trendData, error: trendError } = await supabase
    .from("trending_topics")
    .select(`
      *,
      topic_clusters(*)
    `)
    .eq("id", trendId)
    .single();

  if (trendError || !trendData) {
    console.error("Error fetching trend:", trendError);
    return null;
  }

  const trend = trendData as TrendingTopic;

  // Get the videos
  if (!trend.video_ids || trend.video_ids.length === 0) {
    return { ...trend, videos: [] };
  }

  const { data: videos, error: videosError } = await supabase
    .from("videos")
    .select(`
      *,
      channel:channels(*),
      snapshots(*)
    `)
    .in("video_id", trend.video_ids);

  if (videosError) {
    console.error("Error fetching trend videos:", videosError);
    return { ...trend, videos: [] };
  }

  return {
    ...trend,
    videos: videos as (Video & { channel: Channel; snapshots: Snapshot[] })[]
  };
}

export async function getVideosByIds(videoIds: string[]): Promise<(Video & { channel: Channel; snapshots: Snapshot[] })[]> {
  if (!videoIds || videoIds.length === 0) return [];

  const { data, error } = await supabase
    .from("videos")
    .select(`
      *,
      channel:channels(*),
      snapshots(*)
    `)
    .in("video_id", videoIds);

  if (error) {
    console.error("Error fetching videos by ids:", error);
    return [];
  }

  return (data || []) as (Video & { channel: Channel; snapshots: Snapshot[] })[];
}

export async function getTrendsForBucket(bucketId: string): Promise<TrendingTopic[]> {
  const { data, error } = await supabase
    .from("trending_topics")
    .select(`
      *,
      topic_clusters(*)
    `)
    .eq("bucket_id", bucketId)
    .order("channel_count", { ascending: false });

  if (error) {
    console.error("Error fetching trends for bucket:", error);
    return [];
  }

  return (data || []) as TrendingTopic[];
}
