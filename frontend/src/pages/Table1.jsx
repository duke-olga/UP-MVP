import { useEffect, useMemo, useRef, useState } from "react";
import { getErrorMessage, getTable1, semanticSearch, transferTable1 } from "../api";
import EmptyState from "../components/EmptyState";
import SourceBadge from "../components/SourceBadge";

const FGOS_LABELS = {
  philosophy: "Философия",
  history: "История России",
  foreign_language: "Иностранный язык",
  life_safety: "Безопасность жизнедеятельности",
  educational_practice: "Учебная практика",
  industrial_practice: "Производственная практика",
};

const PART_LABELS = { mandatory: "Обязательная часть", variative: "Вариативная часть" };

function SemChips({ semesters }) {
  if (!semesters?.length) return <span className="text-muted" style={{ fontSize: 12 }}>Сем. не указаны</span>;
  return (
    <>
      {semesters.map((s) => (
        <span key={s} className="sem-chip">С{s}</span>
      ))}
    </>
  );
}

function RecCard({ item, checked, inputType = "checkbox", radioName, onChange }) {
  const handleClick = () => {
    if (inputType === "radio") {
      onChange(item.id, !checked);
    } else {
      onChange(item.id, !checked);
    }
  };

  return (
    <label
      className={`rec-card${checked ? " selected" : ""}`}
      onClick={(e) => { e.preventDefault(); handleClick(); }}
    >
      <div className="rec-card__check">
        <input
          type={inputType}
          name={radioName}
          checked={checked}
          onChange={() => {}}
          style={{ pointerEvents: "none" }}
        />
      </div>
      <div className="rec-card__body">
        <div className="rec-card__name">{item.name}</div>
        <div className="rec-card__meta">
          <span className="rec-card__credits">{item.credits ?? 0} з.е.</span>
          <SemChips semesters={item.semesters} />
          {item.extra_hours > 0 && (
            <span className="sem-chip">+{item.extra_hours} ч.</span>
          )}
          <SourceBadge source={item.source} />
          {item.practice_type && (
            <span className="source-badge source-badge-local">
              {item.practice_type === "educational" ? "Учебная" : "Производственная"}
            </span>
          )}
        </div>
        {item.competency_codes?.length > 0 && (
          <div style={{ marginTop: 4, display: "flex", gap: 4, flexWrap: "wrap" }}>
            {item.competency_codes.map((c) => (
              <span key={c} className="comp-chip">{c}</span>
            ))}
          </div>
        )}
      </div>
    </label>
  );
}

function RecSection({ title, headerClass = "", items, selections, onToggle, onSingleSelect, group }) {
  const selected = items.filter((i) => selections[i.id]).length;
  return (
    <div className="rec-section">
      <div className={`rec-section-header${headerClass ? " " + headerClass : ""}`}>
        <span>{title}</span>
        {group?.is_complete !== undefined && (
          <span
            className="rec-section-badge"
            style={group.is_complete
              ? { background: "var(--success-bg)", color: "var(--success)", borderColor: "var(--success-border)" }
              : { background: "var(--warning-bg)", color: "var(--warning)", borderColor: "var(--warning-border)" }
            }
          >
            {group.is_complete ? "✓ Выполнено" : "Ожидает"}
          </span>
        )}
        {!group && <span className="rec-section-badge">{selected}/{items.length}</span>}
      </div>
      {items.length === 0 ? (
        <div className="rec-cards">
          <div style={{ padding: "12px 16px", color: "var(--text-3)", fontSize: 13 }}>
            Рекомендации не найдены — добавьте вручную на шаге «Учебный план».
          </div>
        </div>
      ) : (
        <div className="rec-cards">
          {items.map((item) => (
            <RecCard
              key={item.id}
              item={item}
              checked={Boolean(selections[item.id])}
              inputType={group?.selection_mode === "single" ? "radio" : "checkbox"}
              radioName={group?.requirement}
              onChange={(id, val) => {
                if (group?.selection_mode === "single") {
                  onSingleSelect?.(group, id, val);
                } else {
                  onToggle(id, val);
                }
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ScoreBadge({ score }) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "var(--success)" : pct >= 45 ? "var(--warning)" : "var(--text-3)";
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, padding: "1px 6px",
      borderRadius: 10, border: `1px solid ${color}`, color,
      background: "transparent", whiteSpace: "nowrap",
    }}>
      {pct}%
    </span>
  );
}

function SemanticSearchPanel({ planId, selections, onToggle }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const debounceRef = useRef(null);

  const runSearch = (q) => {
    if (!q || q.trim().length < 2) { setResults(null); setError(""); return; }
    setLoading(true);
    setError("");
    semanticSearch(planId, q.trim())
      .then((res) => { setResults(res.data); })
      .catch((e) => {
        const msg = e?.response?.data?.detail || e?.message || "Ошибка поиска";
        setError(msg);
        setResults(null);
      })
      .finally(() => setLoading(false));
  };

  const handleChange = (e) => {
    const q = e.target.value;
    setQuery(q);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(q), 400);
  };

  return (
    <div style={{ marginBottom: 16, border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", textAlign: "left", padding: "10px 16px",
          background: open ? "var(--indigo-50, #eef2ff)" : "var(--surface-2)",
          border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 8,
          fontSize: 13, fontWeight: 600, color: "var(--text-1)",
        }}
      >
        <span style={{ fontSize: 15 }}>🔍</span>
        Семантический поиск по смыслу
        <span style={{ marginLeft: "auto", color: "var(--text-3)", fontWeight: 400, fontSize: 12 }}>
          {open ? "▲ свернуть" : "▼ развернуть"}
        </span>
      </button>

      {open && (
        <div style={{ padding: "12px 16px", background: "var(--surface-1)" }}>
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 8 }}>
            Введите название компетенции, тему или ключевые слова — система найдёт похожие дисциплины по смыслу, даже если слова не совпадают точно.
          </div>
          <input
            type="text"
            value={query}
            onChange={handleChange}
            placeholder="Например: машинное обучение, анализ данных, программная инженерия…"
            style={{
              width: "100%", padding: "8px 12px", border: "1px solid var(--border)",
              borderRadius: 6, fontSize: 13, outline: "none", boxSizing: "border-box",
              background: "var(--surface-1)", color: "var(--text-1)",
            }}
          />

          {loading && (
            <div style={{ marginTop: 10, color: "var(--text-3)", fontSize: 13 }}>
              <span className="spinner" style={{ marginRight: 6 }} />
              Вычисляем сходство… (первый запрос загружает модель)
            </div>
          )}

          {error && (
            <div style={{ marginTop: 10, fontSize: 12, color: "var(--error, #dc2626)" }}>
              {error.includes("unavailable") || error.includes("503")
                ? "⚠ Семантическая модель недоступна. Убедитесь, что sentence-transformers установлен."
                : `Ошибка: ${error}`}
            </div>
          )}

          {results && results.length === 0 && !loading && (
            <div style={{ marginTop: 10, color: "var(--text-3)", fontSize: 13 }}>Ничего не найдено.</div>
          )}

          {results && results.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: ".3px", marginBottom: 6 }}>
                Результаты · по убыванию сходства
              </div>
              <div className="rec-cards">
                {results.map(({ element, score }) => (
                  <label
                    key={element.id}
                    className={`rec-card${selections[element.id] ? " selected" : ""}`}
                    onClick={(e) => { e.preventDefault(); onToggle(element.id, !selections[element.id]); }}
                  >
                    <div className="rec-card__check">
                      <input type="checkbox" checked={Boolean(selections[element.id])} onChange={() => {}} style={{ pointerEvents: "none" }} />
                    </div>
                    <div className="rec-card__body">
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span className="rec-card__name" style={{ flex: 1 }}>{element.name}</span>
                        <ScoreBadge score={score} />
                      </div>
                      <div className="rec-card__meta">
                        <span className="rec-card__credits">{element.credits ?? 0} з.е.</span>
                        {element.semesters?.map((s) => <span key={s} className="sem-chip">С{s}</span>)}
                        <SourceBadge source={element.source} />
                      </div>
                      {element.competency_codes?.length > 0 && (
                        <div style={{ marginTop: 4, display: "flex", gap: 4, flexWrap: "wrap" }}>
                          {element.competency_codes.map((c) => <span key={c} className="comp-chip">{c}</span>)}
                        </div>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Table1({ plan, planId, onNotice, onRefresh, onNext }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selections, setSelections] = useState({});
  const [transferring, setTransferring] = useState(false);

  useEffect(() => {
    if (!planId) { setData(null); setSelections({}); return; }
    let cancelled = false;
    setLoading(true);
    setError("");
    getTable1(planId)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        const sel = {};
        const collect = (items) => items.forEach((i) => { sel[i.id] = i.selected; });
        d.fgos_disciplines.forEach((g) => collect(g.items));
        d.fgos_practices.forEach((g) => collect(g.items));
        d.competencies.forEach((s) => {
          collect(s.mandatory_disciplines);
          collect(s.variative_disciplines);
          collect(s.mandatory_practices);
        });
        setSelections(sel);
      })
      .catch((e) => { if (!cancelled) setError(getErrorMessage(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [planId]);

  const selectedCount = useMemo(() => Object.values(selections).filter(Boolean).length, [selections]);

  const summary = data?.selection_summary;
  const fgosOk = summary?.required_disciplines_complete && summary?.required_practices_complete;

  const toggle = (id, val) => setSelections((s) => ({ ...s, [id]: val }));
  const singleSelect = (group, itemId, val) => {
    setSelections((s) => {
      const next = { ...s };
      group.items.forEach((i) => { next[i.id] = false; });
      if (val) next[itemId] = true;
      return next;
    });
  };

  const handleTransfer = async () => {
    setTransferring(true);
    try {
      const payload = Object.entries(selections).map(([id, sel]) => ({
        element_id: Number(id),
        selected: sel,
      }));
      const result = await transferTable1(planId, payload);
      onNotice?.(`Перенос завершён. Добавлено: ${result.created_count}, обновлено: ${result.updated_count}.`, "success");
      onRefresh?.();
      onNext?.();
    } catch (e) {
      onNotice?.(getErrorMessage(e), "error");
    } finally {
      setTransferring(false);
    }
  };

  if (!plan) return null;

  if (loading) return (
    <EmptyState icon="⏳" title="Загрузка рекомендаций…" description="Получаем рекомендации ФГОС для вашей программы" />
  );
  if (error) return (
    <div className="notice notice-error"><span className="notice-icon">✗</span>{error}</div>
  );
  if (!data) return null;

  return (
    <div className="page-panel">
      <div className="section-header">
        <div>
          <div className="section-header__title">Рекомендации ФГОС</div>
          <div className="section-header__sub">
            Программа {plan.program_code} · Выберите дисциплины и практики для переноса в план
          </div>
        </div>
      </div>

      <SemanticSearchPanel planId={planId} selections={selections} onToggle={toggle} />

      <div className="rec-layout">
        {/* Left: cards */}
        <div>
          {/* FGOS mandatory disciplines */}
          {data.fgos_disciplines.length > 0 && (
            <>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 8 }}>
                Обязательные дисциплины ФГОС
              </div>
              {data.fgos_disciplines.map((group) => (
                <RecSection
                  key={group.requirement}
                  title={FGOS_LABELS[group.requirement] || group.title}
                  headerClass="fgos"
                  items={group.items}
                  selections={selections}
                  onToggle={toggle}
                  onSingleSelect={singleSelect}
                  group={group}
                />
              ))}
            </>
          )}

          {/* FGOS mandatory practices */}
          {data.fgos_practices.length > 0 && (
            <>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 8, marginTop: 16 }}>
                Обязательные практики ФГОС
              </div>
              {data.fgos_practices.map((group) => (
                <RecSection
                  key={group.requirement}
                  title={FGOS_LABELS[group.requirement] || group.title}
                  headerClass="fgos-practices"
                  items={group.items}
                  selections={selections}
                  onToggle={toggle}
                  onSingleSelect={singleSelect}
                  group={group}
                />
              ))}
            </>
          )}

          {/* Competency recommendations */}
          {data.competencies.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 8 }}>
                Рекомендации по компетенциям
              </div>
              {data.competencies.map((section) => {
                if (section.mode === "manual_only") {
                  return (
                    <div key={section.competency.id} className="rec-section">
                      <div className="rec-section-header" style={{ background: "var(--surface-2)" }}>
                        <span>{section.competency.code} — {section.competency.name}</span>
                        <span className="badge badge-manual" style={{ marginLeft: "auto" }}>Ручной режим (ПКС)</span>
                      </div>
                      <div className="rec-cards">
                        <div style={{ padding: "12px 16px", color: "var(--text-3)", fontSize: 13 }}>
                          ПКС не имеют автоматических рекомендаций. Добавьте дисциплины вручную в разделе «Учебный план» и свяжите их с этой компетенцией.
                        </div>
                      </div>
                    </div>
                  );
                }

                const allItems = [
                  ...section.mandatory_disciplines,
                  ...section.variative_disciplines,
                  ...section.mandatory_practices,
                ];

                if (allItems.length === 0) return null;

                const grouped = [
                  { title: "Дисциплины · Обязательная часть", items: section.mandatory_disciplines },
                  { title: "Дисциплины · Вариативная часть",  items: section.variative_disciplines },
                  { title: "Практики · Обязательная часть",   items: section.mandatory_practices },
                ].filter((g) => g.items.length > 0);

                return (
                  <div key={section.competency.id} className="rec-section">
                    <div className="rec-section-header">
                      <span>{section.competency.code} — {section.competency.name}</span>
                      <span className="rec-section-badge">{section.competency.type}</span>
                    </div>
                    <div className="rec-cards">
                      {grouped.map((g) => (
                        <div key={g.title}>
                          <div style={{
                            padding: "5px 16px",
                            fontSize: 11, fontWeight: 600, color: "var(--text-3)",
                            textTransform: "uppercase", letterSpacing: ".3px",
                            background: "var(--surface-2)", borderBottom: "1px solid var(--border)",
                          }}>
                            {g.title}
                          </div>
                          {g.items.map((item) => (
                            <RecCard
                              key={item.id}
                              item={item}
                              checked={Boolean(selections[item.id])}
                              onChange={toggle}
                            />
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {data.fgos_disciplines.length === 0 && data.fgos_practices.length === 0 && data.competencies.length === 0 && (
            <EmptyState
              icon="📭"
              title="Рекомендации не найдены"
              description="Для данной программы рекомендации отсутствуют. Добавьте дисциплины вручную на следующем шаге."
            />
          )}
        </div>

        {/* Right: sticky summary */}
        <div>
          <div className="rec-summary">
            <div className="rec-summary__header">Сводка выбора</div>
            <div className="rec-summary__body">
              <div className="card-section-title">Требования ФГОС</div>

              {summary?.required_disciplines_complete !== undefined && (
                <>
                  <div className={`req-row ${summary.required_disciplines_complete ? "ok" : summary.missing_discipline_requirements?.length ? "warn" : "pending"}`}>
                    <span className="req-row__icon">{summary.required_disciplines_complete ? "✓" : "○"}</span>
                    <span className="req-row__label">Дисциплины ФГОС</span>
                  </div>
                  {!summary.required_disciplines_complete && summary.missing_discipline_requirements?.length > 0 && (
                    <div style={{ paddingLeft: 24, fontSize: 11.5, color: "var(--warning)", lineHeight: 1.5 }}>
                      Не выбраны: {summary.missing_discipline_requirements.map((r) => FGOS_LABELS[r] || r).join(", ")}
                    </div>
                  )}
                  <div className={`req-row ${summary.required_practices_complete ? "ok" : "warn"}`}>
                    <span className="req-row__icon">{summary.required_practices_complete ? "✓" : "○"}</span>
                    <span className="req-row__label">Практики ФГОС</span>
                  </div>
                  {!summary.required_practices_complete && summary.missing_practice_requirements?.length > 0 && (
                    <div style={{ paddingLeft: 24, fontSize: 11.5, color: "var(--warning)", lineHeight: 1.5 }}>
                      Не выбраны: {summary.missing_practice_requirements.map((r) => FGOS_LABELS[r] || r).join(", ")}
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="rec-summary__count">
              Выбрано: <strong>{selectedCount}</strong> элементов
            </div>

            {!fgosOk && (
              <div style={{ padding: "8px 16px", fontSize: 12, color: "var(--warning)", borderTop: "1px solid var(--border)" }}>
                ⚠ Не все требования ФГОС выполнены. Вы всё равно можете перенести выбранное.
              </div>
            )}

            <div className="rec-summary__footer">
              <button
                className="btn btn-primary"
                style={{ width: "100%" }}
                onClick={handleTransfer}
                disabled={transferring || selectedCount === 0}
              >
                {transferring
                  ? <><span className="spinner" /> Перенос…</>
                  : `Перенести ${selectedCount > 0 ? `(${selectedCount})` : ""} в план →`
                }
              </button>
              {selectedCount === 0 && (
                <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-3)", textAlign: "center" }}>
                  Отметьте хотя бы одну дисциплину
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
