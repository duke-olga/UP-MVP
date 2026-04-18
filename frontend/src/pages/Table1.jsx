import { useEffect, useMemo, useState } from "react";

import { getErrorMessage, getTable1, transferTable1 } from "../api";
import EmptyState from "../components/EmptyState";
import HelpTooltip from "../components/HelpTooltip";
import SourceBadge from "../components/SourceBadge";
import StatusBadge from "../components/StatusBadge";

function RecommendationList({ items, selectable = false, selections, onToggle, emptyText }) {
  if (!items.length) {
    return <p className="status-muted">{emptyText}</p>;
  }

  return (
    <div className="recommendation-list">
      {items.map((item) => (
        <label key={item.id} className={selectable ? "recommendation checkbox" : "recommendation"}>
          {selectable ? (
            <input
              type="checkbox"
              checked={Boolean(selections[item.id])}
              onChange={(event) => onToggle(item.id, event.target.checked)}
            />
          ) : null}
          <div>
            <strong>{item.name}</strong>
            <span>
              {item.credits ?? 0} з.е. · семестр {item.semester ?? "не указан"}
            </span>
            <div className="recommendation-meta">
              <SourceBadge source={item.source_label || item.source} />
            </div>
            {item.competency_codes?.length ? <small>{item.competency_codes.join(", ")}</small> : null}
          </div>
        </label>
      ))}
    </div>
  );
}

export default function Table1({ plan, planId, refreshToken, onNavigate, onRefresh, setGlobalNotice }) {
  const [sections, setSections] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selections, setSelections] = useState({});
  const [transferring, setTransferring] = useState(false);

  useEffect(() => {
    if (!planId) {
      setSections([]);
      setSelections({});
      return;
    }

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const data = await getTable1(planId);
        if (cancelled) {
          return;
        }
        setSections(data);
        const nextSelections = {};
        data.forEach((section) => {
          section.variative_disciplines.forEach((item) => {
            nextSelections[item.id] = item.selected;
          });
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

  const selectedVariativeCount = useMemo(
    () => Object.values(selections).filter(Boolean).length,
    [selections],
  );

  const recommendationSectionCount = useMemo(
    () => sections.filter((section) => section.mode === "recommendation").length,
    [sections],
  );

  const manualSectionCount = useMemo(
    () => sections.filter((section) => section.mode === "manual_only").length,
    [sections],
  );

  const handleToggle = (elementId, checked) => {
    setSelections((current) => ({ ...current, [elementId]: checked }));
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
      setGlobalNotice(getErrorMessage(transferError, "Не удалось перенести элементы в структуру плана."));
    } finally {
      setTransferring(false);
    }
  };

  if (!plan) {
    return (
      <section className="card">
        <h2>Рекомендации</h2>
        <p>Сначала выберите учебный план на стартовом экране.</p>
      </section>
    );
  }

  return (
    <section className="stack-panel">
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Рекомендации</p>
            <h2>Рекомендации по компетенциям</h2>
          </div>
          <button className="primary-button" type="button" onClick={handleTransfer} disabled={transferring}>
            {transferring ? "Перенос..." : "Перенести в структуру плана"}
          </button>
        </div>
        <p className="status-muted">
          Здесь показаны рекомендуемые элементы для формирования учебного плана. Этот экран не
          является самой структурой плана: обязательные элементы переносятся автоматически, а
          вариативные дисциплины включаются только по отмеченным позициям.
        </p>
        {loading ? <p className="status-muted">Загрузка рекомендаций...</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

      <div className="card totals-grid">
        <div className="metric-tile">
          <span>Компетенций</span>
          <strong>{sections.length}</strong>
        </div>
        <div className="metric-tile">
          <span>Компетенции с рекомендациями</span>
          <strong>{recommendationSectionCount}</strong>
        </div>
        <div className="metric-tile">
          <span>Ручной режим</span>
          <strong>{manualSectionCount}</strong>
        </div>
        <div className="metric-tile">
          <span>Выбрано вариативных дисциплин</span>
          <strong>{selectedVariativeCount}</strong>
        </div>
      </div>

      {!loading && !error && sections.length === 0 ? (
        <EmptyState
          title="Рекомендации пока не найдены"
          description="Для выбранного плана система пока не подготовила рекомендации по компетенциям."
        />
      ) : null}

      {sections.map((section) => (
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

          {section.mode === "manual_only" ? (
            <div className="manual-note">
              <div className="inline-hint">
                <strong>Для этой компетенции действует ручной режим.</strong>
                <HelpTooltip text="Для ПКС автоматический подбор не применяется. Добавьте дисциплины и практики вручную в разделе «Структура плана»." />
              </div>
              <p>
                Автоматический подбор не применяется. Добавьте дисциплины и практики вручную в
                разделе «Структура плана».
              </p>
            </div>
          ) : (
            <div className="three-columns">
              <div className="content-block">
                <div className="inline-hint">
                  <h4>Обязательные дисциплины</h4>
                  <HelpTooltip text="Эти элементы переносятся в структуру плана автоматически." />
                </div>
                <RecommendationList
                  items={section.mandatory_disciplines}
                  selections={selections}
                  emptyText="Обязательные дисциплины не заданы."
                />
              </div>
              <div className="content-block">
                <div className="inline-hint">
                  <h4>Рекомендуемые дисциплины</h4>
                  <HelpTooltip text="Отметьте только те вариативные дисциплины, которые нужно включить в структуру плана." />
                </div>
                <RecommendationList
                  items={section.variative_disciplines}
                  selectable
                  selections={selections}
                  onToggle={handleToggle}
                  emptyText="Рекомендуемые вариативные дисциплины не найдены."
                />
              </div>
              <div className="content-block">
                <div className="inline-hint">
                  <h4>Обязательные практики</h4>
                  <HelpTooltip text="Вариативные практики в MVP не предлагаются автоматически и добавляются вручную в структуру плана." />
                </div>
                <RecommendationList
                  items={section.mandatory_practices}
                  selections={selections}
                  emptyText="Обязательные практики не заданы."
                />
              </div>
            </div>
          )}
        </article>
      ))}
    </section>
  );
}
