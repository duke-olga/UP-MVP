const statusMap = {
  draft: { label: "Черновик", tone: "draft" },
  checked: { label: "Проверен", tone: "checked" },
  approved: { label: "Утвержден", tone: "approved" },
  critical: { label: "Критическое нарушение", tone: "critical" },
  error: { label: "Ошибка", tone: "error" },
  warning: { label: "Предупреждение", tone: "warning" },
  manual: { label: "Ручной режим", tone: "manual" },
  neutral: { label: "Статус", tone: "neutral" },
};

export default function StatusBadge({ value, children }) {
  const config = statusMap[value] || statusMap.neutral;
  return <span className={`status-badge ${config.tone}`}>{children || config.label}</span>;
}
