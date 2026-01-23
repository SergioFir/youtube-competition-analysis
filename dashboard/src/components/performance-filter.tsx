"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";

interface PerformanceFilterProps {
  currentFilter: string;
}

const PERFORMANCE_OPTIONS = [
  { value: "all", label: "All Videos" },
  { value: "above", label: "Above Baseline", description: ">1x" },
  { value: "hits", label: "Potential HITs", description: ">2x" },
  { value: "below", label: "Below Baseline", description: "<1x" },
];

export function PerformanceFilter({ currentFilter }: PerformanceFilterProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleFilterClick = (value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value === "all") {
      params.delete("performance");
    } else {
      params.set("performance", value);
    }
    router.push(`?${params.toString()}`);
  };

  return (
    <div className="flex flex-wrap gap-2">
      {PERFORMANCE_OPTIONS.map((option) => (
        <Badge
          key={option.value}
          variant={currentFilter === option.value ? "default" : "outline"}
          className={`cursor-pointer hover:bg-primary/80 ${
            option.value === "hits" && currentFilter === option.value
              ? "bg-green-600 hover:bg-green-700"
              : ""
          }`}
          onClick={() => handleFilterClick(option.value)}
        >
          {option.label}
          {option.description && (
            <span className="ml-1 opacity-60">{option.description}</span>
          )}
        </Badge>
      ))}
    </div>
  );
}
