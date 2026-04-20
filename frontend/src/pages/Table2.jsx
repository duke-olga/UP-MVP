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

const BLOCK_LABELS = {
  "1": "Блок 1 — Дисциплины",
  "2": "Блок 2 — Практики",
  "3": "Блок 3 — ГИА",
  fac: "Факультативные дисциплины",
};
const PART_LABELS = { mandatory: "Обязательная часть", variative: "Вариативная часть" };
const PRACTICE_LABELS = { educational: "Учебная практика", industrial: "Производственная практика" };

const EMPTY_FORM = {
  name: "", block: "1", part: "mandatory",
  credits: "3", extra_hours: "0", semesters: "1",
  competency_ids: [], practice_type: "", fgos_requirement: "",
};

function parseSemesters(v) {
  if (!v && v !== 0) return [];
  return [...new Set(
    String(v).split(",").map((s) => s.trim()).filter(Boolean)
      .map(Number).filter((n) => Number.isInteger(n) && n > 0)
  )].sort((a, b) => a - b);
}

function fmtSems(semesters) {
  return semesters?.length ? semesters.join(", ") : "—";
}

function normalizePayload(d) {
  return {
    name: d.name.trim(),
    block: d.block,
    part: d.part,
    credits: Number(d.credits),
    extra_hours: Number(d.extra_hours || 0),
    semesters: parseSemesters(d.semesters),
    competency_ids: d.competency_ids,
    practice_type: d.practice_type || null,
    fgos_requirement: d.fgos_requirement || null,
  };
}

function toDraft(el) {
  return {
    name: el.name,
    block: el.block,
    part: el.part,
    credits: String(el.credits),
    extra_hours: String(el.extra_hours || 0),
    semesters: fmtSems(el.semesters || []).replace(/^—$/, ""),
    competency_ids: el.competency_ids,
    practice_type: el.practice_type || "",
    fgos_requirement: el.fgos_requirement || "",
  };
}

function collectAll(grouped) {
  return Object.values(grouped || {}).flatMap((parts) => Object.values(parts).flat());
}

function buildCompMap(grouped) {
  return Object.fromEntries(Object.values(grouped).flat().map((c) => [c.id, c]));
}

/* -------------------------------------------------- Inline form ---- */
function ElementForm({ value, onChange, competencies, saving, onSave, onCancel, isNew }) {
  return (
    <div className="inline-edit-form">
      <div className="inline-edit-grid">
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label>Наименование</label>
          <input
            type="text"
            value={value.name}
            onChange={(e) => onChange("name", e.target.value)}
            placeholder="Название дисциплины или практики"
            autoFocus={isNew}
          />
        </div>
        <div className="field">
          <label>Блок</label>
          <select value={value.block} onChange={(e) => onChange("block", e.target.value)}>
            <option value="1">Блок 1</option>
            <option value="2">Блок 2</option>
            <option value="3">Блок 3</option>
            <option value="fac">Факультативы</option>
          </select>
        </div>
        <div className="field">
          <label>Часть</label>
          <select value={value.part} onChange={(e) => onChange("part", e.target.value)}>
            <option value="mandatory">Обязательная</option>
            <option value="variative">Вариативная</option>
          </select>
        </div>
        <div className="field">
          <label>З.е.</label>
          <input type="number" min="0" step="0.5" value={value.credits} onChange={(e) => onChange("credits", e.target.value)} />
        </div>
        <div className="field">
          <label>Семестры</label>
          <input type="text" value={value.semesters} onChange={(e) => onChange("semesters", e.target.value)} placeholder="1, 2" />
        </div>
      </div>
      <div className="inline-edit-grid-2">
        <div className="field">
          <label>Доп. часы</label>
          <input type="number" min="0" step="1" value={value.extra_hours} onChange={(e) => onChange("extra_hours", e.target.value)} />
        </div>
        <div className="field">
          <label>Тип практики</label>
          <select value={value.practice_type} onChange={(e) => onChange("practice_type", e.target.value)}>
            <option value="">—</option>
            <option value="educational">Учебная</option>
            <option value="industrial">Производственная</option>
          </select>
        </div>
      </div>
      <div className="field">
        <label>Компетенции</label>
        <CompetencyMultiSelect
          groupedCompetencies={competencies}
          selectedIds={value.competency_ids}
          onChange={(v) => onChange("competency_ids", v)}
        />
      </div>
      <div style={{ fontSize: 12, color: "var(--text-3)" }}>
        Часы рассчитываются автоматически: 1 з.е. = 36 ч. Доп. часы учитываются отдельно.
      </div>
      <div className="inline-edit-actions">
        <button className="btn btn-secondary btn-sm" type="button" onClick={onCancel}>Отмена</button>
        <button
          className="btn btn-primary btn-sm" type="button"
          onClick={onSave} disabled={saving || !value.name.trim()}
        >
          {saving ? <><span className="spinner" /> Сохранение…</> : isNew ? "Добавить" : "Сохранить"}
        </button>
      </div>
    </div>
  );
}

/* -------------------------------------------------- Block section -- */
function BlockSection({ block, parts, competencies, competencyMap, onEdit, onDelete, editingId, drafts, onDraftChange, onSave, onCancelEdit, saving, showAddForm, onShowAdd, addDraft, onAddChange, onAdd }) {
  const [open, setOpen] = useState(true);
  const totalCredits = Object.values(parts).flat().reduce((s, e) => s + (e.credits || 0), 0);

  return (
    <div className="block-section">
      <button className={`block-toggle${open ? " open" : ""}`} onClick={() => setOpen((o) => !o)} type="button">
        <span className="block-toggle__arrow">▶</span>
        <span className="block-toggle__title">{BLOCK_LABELS[block] || `Блок ${block}`}</span>
        <span className="block-toggle__credits">{totalCredits.toFixed(1)} з.е.</span>
      </button>

      {open && (
        <div className="block-body">
          {Object.entries(parts).map(([part, elements]) => (
            <div key={part} className="part-section">
              <div className="part-header">
                {PART_LABELS[part] || part}
                <span className="part-header__count">{elements.length}</span>
              </div>

              {elements.length > 0 && (
                <div className="curr-table-wrap">
                  <table className="curr-table">
                    <thead>
                      <tr>
                        <th className="col-name">Наименование</th>
                        <th className="col-sems">Семестры</th>
                        <th className="col-num">З.е.</th>
                        <th className="col-num">Часы</th>
                        <th className="col-num">Доп.ч.</th>
                        <th className="col-comp">Компетенции</th>
                        <th className="col-act"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {elements.map((el) =>
                        editingId === el.id ? (
                          <tr key={el.id} className="editing">
                            <td colSpan={7} style={{ padding: "16px" }}>
                              <ElementForm
                                value={drafts[el.id]}
                                onChange={(f, v) => onDraftChange(el.id, f, v)}
                                competencies={competencies}
                                saving={saving}
                                onSave={() => onSave(el.id)}
                                onCancel={onCancelEdit}
                                isNew={false}
                              />
                            </td>
                          </tr>
                        ) : (
                          <tr key={el.id}>
                            <td>
                              <div className="cell-name">{el.name}</div>
                              {el.practice_type && (
                                <div className="cell-name-sub">{PRACTICE_LABELS[el.practice_type] || ""}</div>
                              )}
                              {el.fgos_requirement && (
                                <div className="cell-name-sub" style={{ color: "var(--warning)" }}>ФГОС</div>
                              )}
                            </td>
                            <td>
                              <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
                                {el.semesters?.length
                                  ? el.semesters.map((s) => <span key={s} className="sem-chip">С{s}</span>)
                                  : <span className="text-muted">—</span>
                                }
                              </div>
                            </td>
                            <td className="cell-num">{el.credits}</td>
                            <td className="cell-num">{el.hours}</td>
                            <td className="cell-num">{el.extra_hours || 0}</td>
                            <td>
                              <div className="comp-chips">
                                {el.competency_ids
                                  ?.filter((id) => competencyMap[id])
                                  .map((id) => (
                                    <span key={id} className="comp-chip" title={competencyMap[id].name}>
                                      {competencyMap[id].code}
                                    </span>
                                  ))
                                }
                              </div>
                            </td>
                            <td>
                              <div className="row-actions">
                                <button className="btn-icon" type="button" title="Редактировать" onClick={() => onEdit(el.id)}>✏</button>
                                <button className="btn-icon danger" type="button" title="Удалить" onClick={() => onDelete(el)} disabled={saving}>✕</button>
                              </div>
                            </td>
                          </tr>
                        )
                      )}
                      <tr className="block-total-row">
                        <td>Итого</td>
                        <td></td>
                        <td className="cell-num">{elements.reduce((s, e) => s + e.credits, 0).toFixed(1)}</td>
                        <td className="cell-num">{elements.reduce((s, e) => s + (e.hours || 0), 0)}</td>
                        <td className="cell-num">{elements.reduce((s, e) => s + (e.extra_hours || 0), 0)}</td>
                        <td colSpan={2}></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}

          {/* Add element in-block form */}
          {showAddForm ? (
            <div className="add-elem-form">
              <ElementForm
                value={addDraft}
                onChange={onAddChange}
                competencies={competencies}
                saving={saving}
                onSave={onAdd}
                onCancel={() => onShowAdd(false)}
                isNew
              />
            </div>
          ) : (
            <button className="add-elem-btn" type="button" onClick={() => onShowAdd(true)}>
              + Добавить дисциплину в блок
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/* --------------------------------------------------------- Table2 -- */
export default function Table2({ plan, planId, onNotice, onRefresh, onNext }) {
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [drafts, setDrafts]     = useState({});
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving]     = useState(false);
  const [competencies, setCompetencies] = useState({});
  const [addBlock, setAddBlock] = useState(null);  // block key where add form is open
  const [addDraft, setAddDraft] = useState(EMPTY_FORM);

  useEffect(() => {
    if (!planId) { setData(null); return; }
    let cancelled = false;
    setLoading(true); setError("");
    getTable2(planId)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        const nextDrafts = {};
        collectAll(d.grouped_elements).forEach((el) => { nextDrafts[el.id] = toDraft(el); });
        setDrafts(nextDrafts);
      })
      .catch((e) => { if (!cancelled) setError(getErrorMessage(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [planId]);

  useEffect(() => {
    let cancelled = false;
    listCompetencies()
      .then((d) => { if (!cancelled) setCompetencies(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const competencyMap = useMemo(() => buildCompMap(competencies), [competencies]);

  const reload = (msg) => {
    if (msg) onNotice?.(msg, "success");
    onRefresh?.();
  };

  const handleSave = async (id) => {
    setSaving(true);
    try {
      await updateTable2Element(planId, id, normalizePayload(drafts[id]));
      setEditingId(null);
      reload("Изменения сохранены");
    } catch (e) { onNotice?.(getErrorMessage(e), "error"); }
    finally { setSaving(false); }
  };

  const handleDelete = async (el) => {
    const extra = el.fgos_requirement ? " Это нормативно значимый элемент ФГОС." : "";
    if (!window.confirm(`Удалить «${el.name}»?${extra}`)) return;
    setSaving(true);
    try {
      await deleteTable2Element(planId, el.id);
      reload("Элемент удалён");
    } catch (e) { onNotice?.(getErrorMessage(e), "error"); }
    finally { setSaving(false); }
  };

  const handleAdd = async () => {
    setSaving(true);
    try {
      const payload = { ...normalizePayload(addDraft), source_element_id: null };
      if (addBlock && addDraft.block === EMPTY_FORM.block) payload.block = addBlock;
      await createTable2Element(planId, payload);
      setAddBlock(null);
      setAddDraft(EMPTY_FORM);
      reload("Элемент добавлен");
    } catch (e) { onNotice?.(getErrorMessage(e), "error"); }
    finally { setSaving(false); }
  };

  if (!plan) return null;
  if (loading) return <EmptyState icon="⏳" title="Загрузка…" description="Получаем структуру учебного плана" />;
  if (error)   return <div className="notice notice-error"><span className="notice-icon">✗</span>{error}</div>;

  const agg = data?.aggregates;
  const allElements = data ? collectAll(data.grouped_elements) : [];

  return (
    <div className="page-panel">
      <div className="section-header">
        <div>
          <div className="section-header__title">Учебный план</div>
          <div className="section-header__sub">Структура дисциплин, практик и нагрузка по блокам</div>
        </div>
        <div className="section-header__spacer" />
        <button className="btn btn-secondary btn-sm" onClick={onNext}>
          Перейти к проверке →
        </button>
      </div>

      {/* Summary stat cards */}
      {agg && (
        <div className="stat-cards" style={{ marginBottom: "var(--s-5)" }}>
          <div className="stat-card accent">
            <div className="stat-card__label">З.е. (без фак.)</div>
            <div className="stat-card__value">{agg.total_credits}</div>
            <div className="stat-card__sub">из 240 по норме</div>
          </div>
          <div className="stat-card">
            <div className="stat-card__label">Часы по з.е.</div>
            <div className="stat-card__value">{agg.total_base_hours}</div>
          </div>
          <div className="stat-card">
            <div className="stat-card__label">Доп. часы</div>
            <div className="stat-card__value">{agg.total_extra_hours}</div>
          </div>
          <div className="stat-card">
            <div className="stat-card__label">Всего часов</div>
            <div className="stat-card__value">{agg.total_hours}</div>
          </div>
          <div className={`stat-card ${(agg.mandatory_percent * 100) >= 40 ? "ok" : "warn"}`}>
            <div className="stat-card__label">Обяз. часть</div>
            <div className="stat-card__value">{(agg.mandatory_percent * 100).toFixed(1)}%</div>
            <div className="stat-card__sub">норма ≥ 40%</div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && data && allElements.length === 0 && (
        <EmptyState
          icon="📭"
          title="Учебный план пуст"
          description="Перенесите элементы из рекомендаций ФГОС или добавьте вручную через кнопку в каждом блоке."
        />
      )}

      {/* Block sections */}
      {data && Object.entries(data.grouped_elements).map(([block, parts]) => (
        <BlockSection
          key={block}
          block={block}
          parts={parts}
          competencies={competencies}
          competencyMap={competencyMap}
          editingId={editingId}
          drafts={drafts}
          saving={saving}
          onEdit={(id) => { setEditingId(id); setAddBlock(null); }}
          onDelete={handleDelete}
          onDraftChange={(id, f, v) => setDrafts((s) => ({ ...s, [id]: { ...s[id], [f]: v } }))}
          onSave={handleSave}
          onCancelEdit={() => setEditingId(null)}
          showAddForm={addBlock === block}
          onShowAdd={(show) => {
            setEditingId(null);
            setAddBlock(show ? block : null);
            setAddDraft({ ...EMPTY_FORM, block });
          }}
          addDraft={addDraft}
          onAddChange={(f, v) => setAddDraft((s) => ({ ...s, [f]: v }))}
          onAdd={handleAdd}
        />
      ))}
    </div>
  );
}
