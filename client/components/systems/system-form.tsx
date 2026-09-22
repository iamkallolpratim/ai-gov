"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { MultiSelect } from "@/components/systems/multi-select";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  ATTRIBUTE_FLAGS,
  ATTRIBUTE_FLAG_GROUPS,
  AUTONOMY_LABELS,
  DATA_CATEGORIES,
  GOVERNANCE_CONTROLS,
  INDUSTRIES,
  REGIONS,
  STATUS_LABELS,
  USE_CASES,
} from "@/lib/constants";
import { humanize } from "@/lib/format";
import {
  AUTONOMY_LEVELS,
  SYSTEM_STATUSES,
  type AISystem,
  type AISystemCreateInput,
} from "@/types/api";

const schema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  description: z.string().max(2000).optional(),
  status: z.enum(SYSTEM_STATUSES),
  purpose: z.string().max(2000).optional(),
  use_case: z.string().optional(),
  industry: z.string().optional(),
  autonomy_level: z.enum(AUTONOMY_LEVELS),
  data_categories: z.array(z.string()),
  deployment_regions: z.array(z.string()),
  data_subject_regions: z.array(z.string()),
  data_residency: z.array(z.string()),
  offered_in_regions: z.array(z.string()),
  service_accessible_regions: z.array(z.string()),
  content_accessible_regions: z.array(z.string()),
  third_party_models: z.array(z.string()),
  technical_documentation_url: z.string().url("Enter a valid URL").or(z.literal("")).optional(),
  booleans: z.record(z.boolean()),
  attributes: z.record(z.boolean()),
  change_summary: z.string().max(500).optional(),
});

export type SystemFormValues = z.infer<typeof schema>;

const NONE = "__none__";

function toDefaults(system?: AISystem): SystemFormValues {
  const meta = system?.system_metadata;
  const booleans: Record<string, boolean> = {};
  for (const control of GOVERNANCE_CONTROLS) {
    booleans[control.name as string] = Boolean(meta?.[control.name] ?? false);
  }
  const attributes: Record<string, boolean> = {};
  for (const flag of ATTRIBUTE_FLAGS) {
    attributes[flag.name] = Boolean((meta?.attributes as Record<string, unknown>)?.[flag.name]);
  }

  return {
    name: system?.name ?? "",
    description: system?.description ?? "",
    status: system?.status ?? "draft",
    purpose: meta?.purpose ?? "",
    use_case: meta?.use_case ?? "",
    industry: meta?.industry ?? "",
    autonomy_level: meta?.autonomy_level ?? "human_in_the_loop",
    data_categories: meta?.data_categories ?? [],
    deployment_regions: meta?.deployment_regions ?? [],
    data_subject_regions: meta?.data_subject_regions ?? [],
    data_residency: meta?.data_residency ?? [],
    offered_in_regions: meta?.offered_in_regions ?? [],
    service_accessible_regions: meta?.service_accessible_regions ?? [],
    content_accessible_regions: meta?.content_accessible_regions ?? [],
    third_party_models: meta?.third_party_models ?? [],
    technical_documentation_url: meta?.technical_documentation_url ?? "",
    booleans,
    attributes,
    change_summary: "",
  };
}

/** Maps form state onto the API's create/update payload. */
export function toPayload(values: SystemFormValues): AISystemCreateInput & { change_summary?: string } {
  return {
    name: values.name,
    description: values.description || null,
    status: values.status,
    change_summary: values.change_summary || undefined,
    system_metadata: {
      purpose: values.purpose || null,
      use_case: values.use_case || null,
      industry: values.industry || null,
      autonomy_level: values.autonomy_level,
      data_categories: values.data_categories,
      deployment_regions: values.deployment_regions,
      data_subject_regions: values.data_subject_regions,
      data_residency: values.data_residency,
      offered_in_regions: values.offered_in_regions,
      service_accessible_regions: values.service_accessible_regions,
      content_accessible_regions: values.content_accessible_regions,
      third_party_models: values.third_party_models,
      technical_documentation_url: values.technical_documentation_url || null,
      ...values.booleans,
      attributes: values.attributes,
    },
  };
}

const REGION_FIELDS: {
  name: keyof SystemFormValues;
  label: string;
  description: string;
}[] = [
  {
    name: "deployment_regions",
    label: "Deployment regions",
    description: "Where the system actually runs.",
  },
  {
    name: "data_subject_regions",
    label: "Data subject regions",
    description: "Where the people it processes data about are located. Drives extraterritorial reach.",
  },
  {
    name: "data_residency",
    label: "Data residency",
    description: "Where its data is stored or processed.",
  },
  {
    name: "offered_in_regions",
    label: "Offered in",
    description: "Markets the system is offered or marketed to.",
  },
  {
    name: "service_accessible_regions",
    label: "Service accessible from",
    description: "Where the service can be reached at all. Use GLOBAL for the public internet.",
  },
  {
    name: "content_accessible_regions",
    label: "Generated content accessible from",
    description: "Where output produced by the system can be viewed. Only used for generative systems.",
  },
];

export function SystemForm({
  system,
  onSubmit,
  isSubmitting,
  mode,
}: {
  system?: AISystem;
  onSubmit: (values: SystemFormValues) => void;
  isSubmitting: boolean;
  mode: "create" | "edit";
}) {
  const form = useForm<SystemFormValues>({
    resolver: zodResolver(schema),
    defaultValues: toDefaults(system),
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6" noValidate>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Identity</CardTitle>
            <CardDescription>What the system is and who is accountable for it.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-5 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Resume Screening Assistant" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={2}
                      placeholder="Ranks and shortlists job applicants for recruiters."
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Status</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {SYSTEM_STATUSES.map((value) => (
                        <SelectItem key={value} value={value}>
                          {STATUS_LABELS[value]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="industry"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Industry</FormLabel>
                  <Select
                    onValueChange={(value) => field.onChange(value === NONE ? "" : value)}
                    value={field.value || NONE}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select an industry" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={NONE}>Not specified</SelectItem>
                      {INDUSTRIES.map((value) => (
                        <SelectItem key={value} value={value}>
                          {humanize(value)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Purpose and use case</CardTitle>
            <CardDescription>
              The use case is matched against EU AI Act Annex III, so choosing an exact value
              here is what makes classification correct.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-5 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="purpose"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Purpose</FormLabel>
                  <FormControl>
                    <Textarea rows={2} placeholder="Shortlist job applicants from submitted CVs." {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="use_case"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Use case</FormLabel>
                  <Select
                    onValueChange={(value) => field.onChange(value === NONE ? "" : value)}
                    value={field.value || NONE}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a use case" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent className="max-h-72">
                      <SelectItem value={NONE}>Not specified</SelectItem>
                      {USE_CASES.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    Prohibited and Annex III use cases are grouped in the list.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="autonomy_level"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Autonomy level</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {AUTONOMY_LEVELS.map((value) => (
                        <SelectItem key={value} value={value}>
                          {AUTONOMY_LABELS[value]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="data_categories"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Data categories</FormLabel>
                  <FormControl>
                    <MultiSelect
                      options={DATA_CATEGORIES.map((c) => ({
                        value: c.value,
                        label: c.sensitive ? `${c.label} — special category` : c.label,
                      }))}
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="Select data categories"
                    />
                  </FormControl>
                  <FormDescription>
                    Special category data triggers additional safeguards under Art. 10(5).
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="third_party_models"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Third-party models</FormLabel>
                  <FormControl>
                    <MultiSelect
                      options={[
                        { value: "claude-opus-5", label: "claude-opus-5" },
                        { value: "claude-sonnet-5", label: "claude-sonnet-5" },
                      ]}
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="Add a model the system builds on"
                    />
                  </FormControl>
                  <FormDescription>Drives value-chain duties under Art. 25 and Art. 53.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Reach</CardTitle>
            <CardDescription>
              Where the system runs, who it affects and where it can be reached. These fields
              decide which jurisdictions apply.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-5 sm:grid-cols-2">
            {REGION_FIELDS.map((regionField) => (
              <FormField
                key={regionField.name}
                control={form.control}
                name={regionField.name}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{regionField.label}</FormLabel>
                    <FormControl>
                      <MultiSelect
                        options={REGIONS}
                        value={(field.value as string[]) ?? []}
                        onChange={field.onChange}
                        placeholder="Select regions"
                      />
                    </FormControl>
                    <FormDescription>{regionField.description}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Governance controls</CardTitle>
            <CardDescription>
              What the policy engine reads when deciding whether obligations are met.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-3 sm:grid-cols-2">
              {GOVERNANCE_CONTROLS.map((control) => (
                <FormField
                  key={control.name as string}
                  control={form.control}
                  name={`booleans.${control.name as string}` as const}
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between gap-4 rounded-lg border p-3">
                      <div className="space-y-0.5">
                        <FormLabel className="text-sm font-medium">{control.label}</FormLabel>
                        <FormDescription className="text-xs">{control.help}</FormDescription>
                      </div>
                      <FormControl>
                        <Switch checked={!!field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              ))}
            </div>

            <FormField
              control={form.control}
              name="technical_documentation_url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Technical documentation URL</FormLabel>
                  <FormControl>
                    <Input placeholder="https://docs.internal/ai/system" {...field} />
                  </FormControl>
                  <FormDescription>Required for high-risk systems under Art. 11.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="space-y-5">
              <p className="text-sm font-medium">Evidence of specific obligations</p>
              {ATTRIBUTE_FLAG_GROUPS.map((group) => (
                <div key={group.jurisdiction}>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {group.label}
                  </p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {group.flags.map((flag) => (
                      <FormField
                        key={flag.name}
                        control={form.control}
                        name={`attributes.${flag.name}` as const}
                        render={({ field }) => (
                          <FormItem className="flex items-center justify-between gap-4 rounded-lg border p-3">
                            <div className="space-y-0.5">
                              <FormLabel className="text-sm font-medium">{flag.label}</FormLabel>
                              <FormDescription className="text-xs">{flag.help}</FormDescription>
                            </div>
                            <FormControl>
                              <Switch checked={!!field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </FormItem>
                        )}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {mode === "edit" ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Change summary</CardTitle>
              <CardDescription>
                Recorded on the immutable version history alongside the field-level diff.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <FormField
                control={form.control}
                name="change_summary"
                render={({ field }) => (
                  <FormItem>
                    <FormControl>
                      <Input placeholder="Added EU deployment and documented oversight" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>
        ) : null}

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" asChild>
            <Link href={system ? `/systems/${system.id}` : "/systems"}>Cancel</Link>
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            {mode === "create" ? "Register system" : "Save changes"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
