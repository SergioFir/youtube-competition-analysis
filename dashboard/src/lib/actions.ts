"use server";

import { supabase } from "./supabase";
import type { Bucket } from "@/types/database";

const YOUTUBE_API_KEY = process.env.YOUTUBE_API_KEY;

interface ChannelInfo {
  channel_id: string;
  channel_name: string;
  subscriber_count: number;
  total_videos: number;
}

// Parse YouTube channel URL to extract identifier
function parseChannelUrl(url: string): { type: string; value: string } | null {
  const trimmed = url.trim();

  // Handle @username format
  if (trimmed.startsWith("@")) {
    return { type: "handle", value: trimmed };
  }

  // Handle full URLs
  try {
    const urlObj = new URL(trimmed.startsWith("http") ? trimmed : `https://${trimmed}`);

    if (urlObj.hostname.includes("youtube.com")) {
      const path = urlObj.pathname;

      // /@username
      if (path.startsWith("/@")) {
        return { type: "handle", value: path.substring(1) };
      }
      // /channel/UCxxxx
      if (path.startsWith("/channel/")) {
        return { type: "channel_id", value: path.replace("/channel/", "").split("/")[0] };
      }
      // /c/CustomName
      if (path.startsWith("/c/")) {
        return { type: "custom", value: path.replace("/c/", "").split("/")[0] };
      }
      // /user/username
      if (path.startsWith("/user/")) {
        return { type: "user", value: path.replace("/user/", "").split("/")[0] };
      }
    }
  } catch {
    // Not a valid URL
  }

  // Assume it's a channel ID if it starts with UC
  if (trimmed.startsWith("UC") && trimmed.length === 24) {
    return { type: "channel_id", value: trimmed };
  }

  // Assume it's a handle without @
  if (!trimmed.includes("/") && !trimmed.includes(".")) {
    return { type: "handle", value: `@${trimmed}` };
  }

  return null;
}

// Resolve channel URL to channel info using YouTube API
async function resolveChannel(url: string): Promise<ChannelInfo | null> {
  if (!YOUTUBE_API_KEY) {
    console.error("YOUTUBE_API_KEY not configured");
    return null;
  }

  const parsed = parseChannelUrl(url);
  if (!parsed) {
    return null;
  }

  let apiUrl: string;

  if (parsed.type === "handle") {
    apiUrl = `https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&forHandle=${encodeURIComponent(parsed.value)}&key=${YOUTUBE_API_KEY}`;
  } else if (parsed.type === "channel_id") {
    apiUrl = `https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&id=${parsed.value}&key=${YOUTUBE_API_KEY}`;
  } else if (parsed.type === "user") {
    apiUrl = `https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&forUsername=${parsed.value}&key=${YOUTUBE_API_KEY}`;
  } else {
    // Custom URL - need to search
    apiUrl = `https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q=${encodeURIComponent(parsed.value)}&maxResults=1&key=${YOUTUBE_API_KEY}`;
  }

  try {
    const response = await fetch(apiUrl);
    const data = await response.json();

    if (parsed.type === "custom" && data.items?.[0]) {
      // For custom URLs, we get a search result, need to fetch channel details
      const channelId = data.items[0].snippet.channelId;
      const channelResponse = await fetch(
        `https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&id=${channelId}&key=${YOUTUBE_API_KEY}`
      );
      const channelData = await channelResponse.json();

      if (channelData.items?.[0]) {
        const channel = channelData.items[0];
        return {
          channel_id: channel.id,
          channel_name: channel.snippet.title,
          subscriber_count: parseInt(channel.statistics.subscriberCount) || 0,
          total_videos: parseInt(channel.statistics.videoCount) || 0,
        };
      }
    } else if (data.items?.[0]) {
      const channel = data.items[0];
      return {
        channel_id: channel.id,
        channel_name: channel.snippet.title,
        subscriber_count: parseInt(channel.statistics.subscriberCount) || 0,
        total_videos: parseInt(channel.statistics.videoCount) || 0,
      };
    }

    return null;
  } catch (error) {
    console.error("Error resolving channel:", error);
    return null;
  }
}

// Convert VPH to baseline views for each window
function vphToWindowViews(vph: number): Record<string, number> {
  return {
    "1h": Math.round(vph * 1),
    "6h": Math.round(vph * 6),
    "24h": Math.round(vph * 24),
    "48h": Math.round(vph * 48),
  };
}

export interface AddChannelResult {
  success: boolean;
  error?: string;
  channel?: ChannelInfo;
}

export async function addChannel(
  channelUrl: string,
  vph: number,
  bucketId?: string
): Promise<AddChannelResult> {
  // Resolve the channel
  const channelInfo = await resolveChannel(channelUrl);

  if (!channelInfo) {
    return { success: false, error: "Could not find channel. Check the URL or handle." };
  }

  // Check if channel already exists
  const { data: existing } = await supabase
    .from("channels")
    .select("channel_id")
    .eq("channel_id", channelInfo.channel_id)
    .single();

  if (existing) {
    return { success: false, error: "Channel already exists." };
  }

  // Add channel
  const { error: channelError } = await supabase
    .from("channels")
    .insert({
      channel_id: channelInfo.channel_id,
      channel_name: channelInfo.channel_name,
      subscriber_count: channelInfo.subscriber_count,
      total_videos: channelInfo.total_videos,
      is_active: true,
    } as any);

  if (channelError) {
    console.error("Error adding channel:", channelError);
    return { success: false, error: "Failed to add channel to database." };
  }

  // Create seed baselines
  const windowViews = vphToWindowViews(vph);

  for (const [windowType, views] of Object.entries(windowViews)) {
    await supabase
      .from("channel_baselines")
      .upsert({
        channel_id: channelInfo.channel_id,
        is_short: false,
        window_type: windowType,
        median_views: views,
        median_likes: null,
        median_comments: null,
        sample_size: 10,
        source: "manual",
      } as any);
  }

  // Add to bucket if specified
  if (bucketId) {
    await supabase
      .from("bucket_channels")
      .insert({
        bucket_id: bucketId,
        channel_id: channelInfo.channel_id,
      } as any);
  }

  return { success: true, channel: channelInfo };
}

export async function resolveChannelPreview(channelUrl: string): Promise<ChannelInfo | null> {
  return resolveChannel(channelUrl);
}
