const sourceLabelMap = {
  poop: "ПООП",
  best_practice: "Лучшие практики",
  local_requirement: "Локальные требования вуза",
  local: "Локальные требования вуза",
};

export function getSourceLabel(source) {
  return sourceLabelMap[source] || "Источник не указан";
}

export default function SourceBadge({ source }) {
  return <span className="source-badge">{getSourceLabel(source)}</span>;
}
