type StatCardProps = {
  label: string;
  value: string | number;
  note: string;
};

export function StatCard({ label, value, note }: StatCardProps) {
  return (
    <article className="stat-card">
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      <p>{note}</p>
    </article>
  );
}
