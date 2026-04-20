import { useEffect, useMemo, useState } from "react";

import {
  createTable2Element,
  deleteTable2Element,
  getErrorMessage,
  getTable2,
  listCompetencies,
  updateTable2Element,
} from "../api";
import CompetencyMultiSelect from "../components/CompetencyMultiSelect";
import EmptyState from "../components/EmptyState";
import HelpTooltip from "../components/HelpTooltip";
import StatusBadge from "../components/StatusBadge";

const defaultNewElement = {
  name: "",
  block: "1",
  part: "mandatory",
  credits: "3",
  extra_hours: "0",
  semesters: "1",
  competency_ids: [],
  practice_type: "",
  fgos_requirement: "",
};

const partLabels = {
  mandatory: "Обязательная часть",
  variative: "Вариативная часть",
};

const blockLabels = {
  "1": "Блок 1 · Дисциплины",
  "2": "Блок 2 · Практики",
  "3": "Блок 3 · ГИА",
  fac: "Факультативы",
};

const practiceTypeLabels = {
  educational: "Учебная",
  industrial: "Производственная",
};

const statusLabels = {
  draft: "Черновик",
  checked: "Проверен",
  approved: "Утверждён",
};

function buildCompetencyMap(groupedCompetencies) {
  return Object.fromEntries(
    Object.values(groupedCompetencies)
      .flat()
      .map((item) => [item.id, item]),
  );
}

function collectAllElements(groupedElements) {
  return Object.values(groupedElements || {}).flatMap((parts) => Object.values(parts).flat());
}

function parseSemesters(value) {
  if (!value || !String(value).trim()) return [];
  return [...new Set(
    String(value)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .map(Number)
      .filter((n) => Number.isInteger(n) && n > 0),
  )].sort((a, b) => a - b);
}

function formatSemesters(semesters) {
  if (!semesters || semesters.length === 0) return "—";
  return semesters.join(", ");
}

function toDraft(element) {
  return {
    name: element.name,
    block: element.block,
    part: element.part,
    credits: String(element.credits),
    extra_hours: String(element.extra_hours || 0),
    semesters: formatSemesters(element.semesters || []),
    competency_ids: element.competency_ids,
    practice_type: element.practice_type || "",
    fgos_requirement: element.fgos_requirement || "",
  };
}

function ElementFormFields({ value, onChange }) {
  return (
    <>
      <div className="form-grid">
        <label className="field">
          <span>Наименование</span>
          <input
            value={value.name}
            onChange={(e) => onChange("name", e.target.value)}
            placeholder="Название дисциплины или практики"
            required
          />
        </label>

        <label className="field">
          <span>Блок</span>
          <select value={value.block} onChange={(e) => onChange("block", e.target.value)}>
            <option value="1">Блок 1</option>
            <option value="2">Блок 2</option>
            <option value="3">Блок 3</option>
            <option value="fac">Факультативы</option>
          </select>
        </label>

        <label className="field">
          <div className="field-label-row">
            <span>Часть плана</span>
            <HelpTooltip text="Определяет принадлежность к обязательной или вариативной части. Для ГИА используйте обязательную часть." />
          </div>
          <select value={value.part} onChange={(e) => onChange("part", e.target.value)}>
            <option value="mandatory">Обязательная</option>
            <option value="variative">Вариативная</option>
          </select>
        </label>

        <label className="field">
          <span>Зачётные единицы</span>
          <input
            type="number"
            min="0"
            step="0.5"
            value={value.credits}
            onChange={(e) => onChange("credits", e.target.value)}
          />
        </label>

        <label className="field">
          <div className="field-label-row">
            <span>Доп. часы</span>
            <HelpTooltip text="Используются для «Физической культуры и спорта». Не переводятся в з.е., учитываются отдельно." />
          </div>
          <input
            type="number"
            min="0"
            step="1"
            value={value.extra_hours}
            onChange={(e) => onChange("extra_hours", e.target.value)}
          />
        </label>

        <label className="field">
          <div className="field-label-row">
            <span>Семестры</span>
            <HelpTooltip text="Один или несколько номеров через запятую." />
          </div>
          <input
            value={value.semesters}
            onChange={(e) => onChange("semesters", e.target.value)}
            placeholder="1, 2"
          />
        </label>

        <label className="field">
          <div className="field-label-row">
            <span>Тип практики</span>
            <HelpTooltip text="Обязательно для элементов Блока 2. Используется в проверках." />
          </div>
          <select value={value.practice_type} onChange={(e) => onChange("practice_type", e.target.value)}>
            <option value="">Не задан</option>
            <option value="educational">Учебная</option>
            <option value="industrial">Производственная</option>
          </select>
        </label>
      </div>

      <p className="form-note">
        Часы по з.е. рассчитываются автоматически (1 з.е. = 36 ч.). Итоговая нагрузка = часы по з.е. + дополнительные часы.
      </p>
    </>
  );
}

export default function Table2({ plan, planId, refreshToken, onRefresh, setGlobalNotice }) {
  const [data, setData] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [newElement, setNewElement] = useState(defaultNewElement);
  const [competencies, setCompetencies] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState(null);

  useEffect(() => {
    if (!planId) { setData(null); return; }

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const table2 = await getTable2(planId);
        if (cancelled) return;
        setData(table2);
        const nextDrafts = {};
        collectAllElements(table2.grouped_elements).forEach((el) => {
          nextDrafts[el.id] = toDraft(el);
        });
        setDrafts(nextDrafts);
      } catch (loadError) {
        if (!cancelled) setError(getErrorMessage(loadError, "Не удалось загрузить структуру плана."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [planId, refreshToken]);

  useEffect(() => {
    let cancelled = false;

    const loadCompetencies = async () => {
      try {
        const grouped = await listCompetencies();
        if (!cancelled) setCompetencies(grouped);
      } catch (loadError) {
        if (!cancelled) setGlobalNotice(getErrorMessage(loadError, "Не удалось загрузить компетенции."));
      }
    };

    loadCompetencies();
    return () => { cancelled = true; };
  }, [setGlobalNotice]);

  const competencyMap = useMemo(() => buildCompetencyMap(competencies), [competencies]);

  const updateDraft = (elementId, field, value) => {
    setDrafts((cur) => ({ ...cur, [elementId]: { ...cur[elementId], [field]: value } }));
  };

  const updateNewElement = (field, value) => {
    setNewElement((cur) => ({ ...cur, [field]: value }));
  };

  const normalizePayload = (draft) => ({
    name: draft.name,
    block: draft.block,
    part: draft.part,
    credits: Number(draft.credits),
    extra_hours: Number(draft.extra_hours || 0),
    semesters: parseSemesters(draft.semesters),
    competency_ids: draft.competency_ids,
    practice_type: draft.practice_type || null,
    fgos_requirement: draft.fgos_requirement || null,
  });

  const handleSaveElement = async (elementId) => {
    const draft = drafts[elementId];
    setSaving(true);
    try {
      await updateTable2Element(planId, elementId, normalizePayload(draft));
      setEditingId(null);
      onRefresh("Изменения сохранены.");
    } catch (saveError) {
      setGlobalNotice(getErrorMessage(saveError, "Не удалось сохранить изменения."));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteElement = async (element) => {
    const extra = element.fgos_requirement
      ? " Это нормативно значимый элемент — его удаление может заблокировать утверждение плана."
      : "";
    if (!window.confirm(`Удалить «${element.name}» из структуры плана?${extra}`)) return;

    setSaving(true);
    try {
      await deleteTable2Element(planId, element.id);
      onRefresh("Элемент удалён.");
    } catch (deleteError) {
      setGlobalNotice(getErrorMessage(deleteError, "Не удалось удалить элемент."));
    } finally {
      setSaving(false);
    }
  };

  const handleCreateElement = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await createTable2Element(planId, { ...normalizePayload(newElement), source_element_id: null });
      setNewElement(defaultNewElement);
      onRefresh("Элемент добавлен.");
    } catch (createError) {
      setGlobalNotice(getErrorMessage(createError, "Не удалось добавить элемент."));
    } finally {
      setSaving(false);
    }
  };

  if (!plan) {
    return <div className="card"><p>Сначала выберите учебный план.</p></div>;
  }

  return (
    <section className="stack-panel">
      {/* Header */}
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Шаг 2</p>
            <h2 style={{ fontSize: "18px" }}>Структура учебного плана</h2>
            <p className="status-muted" style={{ marginTop: "4px" }}>
              Все нормативные расчёты и проверки строятся только на данных этой таблицы.
            </p>
          </div>
          <StatusBadge value={plan.status}>{statusLabels[plan.status] || plan.status}</StatusBadge>
        </div>
        {loading ? <p className="status-muted">Загрузка структуры…</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

      {/* Aggregates */}
      {data ? (
        <div className="card totals-grid">
          <div className="metric-tile">
            <span>З.е. без факультативов</span>
            <strong>{data.aggregates.total_credits}</strong>
          </div>
          <div className="metric-tile">
            <span>Часы по з.е.</span>
            <strong>{data.aggregates.total_base_hours}</strong>
          </div>
          <div className="metric-tile">
            <span>Доп. часы</span>
            <strong>{data.aggregates.total_extra_hours}</strong>
          </div>
          <div className="metric-tile">
            <span>Суммарная нагрузка</span>
            <strong>{data.aggregates.total_hours}</strong>
          </div>
        </div>
      ) : null}

      {/* Add element form */}
      <form className="card stacked-form" onSubmit={handleCreateElement}>
        <div className="section-header">
          <div>
            <p className="card-kicker">Добавить элемент</p>
            <h3 style={{ fontSize: "15px" }}>Новая дисциплина или практика</h3>
          </div>
        </div>
        <ElementFormFields value={newElement} onChange={updateNewElement} />
        <CompetencyMultiSelect
          groupedCompetencies={competencies}
          selectedIds={newElement.competency_ids}
          onChange={(v) => updateNewElement("competency_ids", v)}
        />
        <button className="primary-button" type="submit" disabled={saving} style={{ justifySelf: "start" }}>
          {saving ? "Сохранение…" : "+ Добавить элемент"}
        </button>
      </form>

      {/* Inline edit form */}
      {editingId ? (
        <div className="card stacked-form">
          <div className="section-header">
            <div>
              <p className="card-kicker">Редактирование</p>
              <h3 style={{ fontSize: "15px" }}>
                {drafts[editingId]?.name || "Изменить элемент"}
              </h3>
            </div>
            <button type="button" className="secondary-button" onClick={() => setEditingId(null)}>
              Закрыть
            </button>
          </div>
          <ElementFormFields
            value={drafts[editingId]}
            onChange={(field, value) => updateDraft(editingId, field, value)}
          />
          <CompetencyMultiSelect
            groupedCompetencies={competencies}
            selectedIds={drafts[editingId]?.competency_ids || []}
            onChange={(v) => updateDraft(editingId, "competency_ids", v)}
          />
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              className="primary-button"
              type="button"
              onClick={() => handleSaveElement(editingId)}
              disabled={saving}
            >
              {saving ? "Сохранение…" : "Сохранить изменения"}
            </button>
            <button type="button" className="secondary-button" onClick={() => setEditingId(null)}>
              Отмена
            </button>
          </div>
        </div>
      ) : null}

      {/* Empty state */}
      {!loading && !error && data && collectAllElements(data.grouped_elements).length === 0 ? (
        <EmptyState
          title="Структура плана пуста"
          description="Перенесите элементы из Таблицы 1 или добавьте их вручную с помощью формы выше."
        />
      ) : null}

      {/* Grouped elements by block */}
      {data
        ? Object.entries(data.grouped_elements).map(([block, parts]) => (
            <div key={block} className="card">
              <div className="section-header">
                <div>
                  <p className="card-kicker">Состав плана</p>
                  <h3 style={{ fontSize: "15px" }}>{blockLabels[block] || `Блок ${block}`}</h3>
                </div>
              </div>

              {Object.entries(parts).map(([part, elements]) => (
                <div key={part} className="part-section">
                  <h4>{partLabels[part] || part}</h4>
                  {!elements.length ? (
                    <p className="status-muted">В этой части пока нет элементов.</p>
                  ) : (
                    <div className="table-scroll">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th style={{ minWidth: "180px" }}>Наименование</th>
                            <th>Семестры</th>
                            <th>З.е.</th>
                            <th>Часы</th>
                            <th>Доп. ч.</th>
                            <th>Итого ч.</th>
                            <th style={{ minWidth: "120px" }}>Компетенции</th>
                            <th>Действия</th>
                          </tr>
                        </thead>
                        <tbody>
                          {elements.map((element) => (
                            <tr key={element.id}>
                              <td>
                                <strong>{element.name}</strong>
                                <div className="table-secondary">
                                  {[
                                    element.practice_type && practiceTypeLabels[element.practice_type]
                                      ? `${practiceTypeLabels[element.practice_type]} практика`
                                      : null,
                                    element.fgos_requirement
                                      ? "Норматив ФГОС"
                                      : "Пользовательский",
                                  ]
                                    .filter(Boolean)
                                    .join(" · ")}
                                </div>
                              </td>
                              <td>{formatSemesters(element.semesters)}</td>
                              <td>{element.credits}</td>
                              <td>{element.hours}</td>
                              <td>{element.extra_hours || 0}</td>
                              <td>{element.total_hours}</td>
                              <td>
                                <div className="selected-tags">
                                  {element.competency_ids
                                    .filter((id) => competencyMap[id])
                                    .map((id) => (
                                      <span
                                        key={id}
                                        className="selected-tag light"
                                        title={competencyMap[id].name}
                                      >
                                        {competencyMap[id].code}
                                      </span>
                                    ))}
                                </div>
                              </td>
                              <td>
                                <div className="row-actions">
                                  <button
                                    className="small-button"
                                    type="button"
                                    onClick={() => setEditingId(element.id)}
                                  >
                                    Изменить
                                  </button>
                                  <button
                                    className="small-button danger"
                                    type="button"
                                    onClick={() => handleDeleteElement(element)}
                                    disabled={saving}
                                  >
                                    Удалить
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))
        : null}
    </section>
  );
}
