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
  semesters: "1",
  competency_ids: [],
};

const partLabels = {
  mandatory: "Обязательная часть",
  variative: "Вариативная часть",
};

const blockLabels = {
  "1": "Блок 1. Дисциплины",
  "2": "Блок 2. Практики",
  "3": "Блок 3. ГИА",
  fac: "Факультативы",
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
  if (!value || !String(value).trim()) {
    return [];
  }

  const normalized = String(value)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item) && item > 0);

  return [...new Set(normalized)].sort((left, right) => left - right);
}

function formatSemesters(semesters) {
  if (!semesters || semesters.length === 0) {
    return "—";
  }
  return semesters.join(", ");
}

function toDraft(element) {
  return {
    name: element.name,
    block: element.block,
    part: element.part,
    credits: String(element.credits),
    semesters: formatSemesters(element.semesters || []),
    competency_ids: element.competency_ids,
  };
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
    if (!planId) {
      setData(null);
      return;
    }

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const table2 = await getTable2(planId);
        if (cancelled) {
          return;
        }
        setData(table2);
        const nextDrafts = {};
        collectAllElements(table2.grouped_elements).forEach((element) => {
          nextDrafts[element.id] = toDraft(element);
        });
        setDrafts(nextDrafts);
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, "Не удалось загрузить структуру плана."));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [planId, refreshToken]);

  useEffect(() => {
    let cancelled = false;

    const loadCompetencies = async () => {
      try {
        const grouped = await listCompetencies();
        if (!cancelled) {
          setCompetencies(grouped);
        }
      } catch (loadError) {
        if (!cancelled) {
          setGlobalNotice(getErrorMessage(loadError, "Не удалось загрузить список компетенций."));
        }
      }
    };

    loadCompetencies();
    return () => {
      cancelled = true;
    };
  }, [setGlobalNotice]);

  const competencyMap = useMemo(() => buildCompetencyMap(competencies), [competencies]);

  const updateDraft = (elementId, field, value) => {
    setDrafts((current) => ({
      ...current,
      [elementId]: {
        ...current[elementId],
        [field]: value,
      },
    }));
  };

  const handleSaveElement = async (elementId) => {
    const draft = drafts[elementId];
    setSaving(true);
    try {
      await updateTable2Element(planId, elementId, {
        name: draft.name,
        block: draft.block,
        part: draft.part,
        credits: Number(draft.credits),
        semesters: parseSemesters(draft.semesters),
        competency_ids: draft.competency_ids,
      });
      setEditingId(null);
      onRefresh("Изменения в структуре плана сохранены.");
    } catch (saveError) {
      setGlobalNotice(getErrorMessage(saveError, "Не удалось сохранить изменения."));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteElement = async (elementId) => {
    const currentElement = collectAllElements(data?.grouped_elements).find((element) => element.id === elementId);
    if (!window.confirm(`Удалить элемент «${currentElement?.name || "без названия"}» из структуры плана?`)) {
      return;
    }

    setSaving(true);
    try {
      await deleteTable2Element(planId, elementId);
      onRefresh("Элемент удален из структуры плана.");
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
      await createTable2Element(planId, {
        name: newElement.name,
        block: newElement.block,
        part: newElement.part,
        credits: Number(newElement.credits),
        semesters: parseSemesters(newElement.semesters),
        competency_ids: newElement.competency_ids,
        source_element_id: null,
      });
      setNewElement(defaultNewElement);
      onRefresh("Новый элемент добавлен в структуру плана.");
    } catch (createError) {
      setGlobalNotice(getErrorMessage(createError, "Не удалось добавить элемент."));
    } finally {
      setSaving(false);
    }
  };

  if (!plan) {
    return (
      <section className="card">
        <h2>Структура плана</h2>
        <p>Сначала выберите учебный план на стартовом экране.</p>
      </section>
    );
  }

  return (
    <section className="stack-panel">
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Структура плана</p>
            <h2>Рабочая структура учебного плана</h2>
          </div>
          <StatusBadge value={plan.status} />
        </div>
        <p className="status-muted">
          Здесь редактируется итоговая структура учебного плана. Часы рассчитываются автоматически по количеству
          зачетных единиц, а многосеместровые элементы хранятся одной строкой.
        </p>
        {loading ? <p className="status-muted">Загрузка структуры плана...</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

      {data ? (
        <div className="card totals-grid">
          <div className="metric-tile">
            <span>Всего з.е.</span>
            <strong>{data.aggregates.total_credits}</strong>
          </div>
          <div className="metric-tile">
            <span>Всего часов</span>
            <strong>{data.aggregates.total_hours}</strong>
          </div>
          {Object.entries(data.aggregates.by_block).map(([block, value]) => (
            <div key={block} className="metric-tile">
              <span>{blockLabels[block] || `Блок ${block}`}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      ) : null}

      <form className="card stacked-form" onSubmit={handleCreateElement}>
        <div className="section-header">
          <div>
            <p className="card-kicker">Ручное добавление</p>
            <h3>Добавить элемент</h3>
          </div>
        </div>

        <div className="form-grid">
          <label className="field">
            <span>Наименование</span>
            <input
              value={newElement.name}
              onChange={(event) => setNewElement((current) => ({ ...current, name: event.target.value }))}
              required
            />
          </label>
          <label className="field">
            <span>Блок</span>
            <select
              value={newElement.block}
              onChange={(event) => setNewElement((current) => ({ ...current, block: event.target.value }))}
            >
              <option value="1">Блок 1</option>
              <option value="2">Блок 2</option>
              <option value="3">Блок 3</option>
              <option value="fac">Факультативы</option>
            </select>
          </label>
          <label className="field">
            <div className="field-label-row">
              <span>Часть плана</span>
              <HelpTooltip text="Определяет, относится элемент к обязательной или вариативной части плана." />
            </div>
            <select
              value={newElement.part}
              onChange={(event) => setNewElement((current) => ({ ...current, part: event.target.value }))}
            >
              <option value="mandatory">Обязательная часть</option>
              <option value="variative">Вариативная часть</option>
            </select>
          </label>
          <label className="field">
            <span>З.е.</span>
            <input
              type="number"
              min="0"
              step="0.5"
              value={newElement.credits}
              onChange={(event) => setNewElement((current) => ({ ...current, credits: event.target.value }))}
            />
          </label>
          <label className="field">
            <div className="field-label-row">
              <span>Семестры</span>
              <HelpTooltip text="Укажите один или несколько семестров через запятую, например: 1, 2, 3." />
            </div>
            <input
              value={newElement.semesters}
              onChange={(event) => setNewElement((current) => ({ ...current, semesters: event.target.value }))}
              placeholder="Например: 1, 2, 3"
            />
          </label>
        </div>

        <div className="form-note">
          <span>Часы рассчитываются автоматически по количеству з.е.</span>
          <HelpTooltip text="Поле часов не редактируется вручную и пересчитывается системой автоматически." />
        </div>

        <CompetencyMultiSelect
          groupedCompetencies={competencies}
          selectedIds={newElement.competency_ids}
          onChange={(value) => setNewElement((current) => ({ ...current, competency_ids: value }))}
        />

        <button className="primary-button" type="submit" disabled={saving}>
          {saving ? "Сохранение..." : "Добавить элемент"}
        </button>
      </form>

      {editingId ? (
        <div className="card stacked-form">
          <div className="section-header">
            <div>
              <p className="card-kicker">Редактирование</p>
              <h3>Изменить элемент</h3>
            </div>
            <button type="button" className="secondary-button" onClick={() => setEditingId(null)}>
              Закрыть
            </button>
          </div>

          <div className="form-grid">
            <label className="field">
              <span>Наименование</span>
              <input
                value={drafts[editingId]?.name || ""}
                onChange={(event) => updateDraft(editingId, "name", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Блок</span>
              <select
                value={drafts[editingId]?.block || "1"}
                onChange={(event) => updateDraft(editingId, "block", event.target.value)}
              >
                <option value="1">Блок 1</option>
                <option value="2">Блок 2</option>
                <option value="3">Блок 3</option>
                <option value="fac">Факультативы</option>
              </select>
            </label>
            <label className="field">
              <div className="field-label-row">
                <span>Часть плана</span>
                <HelpTooltip text="Определяет, относится элемент к обязательной или вариативной части плана." />
              </div>
              <select
                value={drafts[editingId]?.part || "mandatory"}
                onChange={(event) => updateDraft(editingId, "part", event.target.value)}
              >
                <option value="mandatory">Обязательная часть</option>
                <option value="variative">Вариативная часть</option>
              </select>
            </label>
            <label className="field">
              <span>З.е.</span>
              <input
                type="number"
                step="0.5"
                value={drafts[editingId]?.credits || ""}
                onChange={(event) => updateDraft(editingId, "credits", event.target.value)}
              />
            </label>
            <label className="field">
              <div className="field-label-row">
                <span>Семестры</span>
                <HelpTooltip text="Укажите один или несколько семестров через запятую, например: 1, 2, 3." />
              </div>
              <input
                value={drafts[editingId]?.semesters || ""}
                onChange={(event) => updateDraft(editingId, "semesters", event.target.value)}
              />
            </label>
          </div>

          <div className="form-note">
            <span>Часы пересчитываются автоматически после сохранения изменений.</span>
            <HelpTooltip text="Поле часов вычисляется системой, поэтому отдельно не редактируется." />
          </div>

          <CompetencyMultiSelect
            groupedCompetencies={competencies}
            selectedIds={drafts[editingId]?.competency_ids || []}
            onChange={(value) => updateDraft(editingId, "competency_ids", value)}
          />

          <button className="primary-button" type="button" onClick={() => handleSaveElement(editingId)} disabled={saving}>
            {saving ? "Сохранение..." : "Сохранить изменения"}
          </button>
        </div>
      ) : null}

      {!loading && !error && data && collectAllElements(data.grouped_elements).length === 0 ? (
        <EmptyState
          title="Структура плана пока пуста"
          description="Перенесите рекомендации с предыдущего экрана или добавьте элементы вручную."
        />
      ) : null}

      {data
        ? Object.entries(data.grouped_elements).map(([block, parts]) => (
            <div key={block} className="card">
              <div className="section-header">
                <div>
                  <p className="card-kicker">Состав плана</p>
                  <h3>{blockLabels[block] || `Блок ${block}`}</h3>
                </div>
              </div>

              {Object.entries(parts).map(([part, elements]) => (
                <div key={part} className="part-section">
                  <h4>{partLabels[part] || part}</h4>
                  {elements.length === 0 ? (
                    <p className="status-muted">В этой части пока нет элементов.</p>
                  ) : (
                    <div className="table-scroll">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Наименование</th>
                            <th>Семестры</th>
                            <th>З.е.</th>
                            <th>Часы</th>
                            <th>Компетенции</th>
                            <th>Действия</th>
                          </tr>
                        </thead>
                        <tbody>
                          {elements.map((element) => (
                            <tr key={element.id}>
                              <td>
                                <strong>{element.name}</strong>
                                <div className="table-secondary">
                                  {(blockLabels[element.block] || `Блок ${element.block}`) +
                                    " · " +
                                    (partLabels[element.part] || element.part)}
                                </div>
                              </td>
                              <td>{formatSemesters(element.semesters)}</td>
                              <td>{element.credits}</td>
                              <td>{element.hours}</td>
                              <td>
                                <div className="selected-tags">
                                  {element.competency_ids
                                    .filter((competencyId) => competencyMap[competencyId])
                                    .map((competencyId) => (
                                      <span
                                        key={competencyId}
                                        className="selected-tag light"
                                        title={competencyMap[competencyId].name}
                                      >
                                        {competencyMap[competencyId].code}
                                      </span>
                                    ))}
                                </div>
                              </td>
                              <td>
                                <div className="row-actions">
                                  <button className="small-button" type="button" onClick={() => setEditingId(element.id)}>
                                    Изменить
                                  </button>
                                  <button
                                    className="small-button danger"
                                    type="button"
                                    onClick={() => handleDeleteElement(element.id)}
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
