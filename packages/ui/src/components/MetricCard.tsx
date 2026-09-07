/** The "—, Not calculated" placeholder card pattern used in both apps. */
export function MetricCard({ label, value }: { label: string; value?: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>—</strong>
      {value !== undefined && <small>{value}</small>}
    </div>
  );
}

export function MetricGrid({ metrics }: { metrics: { label: string; value?: string }[] }) {
  return (
    <div className="metric-grid">
      {metrics.map((metric) => (
        <MetricCard key={metric.label} label={metric.label} value={metric.value} />
      ))}
    </div>
  );
}
