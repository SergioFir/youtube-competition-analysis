"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import type { Bucket, BucketChannel, Channel } from "@/types/database";
import {
  createBucket,
  deleteBucket,
  addChannelToBucket,
  removeChannelFromBucket,
} from "@/lib/data";

interface BucketManagerProps {
  buckets: Bucket[];
  bucketChannels: BucketChannel[];
  channels: Channel[];
}

const COLORS = [
  "#ef4444", // red
  "#f97316", // orange
  "#eab308", // yellow
  "#22c55e", // green
  "#06b6d4", // cyan
  "#3b82f6", // blue
  "#8b5cf6", // violet
  "#ec4899", // pink
];

export function BucketManager({ buckets, bucketChannels, channels }: BucketManagerProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [newBucketName, setNewBucketName] = useState("");
  const [newBucketColor, setNewBucketColor] = useState(COLORS[0]);
  const [selectedBucket, setSelectedBucket] = useState<Bucket | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleCreateBucket = async () => {
    if (!newBucketName.trim()) return;

    setIsLoading(true);
    const bucket = await createBucket(newBucketName.trim(), newBucketColor);
    setIsLoading(false);

    if (bucket) {
      setNewBucketName("");
      router.refresh();
    }
  };

  const handleDeleteBucket = async (bucketId: string) => {
    if (!confirm("Delete this bucket? Channels won't be deleted.")) return;

    setIsLoading(true);
    await deleteBucket(bucketId);
    setIsLoading(false);

    if (selectedBucket?.id === bucketId) {
      setSelectedBucket(null);
    }
    router.refresh();
  };

  const handleToggleChannel = async (channelId: string) => {
    if (!selectedBucket) return;

    const isInBucket = bucketChannels.some(
      bc => bc.bucket_id === selectedBucket.id && bc.channel_id === channelId
    );

    setIsLoading(true);
    if (isInBucket) {
      await removeChannelFromBucket(selectedBucket.id, channelId);
    } else {
      await addChannelToBucket(selectedBucket.id, channelId);
    }
    setIsLoading(false);
    router.refresh();
  };

  const getChannelsInBucket = (bucketId: string) => {
    const channelIds = bucketChannels
      .filter(bc => bc.bucket_id === bucketId)
      .map(bc => bc.channel_id);
    return channels.filter(c => channelIds.includes(c.channel_id));
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Manage Buckets
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Manage Buckets</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Create new bucket */}
          <div className="space-y-3">
            <Label>Create New Bucket</Label>
            <div className="flex gap-2">
              <Input
                placeholder="Bucket name (e.g., AI Channels)"
                value={newBucketName}
                onChange={(e) => setNewBucketName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateBucket()}
              />
              <div className="flex gap-1">
                {COLORS.map((color) => (
                  <button
                    key={color}
                    className={`w-6 h-6 rounded-full border-2 ${
                      newBucketColor === color ? "border-white" : "border-transparent"
                    }`}
                    style={{ backgroundColor: color }}
                    onClick={() => setNewBucketColor(color)}
                  />
                ))}
              </div>
              <Button onClick={handleCreateBucket} disabled={isLoading || !newBucketName.trim()}>
                Create
              </Button>
            </div>
          </div>

          <Separator />

          {/* Existing buckets */}
          <div className="space-y-3">
            <Label>Your Buckets</Label>
            {buckets.length === 0 ? (
              <p className="text-sm text-muted-foreground">No buckets yet.</p>
            ) : (
              <div className="space-y-2">
                {buckets.map((bucket) => (
                  <div
                    key={bucket.id}
                    className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedBucket?.id === bucket.id
                        ? "border-primary bg-muted"
                        : "hover:bg-muted/50"
                    }`}
                    onClick={() => setSelectedBucket(
                      selectedBucket?.id === bucket.id ? null : bucket
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: bucket.color || "#6366f1" }}
                        />
                        <span className="font-medium">{bucket.name}</span>
                        <span className="text-sm text-muted-foreground">
                          ({getChannelsInBucket(bucket.id).length} channels)
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteBucket(bucket.id);
                        }}
                      >
                        Delete
                      </Button>
                    </div>

                    {selectedBucket?.id === bucket.id && (
                      <div className="mt-3 pt-3 border-t">
                        <p className="text-sm text-muted-foreground mb-2">
                          Click channels to add/remove:
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {channels.map((channel) => {
                            const isInBucket = bucketChannels.some(
                              bc => bc.bucket_id === bucket.id && bc.channel_id === channel.channel_id
                            );
                            return (
                              <Badge
                                key={channel.channel_id}
                                variant={isInBucket ? "default" : "outline"}
                                className="cursor-pointer"
                                style={{
                                  backgroundColor: isInBucket ? bucket.color || undefined : undefined,
                                }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleToggleChannel(channel.channel_id);
                                }}
                              >
                                {channel.channel_name}
                              </Badge>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
