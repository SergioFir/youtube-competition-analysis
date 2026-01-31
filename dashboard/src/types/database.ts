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
  status: "active" | "fading" | "inactive";
  first_detected_at: string;
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

// Channel Discovery Types
export interface DiscoverySettings {
  min_subscribers: number;
  max_subscribers: number;
  min_videos: number;
  min_channel_age_days: number;
  exclude_kids_content: boolean;
  country_filter: string[] | null;
  activity_check: boolean;
  max_days_since_upload: number;
}

export interface ChannelSuggestion {
  id: number;
  bucket_id: string;
  channel_id: string;
  channel_name: string;
  subscriber_count: number | null;
  video_count: number | null;
  channel_created_at: string | null;
  thumbnail_url: string | null;
  country: string | null;
  matched_keywords: string[];
  status: 'pending' | 'accepted' | 'declined';
  suggested_at: string;
  responded_at: string | null;
}

export interface DiscoveryResult {
  keywords_used: string[];
  channels_found: number;
  channels_filtered: number;
  suggestions_saved: number;
  filter_stats: Record<string, number>;
  error?: string;
}
