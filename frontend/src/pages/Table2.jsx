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
  "1": "Блок 1. Дисциплины",
  "2": "Блок 2. Практики",
  "3": "Блок 3. ГИА",
  fac: "Факультативы",
};

const practiceTypeLabels = {
  educational: "Учебная",
  industrial: "Производственная",
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
          <input value={value.name} onChange={(event) => onChange("name", event.target.value)} required />
        </label>
        <label className="field">
          <span>Блок</span>
          <select value={value.block} onChange={(event) => onChange("block", event.target.value)}>
            <option value="1">Блок 1</option>
            <option value="2">Блок 2</option>
            <option value="3">Блок 3</option>
            <option value="fac">Факультативы</option>
          </select>
        </label>
        <label className="field">
          <div className="field-label-row">
            <span>Часть плана</span>
            <HelpTooltip text="Определяет принадлежность элемента к обязательной или вариативной части. Для ГИА используйте обязательную часть." />
          </div>
          <select value={value.part} onChange={(event) => onChange("part", event.target.value)}>
            <option value="mandatory">Обязательная часть</option>
            <option value="variative">Вариативная часть</option>
          </select>
        </label>
        <label className="field">
          <span>З.е.</span>
          <input type="number" min="0" step="0.5" value={value.credits} onChange={(event) => onChange("credits", event.target.value)} />
        </label>
        <label className="field">
          <div className="field-label-row">
            <span>Дополнительные часы</span>
            <HelpTooltip text="Используются, например, для дисциплины «Физическая культура и спорт». Эти часы не переводятся в з.е. и учитываются отдельно." />
          </div>
          <input type="number" min="0" step="1" value={value.extra_hours} onChange={(event) => onChange("extra_hours", event.target.value)} />
        </label>
        <label className="field">
          <div className="field-label-row">
            <span>Семестры</span>
            <HelpTooltip text="Можно указать один или несколько семестров через запятую." />
          </div>
          <input value={value.semesters} onChange={(event) => onChange("semesters", event.target.value)} placeholder="Например: 1, 2, 3" />
        </label>
        <label className="field">
          <div className="field-label-row">
            <span>Тип практики</span>
            <HelpTooltip text="Обязательный атрибут для элементов блока 2. Используется в проверках учебной и производственной практики." />
          </div>
          <select value={value.practice_type} onChange={(event) => onChange("practice_type", event.target.value)}>
            <option value="">Не задан</option>
            <option value="educational">Учебная</option>
            <option value="industrial">Производственная</option>
          </select>
        </label>
      </div>
      <div className="form-note">
        <span>Часы по з.е. рассчитываются автоматически. Итоговая нагрузка элемента = часы по з.е. + дополнительные часы.</span>
      </div>
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

  const updateNewElement = (field, value) => {
    setNewElement((current) => ({ ...current, [field]: value }));
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
      onRefresh("Изменения в Таблице 2 сохранены.");
    } catch (saveError) {
      setGlobalNotice(getErrorMessage(saveError, "Не удалось сохранить изменения."));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteElement = async (element) => {
    const warning = element.fgos_requirement
      ? " Это нормативно значимый элемент, его удаление может заблокировать утверждение плана."
      : "";
    if (!window.confirm(`Удалить элемент «${element.name}» из Таблицы 2?${warning}`)) {
      return;
    }

    setSaving(true);
    try {
      await deleteTable2Element(planId, element.id);
      onRefresh("Элемент удалён из Таблицы 2.");
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
        ...normalizePayload(newElement),
        source_element_id: null,
      });
      setNewElement(defaultNewElement);
      onRefresh("Новый элемент добавлен в Таблицу 2.");
    } catch (createError) {
      setGlobalNotice(getErrorMessage(createError, "Не удалось добавить элемент."));
    } finally {
      setSaving(false);
    }
  };

  if (!plan) {
    return (
      <section className="card">
        <h2>Таблица 2</h2>
        <p>Сначала выберите учебный план на стартовом экране.</p>
      </section>
    );
  }

  return (
    <section className="stack-panel">
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Таблица 2</p>
            <h2>Структура учебного плана</h2>
          </div>
          <StatusBadge value={plan.status} />
        </div>
        <p className="status-muted">
          Здесь фиксируется итоговая структура плана. Все расчёты и нормативные проверки строятся только на данных Таблицы 2.
        </p>
        {loading ? <p className="status-muted">Загрузка Таблицы 2...</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

      {data ? (
        <div className="card totals-grid">
          <div className="metric-tile">
            <span>Всего з.е. без факультативов</span>
            <strong>{data.aggregates.total_credits}</strong>
          </div>
          <div className="metric-tile">
            <span>Часы по з.е.</span>
            <strong>{data.aggregates.total_base_hours}</strong>
          </div>
          <div className="metric-tile">
            <span>Дополнительные часы</span>
            <strong>{data.aggregates.total_extra_hours}</strong>
          </div>
          <div className="metric-tile">
            <span>Суммарная нагрузка</span>
            <strong>{data.aggregates.total_hours}</strong>
          </div>
        </div>
      ) : null}

      <form className="card stacked-form" onSubmit={handleCreateElement}>
        <div className="section-header">
          <div>
            <p className="card-kicker">Ручное добавление</p>
            <h3>Добавить элемент в Таблицу 2</h3>
          </div>
        </div>

        <ElementFormFields value={newElement} onChange={updateNewElement} />

        <CompetencyMultiSelect
          groupedCompetencies={competencies}
          selectedIds={newElement.competency_ids}
          onChange={(value) => updateNewElement("competency_ids", value)}
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

          <ElementFormFields value={drafts[editingId]} onChange={(field, value) => updateDraft(editingId, field, value)} />

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
          title="Таблица 2 пока пуста"
          description="Перенесите элементы из Таблицы 1 или добавьте их вручную."
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
                  {!elements.length ? (
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
                            <th>Доп. часы</th>
                            <th>Итого часов</th>
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
                                  {(element.practice_type && practiceTypeLabels[element.practice_type]
                                    ? `${practiceTypeLabels[element.practice_type]} практика · `
                                    : "") +
                                    (element.fgos_requirement ? "Нормативный элемент ФГОС" : "Пользовательский/рекомендованный элемент")}
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
