"use client";

import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { RISK_TIER_LABELS } from "@/lib/constants";
import type { JurisdictionCompliance, RiskTierCount } from "@/types/api";

/** Chart colours resolve from CSS variables, so they follow the active theme. */
const RISK_COLORS: Record<string, string> = {
  prohibited: "hsl(var(--chart-4))",
  high: "hsl(var(--chart-4))",
  limited: "hsl(var(--chart-3))",
  minimal: "hsl(var(--chart-2))",
  unknown: "hsl(var(--muted-foreground))",
};

const tooltipStyle = {
  background: "hsl(var(--popover))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "var(--radius)",
  color: "hsl(var(--popover-foreground))",
  fontSize: 12,
};

export function JurisdictionComplianceChart({ data }: { data: JurisdictionCompliance[] }) {
  const rows = data
    .filter((row) => row.systems_in_scope > 0)
    .map((row) => ({
      code: row.jurisdiction_code,
      Compliant: row.compliant_systems,
      "Non-compliant": row.non_compliant_systems,
      Unassessed: row.unassessed_systems,
    }));

  if (!rows.length) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        No system is in scope for any jurisdiction yet. Run a classification to populate this.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
        <XAxis
          dataKey="code"
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          allowDecimals={false}
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "hsl(var(--muted))", opacity: 0.4 }} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
        <Bar dataKey="Compliant" stackId="a" fill="hsl(var(--chart-2))" radius={[0, 0, 0, 0]} />
        <Bar dataKey="Non-compliant" stackId="a" fill="hsl(var(--chart-4))" />
        <Bar
          dataKey="Unassessed"
          stackId="a"
          fill="hsl(var(--muted-foreground))"
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function RiskTierChart({ data }: { data: RiskTierCount[] }) {
  const rows = data.filter((row) => row.count > 0);

  if (!rows.length) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        No classifications yet.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={rows}
          dataKey="count"
          nameKey="risk_tier"
          innerRadius={62}
          outerRadius={98}
          paddingAngle={2}
          stroke="hsl(var(--background))"
        >
          {rows.map((row) => (
            <Cell key={row.risk_tier} fill={RISK_COLORS[row.risk_tier]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value, name) => [
            value as number,
            RISK_TIER_LABELS[String(name) as keyof typeof RISK_TIER_LABELS] ?? String(name),
          ]}
        />
        <Legend
          iconType="circle"
          wrapperStyle={{ fontSize: 12 }}
          formatter={(value) =>
            RISK_TIER_LABELS[String(value) as keyof typeof RISK_TIER_LABELS] ?? String(value)
          }
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
