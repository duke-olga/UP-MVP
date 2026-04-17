import { useMemo, useState } from "react";

const groupLabels = {
  "УК": "УК",
  "ОПК": "ОПК",
  "ПК": "ПК",
  "ПКС": "ПКС",
};

function normalize(value) {
  return value.trim().toLowerCase();
}

export default function CompetencyMultiSelect({
  groupedCompetencies,
  selectedIds,
  onChange,
  title = "Компетенции",
}) {
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);

  const selectedItems = useMemo(
    () =>
      Object.values(groupedCompetencies)
        .flat()
        .filter((item) => selectedIds.includes(item.id)),
    [groupedCompetencies, selectedIds],
  );

  const filteredGroups = useMemo(() => {
    const preparedQuery = normalize(query);
    return Object.fromEntries(
      Object.entries(groupedCompetencies).map(([group, items]) => [
        group,
        items.filter((item) => {
          if (!preparedQuery) {
            return true;
          }
          return `${item.code} ${item.name}`.toLowerCase().includes(preparedQuery);
        }),
      ]),
    );
  }, [groupedCompetencies, query]);

  const toggleItem = (itemId, checked) => {
    if (checked) {
      onChange([...selectedIds, itemId]);
      return;
    }
    onChange(selectedIds.filter((id) => id !== itemId));
  };

  return (
    <div className="competency-select">
      <button
        type="button"
        className="select-toggle"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        <span>{title}</span>
        <strong>
          {selectedItems.length > 0 ? `Выбрано: ${selectedItems.length}` : "Выбрать компетенции"}
        </strong>
      </button>

      {selectedItems.length > 0 ? (
        <div className="selected-tags">
          {selectedItems.map((item) => (
            <span key={item.id} className="selected-tag">
              {item.code}
            </span>
          ))}
        </div>
      ) : null}

      {expanded ? (
        <div className="select-panel">
          <label className="field">
            <span>Поиск по коду или названию</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Например, УК-1 или Системное мышление"
            />
          </label>

          <div className="select-groups">
            {Object.entries(filteredGroups).map(([group, items]) =>
              items.length > 0 ? (
                <div key={group} className="select-group">
                  <p className="select-group-title">{groupLabels[group] || group}</p>
                  <div className="select-options">
                    {items.map((item) => (
                      <label key={item.id} className="select-option">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(item.id)}
                          onChange={(event) => toggleItem(item.id, event.target.checked)}
                        />
                        <div>
                          <strong>{item.code}</strong>
                          <span>{item.name}</span>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              ) : null,
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
