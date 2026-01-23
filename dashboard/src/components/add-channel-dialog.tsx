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
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Bucket } from "@/types/database";
import { addChannel, resolveChannelPreview } from "@/lib/actions";
import { formatNumber } from "@/lib/data";

interface AddChannelDialogProps {
  buckets: Bucket[];
}

interface ChannelPreview {
  channel_id: string;
  channel_name: string;
  subscriber_count: number;
  total_videos: number;
}

export function AddChannelDialog({ buckets }: AddChannelDialogProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [channelUrl, setChannelUrl] = useState("");
  const [vph, setVph] = useState("");
  const [selectedBucketId, setSelectedBucketId] = useState<string | null>(null);
  const [preview, setPreview] = useState<ChannelPreview | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleResolve = async () => {
    if (!channelUrl.trim()) return;

    setIsResolving(true);
    setError(null);
    setPreview(null);

    const result = await resolveChannelPreview(channelUrl);

    setIsResolving(false);

    if (result) {
      setPreview(result);
    } else {
      setError("Could not find channel. Check the URL or handle.");
    }
  };

  const handleSubmit = async () => {
    if (!preview || !vph) return;

    setIsLoading(true);
    setError(null);

    const result = await addChannel(
      channelUrl,
      parseFloat(vph),
      selectedBucketId || undefined
    );

    setIsLoading(false);

    if (result.success) {
      // Reset form
      setChannelUrl("");
      setVph("");
      setSelectedBucketId(null);
      setPreview(null);
      setOpen(false);
      router.refresh();
    } else {
      setError(result.error || "Failed to add channel");
    }
  };

  const handleClose = (isOpen: boolean) => {
    setOpen(isOpen);
    if (!isOpen) {
      // Reset on close
      setChannelUrl("");
      setVph("");
      setSelectedBucketId(null);
      setPreview(null);
      setError(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogTrigger asChild>
        <Button>Add Channel</Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add New Channel</DialogTitle>
          <DialogDescription>
            Add a YouTube channel to track. Enter the channel URL and estimated views per hour.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Channel URL */}
          <div className="space-y-2">
            <Label htmlFor="channel-url">Channel URL or @handle</Label>
            <div className="flex gap-2">
              <Input
                id="channel-url"
                placeholder="@channelname or youtube.com/@..."
                value={channelUrl}
                onChange={(e) => {
                  setChannelUrl(e.target.value);
                  setPreview(null);
                  setError(null);
                }}
                onKeyDown={(e) => e.key === "Enter" && handleResolve()}
              />
              <Button
                variant="outline"
                onClick={handleResolve}
                disabled={isResolving || !channelUrl.trim()}
              >
                {isResolving ? "..." : "Find"}
              </Button>
            </div>
          </div>

          {/* Preview */}
          {preview && (
            <div className="p-3 bg-muted rounded-lg">
              <div className="font-medium">{preview.channel_name}</div>
              <div className="text-sm text-muted-foreground">
                {formatNumber(preview.subscriber_count)} subscribers • {formatNumber(preview.total_videos)} videos
              </div>
            </div>
          )}

          {/* VPH Input */}
          {preview && (
            <div className="space-y-2">
              <Label htmlFor="vph">
                Median Views Per Hour (VPH)
                <span className="text-muted-foreground font-normal ml-1">
                  (from VidIQ or similar)
                </span>
              </Label>
              <Input
                id="vph"
                type="number"
                placeholder="e.g., 50"
                value={vph}
                onChange={(e) => setVph(e.target.value)}
              />
              {vph && (
                <p className="text-xs text-muted-foreground">
                  Estimated 24h views: {formatNumber(Math.round(parseFloat(vph) * 24))}
                </p>
              )}
            </div>
          )}

          {/* Bucket Selection */}
          {preview && buckets.length > 0 && (
            <div className="space-y-2">
              <Label>Add to Bucket (optional)</Label>
              <div className="flex flex-wrap gap-2">
                <Badge
                  variant={selectedBucketId === null ? "default" : "outline"}
                  className="cursor-pointer"
                  onClick={() => setSelectedBucketId(null)}
                >
                  None
                </Badge>
                {buckets.map((bucket) => (
                  <Badge
                    key={bucket.id}
                    variant={selectedBucketId === bucket.id ? "default" : "outline"}
                    className="cursor-pointer"
                    style={{
                      backgroundColor: selectedBucketId === bucket.id ? bucket.color || undefined : undefined,
                      borderColor: bucket.color || undefined,
                    }}
                    onClick={() => setSelectedBucketId(bucket.id)}
                  >
                    {bucket.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          {/* Submit */}
          <Button
            className="w-full"
            onClick={handleSubmit}
            disabled={isLoading || !preview || !vph}
          >
            {isLoading ? "Adding..." : "Add Channel"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
