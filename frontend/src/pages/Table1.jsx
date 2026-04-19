import { useEffect, useMemo, useState } from "react";

import { getErrorMessage, getTable1, transferTable1 } from "../api";
import EmptyState from "../components/EmptyState";
import HelpTooltip from "../components/HelpTooltip";
import SourceBadge from "../components/SourceBadge";
import StatusBadge from "../components/StatusBadge";

function formatSemesters(semesters) {
  if (!semesters?.length) {
    return "Семестры не указаны";
  }
  return `Семестры ${semesters.join(", ")}`;
}

function RecommendationCard({
  item,
  checked,
  inputType = "checkbox",
  name,
  onChange,
}) {
  return (
    <label className={`recommendation ${inputType === "checkbox" ? "checkbox" : "radio"}`}>
      <input
        type={inputType}
        name={name}
        checked={checked}
        onChange={(event) => onChange(item.id, event.target.checked)}
      />
      <div>
        <strong>{item.name}</strong>
        <span>
          {item.credits ?? 0} з.е. · {formatSemesters(item.semesters)}
          {item.extra_hours ? ` · доп. часы: ${item.extra_hours}` : ""}
        </span>
        <div className="recommendation-meta">
          <SourceBadge source={item.source_title || item.source_label || item.source} />
          {item.source_label && item.source_title && item.source_label !== item.source_title ? (
            <small>{item.source_label}</small>
          ) : null}
          {item.practice_type ? (
            <small>{item.practice_type === "educational" ? "Учебная практика" : "Производственная практика"}</small>
          ) : null}
        </div>
        {item.competency_codes?.length ? <small>{item.competency_codes.join(", ")}</small> : null}
      </div>
    </label>
  );
}

function GroupSelection({ title, groups, selections, onSingleSelect, onToggle, helperText }) {
  return (
    <div className="content-block">
      <div className="inline-hint">
        <h4>{title}</h4>
        <HelpTooltip text={helperText} />
      </div>
      {!groups.length ? <p className="status-muted">Нет доступных вариантов.</p> : null}
      {groups.map((group) => (
        <div key={group.requirement} className="fgos-group">
          <div className="section-header">
            <div>
              <strong>{group.title}</strong>
              <p className="status-muted">
                {group.is_complete ? "Выбор выполнен" : "Выбор пока не выполнен"}
              </p>
            </div>
            <StatusBadge value={group.is_complete ? "checked" : "warning"} />
          </div>
          {!group.items.length ? (
            <p className="status-muted">
              Варианты не найдены. Элемент можно будет добавить вручную в Таблице 2.
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
        <div className="inline-hint">
          <strong>Для этой компетенции действует ручной режим.</strong>
          <HelpTooltip text="Для ПКС автоматические рекомендации не формируются. Связь дисциплин и практик с ПКС задаётся вручную в Таблице 2." />
        </div>
        <p>Автоматический подбор не применяется. Добавьте элементы и свяжите их с компетенцией вручную в Таблице 2.</p>
      </div>
    );
  }

  const groups = [
    {
      title: "Дисциплины обязательной части",
      items: section.mandatory_disciplines,
      emptyText: "Рекомендации не найдены.",
    },
    {
      title: "Дисциплины вариативной части",
      items: section.variative_disciplines,
      emptyText: "Рекомендации не найдены.",
    },
    {
      title: "Практики обязательной части",
      items: section.mandatory_practices,
      emptyText: "Рекомендации не найдены.",
    },
  ];

  return (
    <div className="three-columns">
      {groups.map((group) => (
        <div key={group.title} className="content-block">
          <h4>{group.title}</h4>
          {!group.items.length ? <p className="status-muted">{group.emptyText}</p> : null}
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
        if (cancelled) {
          return;
        }

        setData(nextData);
        const nextSelections = {};
        const collect = (items) => {
          items.forEach((item) => {
            nextSelections[item.id] = item.selected;
          });
        };

        nextData.fgos_disciplines.forEach((group) => collect(group.items));
        nextData.fgos_practices.forEach((group) => collect(group.items));
        nextData.competencies.forEach((section) => {
          collect(section.mandatory_disciplines);
          collect(section.variative_disciplines);
          collect(section.mandatory_practices);
        });
        setSelections(nextSelections);
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, "Не удалось загрузить рекомендации."));
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

  const selectedCount = useMemo(
    () => Object.values(selections).filter(Boolean).length,
    [selections],
  );

  const manualSectionCount = useMemo(
    () => data?.competencies?.filter((section) => section.mode === "manual_only").length || 0,
    [data],
  );

  const handleToggle = (elementId, checked) => {
    setSelections((current) => ({ ...current, [elementId]: checked }));
  };

  const handleSingleSelect = (group, itemId, checked) => {
    setSelections((current) => {
      const next = { ...current };
      group.items.forEach((item) => {
        next[item.id] = false;
      });
      if (checked) {
        next[itemId] = true;
      }
      return next;
    });
  };

  const handleTransfer = async () => {
    if (!planId) {
      return;
    }

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
      <section className="card">
        <h2>Таблица 1</h2>
        <p>Сначала выберите учебный план на стартовом экране.</p>
      </section>
    );
  }

  return (
    <section className="stack-panel">
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Таблица 1</p>
            <h2>Рекомендации и обязательные элементы ФГОС</h2>
            <p className="status-muted">Направление: {plan.program_code}</p>
          </div>
          <button className="primary-button" type="button" onClick={handleTransfer} disabled={transferring}>
            {transferring ? "Перенос..." : "Перенести выбранное в Таблицу 2"}
          </button>
        </div>
        <p className="status-muted">
          Таблица 1 не участвует в расчётах. Здесь выбираются конкретные дисциплины и практики, которые будут перенесены в рабочую структуру учебного плана.
        </p>
        {loading ? <p className="status-muted">Загрузка рекомендаций...</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

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
            <span>Полнота выбора ФГОС</span>
            <strong>
              {data.selection_summary.required_disciplines_complete && data.selection_summary.required_practices_complete
                ? "Полная"
                : "Есть пропуски"}
            </strong>
          </div>
        </div>
      ) : null}

      {data ? (
        <div className="card">
          <div className="section-header">
            <div>
              <p className="card-kicker">ФГОС</p>
              <h3>Статус обязательных элементов</h3>
            </div>
          </div>
          <div className="inline-hint">
            <span>
              {data.selection_summary.required_disciplines_complete
                ? "Все обязательные дисциплины ФГОС выбраны."
                : `Не выбраны дисциплины: ${data.selection_summary.missing_discipline_requirements.join(", ") || "нет данных"}.`}
            </span>
          </div>
          <div className="inline-hint">
            <span>
              {data.selection_summary.required_practices_complete
                ? "Обязательные категории практик выбраны."
                : `Не выбраны практики: ${data.selection_summary.missing_practice_requirements.join(", ") || "нет данных"}.`}
            </span>
          </div>
        </div>
      ) : null}

      {data ? (
        <div className="card">
          <div className="section-header">
            <div>
              <p className="card-kicker">ФГОС</p>
              <h3>Нормативно обязательные элементы</h3>
            </div>
          </div>
          <div className="two-columns">
            <GroupSelection
              title="Обязательные дисциплины (ФГОС)"
              groups={data.fgos_disciplines}
              selections={selections}
              onSingleSelect={handleSingleSelect}
              onToggle={handleToggle}
              helperText="Для каждой нормативной дисциплины выберите один вариант реализации или оставьте выбор пустым и добавьте элемент вручную в Таблице 2."
            />
            <GroupSelection
              title="Обязательные категории практик (ФГОС)"
              groups={data.fgos_practices}
              selections={selections}
              onSingleSelect={handleSingleSelect}
              onToggle={handleToggle}
              helperText="Для каждой обязательной категории практик можно выбрать один или несколько вариантов."
            />
          </div>
        </div>
      ) : null}

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
              <h3>
                {section.competency.code} — {section.competency.name}
              </h3>
            </div>
            {section.mode === "manual_only" ? <StatusBadge value="manual" /> : null}
          </div>
          <p className="status-muted">{section.competency.description}</p>
          <CompetencySection section={section} selections={selections} onToggle={handleToggle} />
        </article>
      ))}
    </section>
  );
}
