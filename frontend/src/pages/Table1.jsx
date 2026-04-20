import { useEffect, useMemo, useState } from "react";

import { getErrorMessage, getTable1, transferTable1 } from "../api";
import EmptyState from "../components/EmptyState";
import HelpTooltip from "../components/HelpTooltip";
import SourceBadge from "../components/SourceBadge";
import StatusBadge from "../components/StatusBadge";

function formatSemesters(semesters) {
  if (!semesters?.length) return "Семестры не указаны";
  return `Сем. ${semesters.join(", ")}`;
}

function RecommendationCard({ item, checked, inputType = "checkbox", name, onChange }) {
  return (
    <label className={`recommendation ${inputType === "checkbox" ? "checkbox" : "radio"}`}>
      <input
        type={inputType}
        name={name}
        checked={checked}
        onChange={(e) => onChange(item.id, e.target.checked)}
      />
      <div>
        <strong>{item.name}</strong>
        <span>
          {item.credits ?? 0} з.е. · {formatSemesters(item.semesters)}
          {item.extra_hours ? ` · доп. ${item.extra_hours} ч.` : ""}
        </span>
        <div className="recommendation-meta">
          <SourceBadge source={item.source_title || item.source_label || item.source} />
          {item.source_label && item.source_title && item.source_label !== item.source_title ? (
            <small>{item.source_label}</small>
          ) : null}
          {item.practice_type ? (
            <small>
              {item.practice_type === "educational" ? "Учебная практика" : "Производственная практика"}
            </small>
          ) : null}
        </div>
        {item.competency_codes?.length ? (
          <small style={{ color: "var(--accent)" }}>{item.competency_codes.join(", ")}</small>
        ) : null}
      </div>
    </label>
  );
}

function GroupSelection({ title, groups, selections, onSingleSelect, onToggle, helperText }) {
  return (
    <div className="content-block">
      <div className="inline-hint" style={{ marginBottom: "2px" }}>
        <h4 style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-2)", margin: 0 }}>{title}</h4>
        <HelpTooltip text={helperText} />
      </div>
      {!groups.length ? <p className="status-muted">Нет доступных вариантов.</p> : null}
      {groups.map((group) => (
        <div key={group.requirement} className="fgos-group">
          <div className="section-header" style={{ marginBottom: "8px" }}>
            <div>
              <strong style={{ fontSize: "13px", color: "var(--text)" }}>{group.title}</strong>
              <p className="status-muted" style={{ marginTop: "1px" }}>
                {group.is_complete ? "Выбор выполнен" : "Выбор не выполнен"}
              </p>
            </div>
            <StatusBadge value={group.is_complete ? "approved" : "warning"}>
              {group.is_complete ? "Готово" : "Ожидает"}
            </StatusBadge>
          </div>
          {!group.items.length ? (
            <p className="status-muted">
              Варианты не найдены — добавьте элемент вручную в Таблице 2.
            </p>
          ) : (
            <div className="recommendation-list">
              {group.items.map((item) => (
                <RecommendationCard
                  key={item.id}
                  item={item}
                  checked={Boolean(selections[item.id])}
                  inputType={group.selection_mode === "single" ? "radio" : "checkbox"}
                  name={group.requirement}
                  onChange={(itemId, nextChecked) => {
                    if (group.selection_mode === "single") {
                      onSingleSelect(group, itemId, nextChecked);
                    } else {
                      onToggle(itemId, nextChecked);
                    }
                  }}
                />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function CompetencySection({ section, selections, onToggle }) {
  if (section.mode === "manual_only") {
    return (
      <div className="manual-note">
        <div className="inline-hint" style={{ marginBottom: "4px" }}>
          <strong>Ручной режим — ПКС</strong>
          <HelpTooltip text="Для ПКС автоматические рекомендации не формируются. Связь дисциплин и практик с ПКС задаётся вручную в Таблице 2." />
        </div>
        <p>Добавьте элементы и свяжите их с компетенцией в Таблице 2.</p>
      </div>
    );
  }

  const groups = [
    { title: "Дисциплины обязательной части", items: section.mandatory_disciplines },
    { title: "Дисциплины вариативной части", items: section.variative_disciplines },
    { title: "Практики обязательной части", items: section.mandatory_practices },
  ];

  return (
    <div className="three-columns">
      {groups.map((group) => (
        <div key={group.title} className="content-block">
          <h4>{group.title}</h4>
          {!group.items.length ? (
            <p className="status-muted" style={{ fontSize: "12px" }}>Рекомендации не найдены.</p>
          ) : null}
          <div className="recommendation-list">
            {group.items.map((item) => (
              <RecommendationCard
                key={item.id}
                item={item}
                checked={Boolean(selections[item.id])}
                onChange={onToggle}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Table1({ plan, planId, refreshToken, onNavigate, onRefresh, setGlobalNotice }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selections, setSelections] = useState({});
  const [transferring, setTransferring] = useState(false);

  useEffect(() => {
    if (!planId) {
      setData(null);
      setSelections({});
      return;
    }

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const nextData = await getTable1(planId);
        if (cancelled) return;

        setData(nextData);
        const nextSelections = {};
        const collect = (items) => items.forEach((item) => { nextSelections[item.id] = item.selected; });

        nextData.fgos_disciplines.forEach((group) => collect(group.items));
        nextData.fgos_practices.forEach((group) => collect(group.items));
        nextData.competencies.forEach((section) => {
          collect(section.mandatory_disciplines);
          collect(section.variative_disciplines);
          collect(section.mandatory_practices);
        });
        setSelections(nextSelections);
      } catch (loadError) {
        if (!cancelled) setError(getErrorMessage(loadError, "Не удалось загрузить рекомендации."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [planId, refreshToken]);

  const selectedCount = useMemo(
    () => Object.values(selections).filter(Boolean).length,
    [selections],
  );

  const manualSectionCount = useMemo(
    () => data?.competencies?.filter((s) => s.mode === "manual_only").length || 0,
    [data],
  );

  const handleToggle = (elementId, checked) => {
    setSelections((cur) => ({ ...cur, [elementId]: checked }));
  };

  const handleSingleSelect = (group, itemId, checked) => {
    setSelections((cur) => {
      const next = { ...cur };
      group.items.forEach((item) => { next[item.id] = false; });
      if (checked) next[itemId] = true;
      return next;
    });
  };

  const handleTransfer = async () => {
    if (!planId) return;

    setTransferring(true);
    try {
      const payload = Object.entries(selections).map(([elementId, selected]) => ({
        element_id: Number(elementId),
        selected,
      }));
      const result = await transferTable1(planId, payload);
      setGlobalNotice(`Перенос завершён. Добавлено: ${result.created_count}, обновлено: ${result.updated_count}.`);
      onRefresh();
      onNavigate("table2");
    } catch (transferError) {
      setGlobalNotice(getErrorMessage(transferError, "Не удалось перенести выбранные элементы в Таблицу 2."));
    } finally {
      setTransferring(false);
    }
  };

  if (!plan) {
    return (
      <div className="card">
        <p>Сначала выберите учебный план.</p>
      </div>
    );
  }

  const fgosComplete =
    data?.selection_summary?.required_disciplines_complete &&
    data?.selection_summary?.required_practices_complete;

  return (
    <section className="stack-panel">
      {/* Header card */}
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Шаг 1</p>
            <h2 style={{ fontSize: "18px" }}>Рекомендации и обязательные элементы ФГОС</h2>
            <p className="status-muted" style={{ marginTop: "4px" }}>
              Направление {plan.program_code} · Выбор здесь не влияет на расчёты — только определяет,
              что перенести в структуру плана.
            </p>
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={handleTransfer}
            disabled={transferring || !data}
          >
            {transferring ? "Перенос…" : "Перенести выбранное →"}
          </button>
        </div>
        {loading ? <p className="status-muted">Загрузка рекомендаций…</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

      {/* Metrics */}
      {data ? (
        <div className="card totals-grid">
          <div className="metric-tile">
            <span>Выбрано элементов</span>
            <strong>{selectedCount}</strong>
          </div>
          <div className="metric-tile">
            <span>Компетенций</span>
            <strong>{data.competencies.length}</strong>
          </div>
          <div className="metric-tile">
            <span>ПКС в ручном режиме</span>
            <strong>{manualSectionCount}</strong>
          </div>
          <div className="metric-tile">
            <span>Полнота ФГОС</span>
            <strong style={{ fontSize: "15px", color: fgosComplete ? "var(--green)" : "var(--amber)" }}>
              {fgosComplete ? "Полная" : "Есть пропуски"}
            </strong>
          </div>
        </div>
      ) : null}

      {/* FGOS completeness status */}
      {data ? (
        <div className="card">
          <div className="section-header">
            <div>
              <p className="card-kicker">Статус ФГОС</p>
              <h3 style={{ fontSize: "15px" }}>Обязательные элементы</h3>
            </div>
            <StatusBadge value={fgosComplete ? "approved" : "warning"}>
              {fgosComplete ? "Всё выбрано" : "Есть пропуски"}
            </StatusBadge>
          </div>
          <div style={{ display: "grid", gap: "6px" }}>
            <div className="inline-hint">
              <span style={{ color: data.selection_summary.required_disciplines_complete ? "var(--green-text)" : "var(--amber-text)" }}>
                {data.selection_summary.required_disciplines_complete
                  ? "✓ Все обязательные дисциплины ФГОС выбраны."
                  : `⚠ Не выбраны дисциплины: ${data.selection_summary.missing_discipline_requirements.join(", ") || "нет данных"}.`}
              </span>
            </div>
            <div className="inline-hint">
              <span style={{ color: data.selection_summary.required_practices_complete ? "var(--green-text)" : "var(--amber-text)" }}>
                {data.selection_summary.required_practices_complete
                  ? "✓ Обязательные категории практик выбраны."
                  : `⚠ Не выбраны практики: ${data.selection_summary.missing_practice_requirements.join(", ") || "нет данных"}.`}
              </span>
            </div>
          </div>
        </div>
      ) : null}

      {/* FGOS mandatory elements */}
      {data ? (
        <div className="card">
          <div className="section-header">
            <div>
              <p className="card-kicker">ФГОС</p>
              <h3 style={{ fontSize: "15px" }}>Нормативно обязательные элементы</h3>
            </div>
          </div>
          <div className="two-columns">
            <GroupSelection
              title="Обязательные дисциплины"
              groups={data.fgos_disciplines}
              selections={selections}
              onSingleSelect={handleSingleSelect}
              onToggle={handleToggle}
              helperText="Для каждой нормативной дисциплины выберите один вариант реализации или оставьте пустым и добавьте вручную в Таблице 2."
            />
            <GroupSelection
              title="Обязательные категории практик"
              groups={data.fgos_practices}
              selections={selections}
              onSingleSelect={handleSingleSelect}
              onToggle={handleToggle}
              helperText="Для каждой категории практик можно выбрать один или несколько вариантов."
            />
          </div>
        </div>
      ) : null}

      {/* Competency sections */}
      {!loading && !error && data && data.competencies.length === 0 ? (
        <EmptyState
          title="Компетенции не найдены"
          description="Для выбранного плана в системе пока нет доступных компетенций."
        />
      ) : null}

      {data?.competencies.map((section) => (
        <article key={section.competency.id} className="card competency-card">
          <div className="section-header">
            <div>
              <p className="card-kicker">{section.competency.type}</p>
              <h3 style={{ fontSize: "15px" }}>
                {section.competency.code} — {section.competency.name}
              </h3>
              <p className="status-muted" style={{ marginTop: "3px" }}>
                {section.competency.description}
              </p>
            </div>
            {section.mode === "manual_only" ? (
              <StatusBadge value="manual">Ручной режим</StatusBadge>
            ) : null}
          </div>
          <CompetencySection section={section} selections={selections} onToggle={handleToggle} />
        </article>
      ))}
    </section>
  );
}
