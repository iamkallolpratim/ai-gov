import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
  href,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: LucideIcon;
  tone?: "default" | "pass" | "warn" | "fail";
  href?: string;
}) {
  const toneClass = {
    default: "bg-muted text-muted-foreground",
    pass: "bg-status-pass text-status-pass-foreground",
    warn: "bg-status-warn text-status-warn-foreground",
    fail: "bg-status-fail text-status-fail-foreground",
  }[tone];

  const content = (
    <Card className={cn("h-full transition-colors", href && "hover:border-primary/40")}>
      <CardContent className="flex items-start justify-between gap-4 p-6">
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="text-3xl font-semibold tabular-nums tracking-tight">{value}</p>
          {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
        </div>
        <span className={cn("rounded-lg p-2.5", toneClass)}>
          <Icon className="h-5 w-5" aria-hidden />
        </span>
      </CardContent>
    </Card>
  );

  return href ? (
    <Link href={href} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-xl">
      {content}
    </Link>
  ) : (
    content
  );
}
