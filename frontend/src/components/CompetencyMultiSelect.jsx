import { useEffect, useMemo, useRef, useState } from "react";

export default function CompetencyMultiSelect({
  groupedCompetencies,
  selectedIds,
  onChange,
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const allItems = useMemo(
    () => Object.values(groupedCompetencies).flat(),
    [groupedCompetencies],
  );

  const selectedItems = useMemo(
    () => allItems.filter((c) => selectedIds.includes(c.id)),
    [allItems, selectedIds],
  );

  const filteredGroups = useMemo(() => {
    const q = query.trim().toLowerCase();
    return Object.fromEntries(
      Object.entries(groupedCompetencies).map(([group, items]) => [
        group,
        q ? items.filter((i) => `${i.code} ${i.name}`.toLowerCase().includes(q)) : items,
      ]),
    );
  }, [groupedCompetencies, query]);

  const toggle = (id, checked) => {
    onChange(checked ? [...selectedIds, id] : selectedIds.filter((x) => x !== id));
  };

  return (
    <div className="comp-multiselect" ref={containerRef}>
      <div
        className={`comp-multiselect__trigger${open ? " open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setOpen((o) => !o); }}
      >
        {selectedItems.length === 0 ? (
          <span className="comp-multiselect__placeholder">Выбрать компетенции…</span>
        ) : (
          selectedItems.map((item) => (
            <span key={item.id} className="comp-chip" title={item.name}>
              {item.code}
            </span>
          ))
        )}
      </div>

      {open && (
        <div className="comp-multiselect__panel">
          <div className="comp-multiselect__search">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Поиск по коду или названию…"
              onClick={(e) => e.stopPropagation()}
              autoFocus
            />
          </div>
          <div className="comp-multiselect__list">
            {Object.entries(filteredGroups).map(([group, items]) =>
              items.length > 0 ? (
                <div key={group}>
                  <div className="comp-multiselect__group-label">{group}</div>
                  {items.map((item) => (
                    <label
                      key={item.id}
                      className={`comp-multiselect__option${selectedIds.includes(item.id) ? " selected" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(item.id)}
                        onChange={(e) => toggle(item.id, e.target.checked)}
                        style={{ width: 14, height: 14, flexShrink: 0 }}
                      />
                      <span className="comp-multiselect__code">{item.code}</span>
                      <span style={{ color: "var(--text-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {item.name}
                      </span>
                    </label>
                  ))}
                </div>
              ) : null
            )}
          </div>
        </div>
      )}
    </div>
  );
}
