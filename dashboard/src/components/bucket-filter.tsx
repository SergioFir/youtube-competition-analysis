"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import type { Bucket, BucketChannel } from "@/types/database";

interface BucketFilterProps {
  buckets: Bucket[];
  bucketChannels: BucketChannel[];
  selectedBucketId: string | null;
}

export function BucketFilter({ buckets, bucketChannels, selectedBucketId }: BucketFilterProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleBucketClick = (bucketId: string | null) => {
    const params = new URLSearchParams(searchParams.toString());

    // Clear channel filter when selecting a bucket
    params.delete("channels");

    if (bucketId) {
      params.set("bucket", bucketId);
    } else {
      params.delete("bucket");
    }
    router.push(`?${params.toString()}`);
  };

  const getChannelCount = (bucketId: string) => {
    return bucketChannels.filter(bc => bc.bucket_id === bucketId).length;
  };

  if (buckets.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-lg">
        <p className="text-lg">No buckets created yet</p>
        <p className="text-sm mt-1">Use "Manage Buckets" to create your first bucket</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
      {/* All Buckets Card */}
      <Card
        className={`p-4 cursor-pointer transition-all hover:scale-105 ${
          selectedBucketId === null
            ? "ring-2 ring-primary bg-primary/10"
            : "hover:bg-muted/50"
        }`}
        onClick={() => handleBucketClick(null)}
      >
        <div className="flex flex-col items-center text-center gap-2">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-primary/50 flex items-center justify-center">
            <span className="text-lg">✦</span>
          </div>
          <div>
            <p className="font-semibold">All</p>
            <p className="text-xs text-muted-foreground">
              {bucketChannels.length > 0
                ? `${new Set(bucketChannels.map(bc => bc.channel_id)).size} channels`
                : "All channels"
              }
            </p>
          </div>
        </div>
      </Card>

      {/* Bucket Cards */}
      {buckets.map((bucket) => {
        const channelCount = getChannelCount(bucket.id);
        const isSelected = selectedBucketId === bucket.id;

        return (
          <Card
            key={bucket.id}
            className={`p-4 cursor-pointer transition-all hover:scale-105 ${
              isSelected
                ? "bg-opacity-20"
                : "hover:bg-muted/50"
            }`}
            style={{
              borderColor: bucket.color || undefined,
              boxShadow: isSelected ? `0 0 0 2px ${bucket.color}` : undefined,
              backgroundColor: isSelected ? `${bucket.color}20` : undefined,
            }}
            onClick={() => handleBucketClick(bucket.id)}
          >
            <div className="flex flex-col items-center text-center gap-2">
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-lg"
                style={{ backgroundColor: bucket.color || "#6366f1" }}
              >
                {bucket.name.charAt(0).toUpperCase()}
              </div>
              <div>
                <p className="font-semibold truncate max-w-[100px]" title={bucket.name}>
                  {bucket.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {channelCount} {channelCount === 1 ? "channel" : "channels"}
                </p>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
