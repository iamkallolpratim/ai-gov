"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { EvidenceGenerateInput } from "@/types/api";

export function GenerateEvidenceDialog({
  open,
  onOpenChange,
  onGenerate,
  isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onGenerate: (input: EvidenceGenerateInput) => void;
  isPending: boolean;
}) {
  const [includeHistory, setIncludeHistory] = useState(false);
  const [refreshChecks, setRefreshChecks] = useState(true);
  const [notes, setNotes] = useState("");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Generate evidence package</DialogTitle>
          <DialogDescription>
            Bundles this system&apos;s metadata, risk classifications and policy results into a
            jurisdiction-specific PDF and a JSON manifest, then checksums both.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="flex items-start gap-3">
            <Checkbox
              id="refresh-checks"
              checked={refreshChecks}
              onCheckedChange={(value) => setRefreshChecks(value === true)}
            />
            <div className="space-y-0.5">
              <Label htmlFor="refresh-checks" className="font-medium">
                Re-run policy checks first
              </Label>
              <p className="text-xs text-muted-foreground">
                Recommended, so the package reflects the current metadata rather than the last run.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <Checkbox
              id="include-history"
              checked={includeHistory}
              onCheckedChange={(value) => setIncludeHistory(value === true)}
            />
            <div className="space-y-0.5">
              <Label htmlFor="include-history" className="font-medium">
                Include change history
              </Label>
              <p className="text-xs text-muted-foreground">
                Appends the metadata version history to the report.
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="evidence-notes">Notes (optional)</Label>
            <Textarea
              id="evidence-notes"
              rows={2}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Q3 internal audit"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button
            onClick={() =>
              onGenerate({
                include_history: includeHistory,
                refresh_checks: refreshChecks,
                notes: notes || null,
              })
            }
            disabled={isPending}
          >
            {isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Generate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
