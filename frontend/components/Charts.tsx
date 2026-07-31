import type { PositionView } from "@/lib/types";
import { formatCompactCurrency, formatCurrency } from "@/lib/format";

type SeriesProps = {
  points: number[];
  className?: string;
  label?: string;
};

function pathFor(points: number[], width: number, height: number): string {
  if (points.length === 0) return "";
  if (points.length === 1) return `M 0 ${height / 2} L ${width} ${height / 2}`;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  return points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * width;
      const y = height - ((point - min) / span) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function Sparkline({ points, className, label }: SeriesProps) {
  const direction = points.length > 1 && points[points.length - 1] >= points[0] ? "positive" : "negative";
  return (
    <svg className={className} viewBox="0 0 120 36" role="img" aria-label={label ?? "Price sparkline"}>
      <path className="sparkline-grid" d="M0 18H120" />
      <path className={`sparkline-path ${direction}`} d={pathFor(points, 120, 36)} />
    </svg>
  );
}

export function LineChart({
  points,
  title,
  valueLabel
}: {
  points: number[];
  title: string;
  valueLabel?: string;
}) {
  return (
    <div className="chart-shell">
      <div className="chart-header">
        <span>{title}</span>
        <strong>{valueLabel}</strong>
      </div>
      <svg className="line-chart" viewBox="0 0 640 240" role="img" aria-label={title}>
        <path className="chart-grid" d="M0 48H640M0 96H640M0 144H640M0 192H640" />
        <path className="chart-axis" d="M0 238H640" />
        <path className="line-chart-path" d={pathFor(points, 640, 220)} />
      </svg>
    </div>
  );
}

export function Heatmap({ positions }: { positions: PositionView[] }) {
  const totalWeight = positions.reduce((sum, position) => sum + position.weight, 0) || 1;

  return (
    <div className="heatmap" aria-label="Portfolio heatmap">
      {positions.length === 0 ? (
        <div className="empty-state">No positions</div>
      ) : (
        positions.map((position) => (
          <div
            className={`heat-cell ${position.unrealizedPnl >= 0 ? "gain" : "loss"}`}
            key={position.ticker}
            style={{ flexGrow: Math.max(8, (position.weight / totalWeight) * 100) }}
            title={`${position.ticker} ${formatCurrency(position.marketValue)}`}
          >
            <strong>{position.ticker}</strong>
            <span>{formatCompactCurrency(position.marketValue)}</span>
            <small>{position.unrealizedReturn >= 0 ? "+" : ""}{position.unrealizedReturn.toFixed(2)}%</small>
          </div>
        ))
      )}
    </div>
  );
}
