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

const SERIES_COLOURS = ["#10B981", "#14B8A6", "#0D1B2A", "#F59E0B", "#EF4444", "#64748B"];

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
          <CartesianGrid horizontal={false} stroke="#e2e8f0" />
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} />
          <YAxis
            type="category"
            dataKey="label"
            width={132}
            tick={{ fontSize: 11, fill: "#334155" }}
          />
          <Tooltip cursor={{ fill: "#f1f5f9" }} />
          <Bar dataKey="value" fill="#10B981" radius={[0, 4, 4, 0]} name="Count" />
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
              <Cell key={row.label} fill={SERIES_COLOURS[index % SERIES_COLOURS.length]} />
            ))}
          </Pie>
          <Legend />
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
