const BADGE_MAP = {
  draft:    { label: "Черновик",    cls: "badge-draft" },
  checked:  { label: "Проверен",    cls: "badge-checked" },
  approved: { label: "Утверждён",   cls: "badge-approved" },
  critical: { label: "Критическое", cls: "badge-critical" },
  error:    { label: "Ошибка",      cls: "badge-error" },
  warning:  { label: "Предупреждение", cls: "badge-warning" },
  ok:       { label: "ОК",          cls: "badge-ok" },
  manual:   { label: "Ручной режим",cls: "badge-manual" },
};

export default function StatusBadge({ value, children }) {
  const cfg = BADGE_MAP[value] || BADGE_MAP.draft;
  return <span className={`badge ${cfg.cls}`}>{children ?? cfg.label}</span>;
}
