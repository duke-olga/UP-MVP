const sourceLabelMap = {
  poop: "ПООП",
  best_practice: "Лучшие практики",
  best_practices: "Лучшие практики",
  local_requirement: "Локальные требования вуза",
  local: "Локальные требования вуза",
};

export function getSourceLabel(source) {
  if (!source) {
    return "Источник не указан";
  }
  if (sourceLabelMap[source]) {
    return sourceLabelMap[source];
  }
  return source;
}

export default function SourceBadge({ source }) {
  return <span className="source-badge">{getSourceLabel(source)}</span>;
}
