"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import type { Channel } from "@/types/database";
import { formatNumber } from "@/lib/data";

interface ChannelFilterProps {
  channels: Channel[];
  selectedChannelIds: string[];
}

export function ChannelFilter({ channels, selectedChannelIds }: ChannelFilterProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleChannelClick = (channelId: string) => {
    const params = new URLSearchParams(searchParams.toString());
    const currentChannels = params.get("channels")?.split(",").filter(Boolean) || [];

    let newChannels: string[];
    if (currentChannels.includes(channelId)) {
      // Remove channel
      newChannels = currentChannels.filter(id => id !== channelId);
    } else {
      // Add channel
      newChannels = [...currentChannels, channelId];
    }

    if (newChannels.length > 0) {
      params.set("channels", newChannels.join(","));
    } else {
      params.delete("channels");
    }
    router.push(`?${params.toString()}`);
  };

  const handleSelectAll = () => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("channels");
    router.push(`?${params.toString()}`);
  };

  const isAllSelected = selectedChannelIds.length === 0;

  return (
    <div className="flex flex-wrap gap-2">
      <Badge
        variant={isAllSelected ? "default" : "outline"}
        className="cursor-pointer hover:bg-primary/80"
        onClick={handleSelectAll}
      >
        All Channels
      </Badge>
      {channels.map((channel) => (
        <Badge
          key={channel.channel_id}
          variant={selectedChannelIds.includes(channel.channel_id) ? "default" : "outline"}
          className="cursor-pointer hover:bg-primary/80"
          onClick={() => handleChannelClick(channel.channel_id)}
        >
          {channel.channel_name}
          <span className="ml-1 opacity-60">
            {formatNumber(channel.subscriber_count || 0)}
          </span>
        </Badge>
      ))}
    </div>
  );
}
