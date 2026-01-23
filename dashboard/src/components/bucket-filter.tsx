"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
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
      <p className="text-sm text-muted-foreground">
        No buckets created yet. Use the manage button to create one.
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Badge
        variant={selectedBucketId === null ? "default" : "outline"}
        className="cursor-pointer hover:bg-primary/80"
        onClick={() => handleBucketClick(null)}
      >
        All Buckets
      </Badge>
      {buckets.map((bucket) => (
        <Badge
          key={bucket.id}
          variant={selectedBucketId === bucket.id ? "default" : "outline"}
          className="cursor-pointer hover:bg-primary/80"
          style={{
            backgroundColor: selectedBucketId === bucket.id ? bucket.color || undefined : undefined,
            borderColor: bucket.color || undefined,
          }}
          onClick={() => handleBucketClick(bucket.id)}
        >
          {bucket.name}
          <span className="ml-1 opacity-60">
            ({getChannelCount(bucket.id)})
          </span>
        </Badge>
      ))}
    </div>
  );
}
