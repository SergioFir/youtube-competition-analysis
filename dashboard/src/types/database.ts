export interface Database {
  public: {
    Tables: {
      channels: {
        Row: {
          channel_id: string;
          channel_name: string;
          subscriber_count: number | null;
          total_videos: number | null;
          created_at: string;
          last_checked_at: string | null;
          is_active: boolean;
        };
        Insert: {
          channel_id: string;
          channel_name: string;
          subscriber_count?: number | null;
          total_videos?: number | null;
          created_at?: string;
          last_checked_at?: string | null;
          is_active?: boolean;
        };
      };
      buckets: {
        Row: {
          id: string;
          name: string;
          color: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          name: string;
          color?: string | null;
          created_at?: string;
        };
      };
      bucket_channels: {
        Row: {
          bucket_id: string;
          channel_id: string;
        };
        Insert: {
          bucket_id: string;
          channel_id: string;
        };
      };
      videos: {
        Row: {
          video_id: string;
          channel_id: string;
          published_at: string;
          discovered_at: string;
          title: string | null;
          duration_seconds: number | null;
          is_short: boolean | null;
          tracking_status: string;
          tracking_until: string | null;
        };
      };
      snapshots: {
        Row: {
          id: number;
          video_id: string;
          captured_at: string;
          window_type: string;
          views: number;
          likes: number;
          comments: number;
        };
      };
      channel_baselines: {
        Row: {
          channel_id: string;
          is_short: boolean;
          window_type: string;
          median_views: number | null;
          median_likes: number | null;
          median_comments: number | null;
          sample_size: number | null;
          source: string | null;
          updated_at: string | null;
        };
      };
    };
  };
}

export type Channel = Database["public"]["Tables"]["channels"]["Row"];
export type Video = Database["public"]["Tables"]["videos"]["Row"];
export type Snapshot = Database["public"]["Tables"]["snapshots"]["Row"];
export type ChannelBaseline = Database["public"]["Tables"]["channel_baselines"]["Row"];
export type Bucket = Database["public"]["Tables"]["buckets"]["Row"];
export type BucketChannel = Database["public"]["Tables"]["bucket_channels"]["Row"];

export interface VideoWithSnapshots extends Video {
  snapshots: Snapshot[];
  channel?: Channel;
}

export interface ChannelWithBaselines extends Channel {
  baselines: ChannelBaseline[];
}

// Trend Detection Types
export interface TopicCluster {
  id: string;
  normalized_name: string;
  created_at: string;
  updated_at: string;
}

export interface TrendingTopic {
  id: number;
  cluster_id: string;
  channel_count: number;
  video_count: number;
  avg_performance: number | null;
  video_ids: string[];
  detected_at: string;
  period_start: string;
  period_end: string;
  topic_clusters?: TopicCluster;
}

export interface VideoTopic {
  id: number;
  video_id: string;
  topic: string;
  extracted_at: string;
}

export interface TrendingTopicWithDetails extends TrendingTopic {
  videos: (Video & { channel: Channel; snapshots: Snapshot[] })[];
}
