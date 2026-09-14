import { Check, ExternalLink, Minus } from "lucide-react";

import { JurisdictionBadge } from "@/components/shared/status-badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ATTRIBUTE_FLAGS, AUTONOMY_LABELS, GOVERNANCE_CONTROLS } from "@/lib/constants";
import { formatDateTime, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AISystem } from "@/types/api";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

function Regions({ values }: { values?: string[] }) {
  if (!values?.length) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {values.map((code) => (
        <JurisdictionBadge key={code} code={code} />
      ))}
    </div>
  );
}

function BooleanRow({ label, help, value }: { label: string; help: string; value: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b py-2.5 last:border-0">
      <div className="min-w-0">
        <p className="text-sm">{label}</p>
        <p className="text-xs text-muted-foreground">{help}</p>
      </div>
      <span
        className={cn(
          "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
          value ? "bg-status-pass text-status-pass-foreground" : "bg-muted text-muted-foreground",
        )}
        aria-label={value ? "Yes" : "No"}
      >
        {value ? <Check className="h-3.5 w-3.5" /> : <Minus className="h-3.5 w-3.5" />}
      </span>
    </div>
  );
}

export function OverviewTab({ system }: { system: AISystem }) {
  const meta = system.system_metadata;
  const attributes = (meta?.attributes ?? {}) as Record<string, unknown>;

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">System</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-6 text-sm text-muted-foreground">
              {system.description || "No description recorded."}
            </p>
            <dl className="grid gap-5 sm:grid-cols-2">
              <Field label="Purpose">{meta?.purpose || <span className="text-muted-foreground">—</span>}</Field>
              <Field label="Use case">{humanize(meta?.use_case)}</Field>
              <Field label="Industry">{humanize(meta?.industry)}</Field>
              <Field label="Autonomy level">
                {meta?.autonomy_level ? AUTONOMY_LABELS[meta.autonomy_level] : "—"}
              </Field>
              <Field label="Owner">{system.owner?.full_name ?? "—"}</Field>
              <Field label="Metadata version">v{system.metadata_version}</Field>
              <Field label="Created">{formatDateTime(system.created_at)}</Field>
              <Field label="Last updated">{formatDateTime(system.updated_at)}</Field>
              <div className="sm:col-span-2">
                <Field label="Technical documentation">
                  {meta?.technical_documentation_url ? (
                    <a
                      href={meta.technical_documentation_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      {meta.technical_documentation_url}
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : (
                    <span className="text-muted-foreground">Not provided</span>
                  )}
                </Field>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Reach</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-5 sm:grid-cols-2">
              <Field label="Deployment regions">
                <Regions values={meta?.deployment_regions} />
              </Field>
              <Field label="Data subject regions">
                <Regions values={meta?.data_subject_regions} />
              </Field>
              <Field label="Data residency">
                <Regions values={meta?.data_residency} />
              </Field>
              <Field label="Offered in">
                <Regions values={meta?.offered_in_regions} />
              </Field>
              <Field label="Service accessible from">
                <Regions values={meta?.service_accessible_regions} />
              </Field>
              <Field label="Content accessible from">
                <Regions values={meta?.content_accessible_regions} />
              </Field>
              <div className="sm:col-span-2">
                <Field label="Data categories">
                  <Regions values={meta?.data_categories} />
                </Field>
              </div>
              <div className="sm:col-span-2">
                <Field label="Third-party models">
                  <Regions values={meta?.third_party_models} />
                </Field>
              </div>
            </dl>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Governance controls</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {GOVERNANCE_CONTROLS.map((control) => (
              <BooleanRow
                key={control.name as string}
                label={control.label}
                help={control.help}
                value={Boolean(meta?.[control.name])}
              />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Evidence of obligations</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {ATTRIBUTE_FLAGS.map((flag) => (
              <BooleanRow
                key={flag.name}
                label={flag.label}
                help={flag.help}
                value={Boolean(attributes[flag.name])}
              />
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
