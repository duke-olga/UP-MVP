const sourceLabelMap = {
  poop: "ПООП",
  best_practice: "Лучшие практики",
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
  if (["ПООП", "Лучшие практики", "Локальные требования вуза"].includes(source)) {
    return source;
  }
  return "Источник не указан";
}

export default function SourceBadge({ source }) {
  return <span className="source-badge">{getSourceLabel(source)}</span>;
}
