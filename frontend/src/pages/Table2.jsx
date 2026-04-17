import { useEffect, useState } from "react";

import {
  createTable2Element,
  deleteTable2Element,
  getErrorMessage,
  getTable2,
  updateTable2Element,
} from "../api";

const defaultNewElement = {
  name: "",
  block: "1",
  part: "mandatory",
  credits: "3",
  semester: "1",
  competency_ids: "",
};

const partLabels = {
  mandatory: "Обязательная часть",
  variative: "Вариативная часть",
};

function toCompetencyIds(value) {
  return String(value)
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item) && item > 0);
}

export default function Table2({ plan, planId, refreshToken, onRefresh, setGlobalNotice }) {
  const [data, setData] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [newElement, setNewElement] = useState(defaultNewElement);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

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
        Object.values(table2.grouped_elements).forEach((parts) => {
          Object.values(parts).forEach((elements) => {
            elements.forEach((element) => {
              nextDrafts[element.id] = {
                name: element.name,
                block: element.block,
                part: element.part,
                credits: String(element.credits),
                semester: element.semester == null ? "" : String(element.semester),
                competency_ids: element.competency_ids.join(", "),
              };
            });
          });
        });
        setDrafts(nextDrafts);
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, "Не удалось загрузить Таблицу 2."));
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
        semester: draft.semester === "" ? null : Number(draft.semester),
        competency_ids: toCompetencyIds(draft.competency_ids),
      });
      onRefresh("Строка Таблицы 2 обновлена.");
    } catch (saveError) {
      setGlobalNotice(getErrorMessage(saveError, "Не удалось сохранить строку."));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteElement = async (elementId) => {
    setSaving(true);
    try {
      await deleteTable2Element(planId, elementId);
      onRefresh("Строка удалена из Таблицы 2.");
    } catch (deleteError) {
      setGlobalNotice(getErrorMessage(deleteError, "Не удалось удалить строку."));
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
        semester: newElement.semester === "" ? null : Number(newElement.semester),
        competency_ids: toCompetencyIds(newElement.competency_ids),
        source_element_id: null,
      });
      setNewElement(defaultNewElement);
      onRefresh("Новая строка добавлена в Таблицу 2.");
    } catch (createError) {
      setGlobalNotice(getErrorMessage(createError, "Не удалось добавить строку."));
    } finally {
      setSaving(false);
    }
  };

  if (!plan) {
    return (
      <section className="card">
        <h2>Таблица 2</h2>
        <p>Сначала выбери или создай учебный план.</p>
      </section>
    );
  }

  return (
    <section className="stack-panel">
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Таблица 2</p>
            <h2>Рабочая структура учебного плана</h2>
          </div>
        </div>
        <p className="status-muted">
          Здесь редактируется итоговый состав учебного плана. Поле часов вычисляется автоматически на
          backend.
        </p>
        {loading ? <p className="status-muted">Загрузка структуры плана...</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

      <form className="card stacked-form" onSubmit={handleCreateElement}>
        <div className="section-header">
          <h3>Добавить строку</h3>
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
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="3">3</option>
              <option value="fac">fac</option>
            </select>
          </label>
          <label className="field">
            <span>Часть</span>
            <select
              value={newElement.part}
              onChange={(event) => setNewElement((current) => ({ ...current, part: event.target.value }))}
            >
              <option value="mandatory">mandatory</option>
              <option value="variative">variative</option>
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
            <span>Семестр</span>
            <input
              type="number"
              min="1"
              value={newElement.semester}
              onChange={(event) => setNewElement((current) => ({ ...current, semester: event.target.value }))}
            />
          </label>
          <label className="field field-wide">
            <span>Competency IDs</span>
            <input
              value={newElement.competency_ids}
              onChange={(event) =>
                setNewElement((current) => ({ ...current, competency_ids: event.target.value }))
              }
              placeholder="1, 2, 3"
            />
          </label>
        </div>
        <button className="primary-button" type="submit" disabled={saving}>
          {saving ? "Сохранение..." : "Добавить строку"}
        </button>
      </form>

      {data ? (
        <>
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
                <span>Блок {block}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>

          {Object.entries(data.grouped_elements).map(([block, parts]) => (
            <div key={block} className="card">
              <div className="section-header">
                <h3>Блок {block}</h3>
              </div>
              {Object.entries(parts).map(([part, elements]) => (
                <div key={part} className="part-section">
                  <h4>{partLabels[part] || part}</h4>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Наименование</th>
                          <th>Блок</th>
                          <th>Часть</th>
                          <th>Семестр</th>
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
                              <input
                                value={drafts[element.id]?.name || ""}
                                onChange={(event) => updateDraft(element.id, "name", event.target.value)}
                              />
                            </td>
                            <td>
                              <select
                                value={drafts[element.id]?.block || "1"}
                                onChange={(event) => updateDraft(element.id, "block", event.target.value)}
                              >
                                <option value="1">1</option>
                                <option value="2">2</option>
                                <option value="3">3</option>
                                <option value="fac">fac</option>
                              </select>
                            </td>
                            <td>
                              <select
                                value={drafts[element.id]?.part || "mandatory"}
                                onChange={(event) => updateDraft(element.id, "part", event.target.value)}
                              >
                                <option value="mandatory">mandatory</option>
                                <option value="variative">variative</option>
                              </select>
                            </td>
                            <td>
                              <input
                                type="number"
                                value={drafts[element.id]?.semester || ""}
                                onChange={(event) => updateDraft(element.id, "semester", event.target.value)}
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                step="0.5"
                                value={drafts[element.id]?.credits || ""}
                                onChange={(event) => updateDraft(element.id, "credits", event.target.value)}
                              />
                            </td>
                            <td>
                              <input value={element.hours} readOnly className="readonly-input" />
                            </td>
                            <td>
                              <input
                                value={drafts[element.id]?.competency_ids || ""}
                                onChange={(event) =>
                                  updateDraft(element.id, "competency_ids", event.target.value)
                                }
                              />
                            </td>
                            <td>
                              <div className="row-actions">
                                <button
                                  className="small-button"
                                  type="button"
                                  onClick={() => handleSaveElement(element.id)}
                                  disabled={saving}
                                >
                                  Сохранить
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
                </div>
              ))}
            </div>
          ))}
        </>
      ) : null}
    </section>
  );
}
