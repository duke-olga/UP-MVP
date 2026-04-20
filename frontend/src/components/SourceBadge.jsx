const SOURCE_MAP = {
  poop:              { label: "ПООП",                   cls: "source-badge-poop" },
  best_practice:     { label: "Лучшие практики",         cls: "source-badge-best" },
  best_practices:    { label: "Лучшие практики",         cls: "source-badge-best" },
  local_requirement: { label: "Локальные требования вуза", cls: "source-badge-local" },
  local:             { label: "Локальные требования вуза", cls: "source-badge-local" },
};

export function getSourceLabel(source) {
  return SOURCE_MAP[source]?.label || source || "Источник не указан";
}

export default function SourceBadge({ source }) {
  const cfg = SOURCE_MAP[source] || { label: source || "—", cls: "source-badge-poop" };
  return <span className={`source-badge ${cfg.cls}`}>{cfg.label}</span>;
}
