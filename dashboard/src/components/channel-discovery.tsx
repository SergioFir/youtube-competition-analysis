"use client";

import { useState, useEffect } from "react";
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
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { Bucket, DiscoverySettings, ChannelSuggestion, DiscoveryResult } from "@/types/database";
import {
  getDiscoverySettingsAction,
  saveDiscoverySettingsAction,
  runDiscoveryAction,
  getDiscoveryKeywordsAction,
  acceptSuggestionAction,
  declineSuggestionAction,
  getPendingSuggestionsAction,
} from "@/lib/actions";
import { formatNumber } from "@/lib/data";
import { Search, Settings, Check, X, Loader2, Sparkles } from "lucide-react";

interface ChannelDiscoveryProps {
  bucket: Bucket;
}

const DEFAULT_SETTINGS: DiscoverySettings = {
  min_subscribers: 10000,
  max_subscribers: 5000000,
  min_videos: 20,
  min_channel_age_days: 180,
  exclude_kids_content: true,
  country_filter: null,
  activity_check: false,
  max_days_since_upload: 60,
};

export function ChannelDiscovery({ bucket }: ChannelDiscoveryProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("discover");

  // Settings state
  const [settings, setSettings] = useState<DiscoverySettings>(DEFAULT_SETTINGS);
  const [isSavingSettings, setIsSavingSettings] = useState(false);

  // Discovery state
  const [keywords, setKeywords] = useState<string[]>([]);
  const [customKeyword, setCustomKeyword] = useState("");
  const [isLoadingKeywords, setIsLoadingKeywords] = useState(false);
  const [isRunningDiscovery, setIsRunningDiscovery] = useState(false);
  const [discoveryResult, setDiscoveryResult] = useState<DiscoveryResult | null>(null);

  // Suggestions state
  const [suggestions, setSuggestions] = useState<ChannelSuggestion[]>([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set());

  // Load initial data when dialog opens
  useEffect(() => {
    if (open) {
      loadInitialData();
    }
  }, [open, bucket.id]);

  const loadInitialData = async () => {
    // Load settings
    const loadedSettings = await getDiscoverySettingsAction(bucket.id);
    setSettings(loadedSettings);

    // Load keywords
    setIsLoadingKeywords(true);
    const loadedKeywords = await getDiscoveryKeywordsAction(bucket.id);
    setKeywords(loadedKeywords);
    setIsLoadingKeywords(false);

    // Load pending suggestions
    await loadSuggestions();
  };

  const loadSuggestions = async () => {
    setIsLoadingSuggestions(true);
    const loadedSuggestions = await getPendingSuggestionsAction(bucket.id);
    setSuggestions(loadedSuggestions);
    setIsLoadingSuggestions(false);
  };

  const handleSaveSettings = async () => {
    setIsSavingSettings(true);
    await saveDiscoverySettingsAction(bucket.id, settings);
    setIsSavingSettings(false);
  };

  const handleAddKeyword = () => {
    if (customKeyword.trim() && !keywords.includes(customKeyword.trim())) {
      setKeywords([...keywords, customKeyword.trim()]);
      setCustomKeyword("");
    }
  };

  const handleRemoveKeyword = (keyword: string) => {
    setKeywords(keywords.filter(k => k !== keyword));
  };

  const handleRunDiscovery = async () => {
    if (keywords.length === 0) return;

    setIsRunningDiscovery(true);
    setDiscoveryResult(null);

    const result = await runDiscoveryAction(bucket.id, keywords);
    setDiscoveryResult(result);

    // Reload suggestions
    await loadSuggestions();

    setIsRunningDiscovery(false);

    // Switch to suggestions tab if we found some
    if (result.suggestions_saved > 0) {
      setActiveTab("suggestions");
    }
  };

  const handleAccept = async (suggestionId: number) => {
    setProcessingIds(prev => new Set(prev).add(suggestionId));

    const result = await acceptSuggestionAction(suggestionId);

    if (result.success) {
      setSuggestions(prev => prev.filter(s => s.id !== suggestionId));
      router.refresh();
    }

    setProcessingIds(prev => {
      const next = new Set(prev);
      next.delete(suggestionId);
      return next;
    });
  };

  const handleDecline = async (suggestionId: number) => {
    setProcessingIds(prev => new Set(prev).add(suggestionId));

    const result = await declineSuggestionAction(suggestionId);

    if (result.success) {
      setSuggestions(prev => prev.filter(s => s.id !== suggestionId));
    }

    setProcessingIds(prev => {
      const next = new Set(prev);
      next.delete(suggestionId);
      return next;
    });
  };

  const pendingCount = suggestions.length;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Sparkles className="h-4 w-4" />
          Discover Channels
          {pendingCount > 0 && (
            <Badge variant="secondary" className="ml-1">
              {pendingCount}
            </Badge>
          )}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Channel Discovery - {bucket.name}</DialogTitle>
          <DialogDescription>
            Find new channels based on trending topics in this bucket
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="discover" className="gap-2">
              <Search className="h-4 w-4" />
              Discover
            </TabsTrigger>
            <TabsTrigger value="suggestions" className="gap-2">
              Suggestions
              {pendingCount > 0 && (
                <Badge variant="secondary" className="ml-1 h-5 px-1.5">
                  {pendingCount}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="settings" className="gap-2">
              <Settings className="h-4 w-4" />
              Settings
            </TabsTrigger>
          </TabsList>

          {/* Discover Tab */}
          <TabsContent value="discover" className="space-y-4">
            {/* Keywords */}
            <div className="space-y-2">
              <Label>Search Keywords</Label>
              <p className="text-sm text-muted-foreground">
                Keywords from trending topics. Add custom keywords or remove irrelevant ones.
              </p>

              {isLoadingKeywords ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading trending topics...
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {keywords.map((keyword) => (
                    <Badge
                      key={keyword}
                      variant="secondary"
                      className="cursor-pointer hover:bg-destructive hover:text-destructive-foreground"
                      onClick={() => handleRemoveKeyword(keyword)}
                    >
                      {keyword}
                      <X className="h-3 w-3 ml-1" />
                    </Badge>
                  ))}
                  {keywords.length === 0 && (
                    <p className="text-sm text-muted-foreground italic">
                      No trending topics found. Add custom keywords below.
                    </p>
                  )}
                </div>
              )}

              {/* Add custom keyword */}
              <div className="flex gap-2">
                <Input
                  placeholder="Add custom keyword..."
                  value={customKeyword}
                  onChange={(e) => setCustomKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAddKeyword()}
                />
                <Button variant="outline" onClick={handleAddKeyword}>
                  Add
                </Button>
              </div>
            </div>

            <Separator />

            {/* Run Discovery */}
            <Button
              className="w-full"
              onClick={handleRunDiscovery}
              disabled={isRunningDiscovery || keywords.length === 0}
            >
              {isRunningDiscovery ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Search for Channels
                </>
              )}
            </Button>

            {/* Discovery Result */}
            {discoveryResult && (
              <Card>
                <CardContent className="pt-4">
                  <div className="text-sm space-y-1">
                    <p>
                      <strong>Keywords searched:</strong> {discoveryResult.keywords_used.length}
                    </p>
                    <p>
                      <strong>Channels found:</strong> {discoveryResult.channels_found}
                    </p>
                    <p>
                      <strong>After filtering:</strong> {discoveryResult.channels_filtered}
                    </p>
                    <p>
                      <strong>New suggestions:</strong> {discoveryResult.suggestions_saved}
                    </p>
                    {discoveryResult.error && (
                      <p className="text-destructive">{discoveryResult.error}</p>
                    )}
                    {Object.keys(discoveryResult.filter_stats).length > 0 && (
                      <div className="mt-2 pt-2 border-t">
                        <p className="font-medium mb-1">Filtered out:</p>
                        {Object.entries(discoveryResult.filter_stats).map(([reason, count]) => (
                          <p key={reason} className="text-muted-foreground">
                            {reason}: {count}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Suggestions Tab */}
          <TabsContent value="suggestions" className="space-y-4">
            {isLoadingSuggestions ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : suggestions.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p>No pending suggestions.</p>
                <p className="text-sm">Run discovery to find new channels.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {suggestions.map((suggestion) => (
                  <Card key={suggestion.id}>
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3">
                        {suggestion.thumbnail_url && (
                          <img
                            src={suggestion.thumbnail_url}
                            alt={suggestion.channel_name}
                            className="w-12 h-12 rounded-full"
                          />
                        )}
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium truncate">{suggestion.channel_name}</h4>
                          <p className="text-sm text-muted-foreground">
                            {formatNumber(suggestion.subscriber_count || 0)} subscribers
                            {suggestion.video_count && ` • ${formatNumber(suggestion.video_count)} videos`}
                            {suggestion.country && ` • ${suggestion.country}`}
                          </p>
                          {suggestion.matched_keywords?.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              {suggestion.matched_keywords.slice(0, 3).map((kw) => (
                                <Badge key={kw} variant="outline" className="text-xs">
                                  {kw}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
                            onClick={() => handleDecline(suggestion.id)}
                            disabled={processingIds.has(suggestion.id)}
                          >
                            {processingIds.has(suggestion.id) ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <X className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleAccept(suggestion.id)}
                            disabled={processingIds.has(suggestion.id)}
                          >
                            {processingIds.has(suggestion.id) ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Check className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="settings" className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              {/* Min Subscribers */}
              <div className="space-y-2">
                <Label htmlFor="min-subs">Min Subscribers</Label>
                <Input
                  id="min-subs"
                  type="number"
                  value={settings.min_subscribers}
                  onChange={(e) => setSettings({ ...settings, min_subscribers: parseInt(e.target.value) || 0 })}
                />
              </div>

              {/* Max Subscribers */}
              <div className="space-y-2">
                <Label htmlFor="max-subs">Max Subscribers</Label>
                <Input
                  id="max-subs"
                  type="number"
                  value={settings.max_subscribers}
                  onChange={(e) => setSettings({ ...settings, max_subscribers: parseInt(e.target.value) || 0 })}
                />
              </div>

              {/* Min Videos */}
              <div className="space-y-2">
                <Label htmlFor="min-videos">Min Videos</Label>
                <Input
                  id="min-videos"
                  type="number"
                  value={settings.min_videos}
                  onChange={(e) => setSettings({ ...settings, min_videos: parseInt(e.target.value) || 0 })}
                />
              </div>

              {/* Min Channel Age */}
              <div className="space-y-2">
                <Label htmlFor="min-age">Min Channel Age (days)</Label>
                <Input
                  id="min-age"
                  type="number"
                  value={settings.min_channel_age_days}
                  onChange={(e) => setSettings({ ...settings, min_channel_age_days: parseInt(e.target.value) || 0 })}
                />
              </div>
            </div>

            <Separator />

            {/* Exclude Kids Content */}
            <div className="flex items-center justify-between">
              <div>
                <Label>Exclude Kids Content</Label>
                <p className="text-sm text-muted-foreground">
                  Filter out channels marked as &quot;Made for Kids&quot;
                </p>
              </div>
              <Switch
                checked={settings.exclude_kids_content}
                onCheckedChange={(checked) => setSettings({ ...settings, exclude_kids_content: checked })}
              />
            </div>

            <Separator />

            {/* Activity Check */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Activity Check</Label>
                  <p className="text-sm text-muted-foreground">
                    Only suggest channels that posted recently
                  </p>
                </div>
                <Switch
                  checked={settings.activity_check}
                  onCheckedChange={(checked) => setSettings({ ...settings, activity_check: checked })}
                />
              </div>

              {settings.activity_check && (
                <div className="space-y-2 pl-4 border-l-2">
                  <Label htmlFor="max-days">Max Days Since Last Upload</Label>
                  <Input
                    id="max-days"
                    type="number"
                    value={settings.max_days_since_upload}
                    onChange={(e) => setSettings({ ...settings, max_days_since_upload: parseInt(e.target.value) || 60 })}
                  />
                </div>
              )}
            </div>

            <Separator />

            <Button
              className="w-full"
              onClick={handleSaveSettings}
              disabled={isSavingSettings}
            >
              {isSavingSettings ? "Saving..." : "Save Settings"}
            </Button>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
