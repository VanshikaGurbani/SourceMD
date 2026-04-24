import { PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer } from "recharts";

function gaugeColor(score: number): string {
  if (score >= 75) return "#10b981";
  if (score >= 45) return "#f59e0b";
  return "#ef4444";
}

export default function TrustGauge({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const data = [{ name: "trust", value: clamped, fill: gaugeColor(clamped) }];

  return (
    <div className="relative w-full h-48">
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart innerRadius="70%" outerRadius="100%" data={data} startAngle={180} endAngle={0}>
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar background dataKey="value" cornerRadius={8} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-end pb-4 pointer-events-none">
        <div className="text-4xl font-bold text-slate-900 dark:text-slate-100">{clamped.toFixed(0)}</div>
        <div className="text-sm text-slate-500 dark:text-slate-400">Trust score</div>
      </div>
    </div>
  );
}
