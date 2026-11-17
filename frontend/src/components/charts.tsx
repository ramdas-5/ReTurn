"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { chartAxis, chartSeries, palette } from "@/lib/design-tokens";

export type ChartDatum = { label: string; value: number };

/** Horizontal bars for categorical counts (labels stay readable). */
export function CountBarChart({ data }: { data: ChartDatum[] }) {
  if (data.length === 0) {
    return <p className="py-6 text-sm text-muted">Nothing recorded for this period yet.</p>;
  }
  return (
    <div className="h-[260px] w-full" role="img" aria-label="Bar chart of counts by category">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid horizontal={false} stroke={chartAxis.grid} />
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: chartAxis.tick }} />
          <YAxis
            type="category"
            dataKey="label"
            width={132}
            tick={{ fontSize: 11, fill: chartAxis.tickStrong }}
          />
          <Tooltip cursor={{ fill: chartAxis.cursor }} />
          <Bar dataKey="value" fill={palette.accent} radius={[0, 4, 4, 0]} name="Count" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Donut for status splits; zero-value rows are dropped by the caller. */
export function SharePieChart({ data }: { data: ChartDatum[] }) {
  if (data.length === 0) {
    return <p className="py-6 text-sm text-muted">Nothing recorded for this period yet.</p>;
  }
  return (
    <div className="h-[240px] w-full" role="img" aria-label="Donut chart of counts by status">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            innerRadius={52}
            outerRadius={82}
            paddingAngle={2}
          >
            {data.map((row, index) => (
              <Cell key={row.label} fill={chartSeries[index % chartSeries.length]} />
            ))}
          </Pie>
          <Legend />
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

