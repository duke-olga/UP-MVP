import { useEffect, useState } from "react";

import { getErrorMessage, getTable1, transferTable1 } from "../api";

function RecommendationList({ items, type = "static", selections, onToggle }) {
  if (!items.length) {
    return <p className="status-muted">Нет элементов.</p>;
  }

  return (
    <div className="recommendation-list">
      {items.map((item) => (
        <label key={item.id} className={type === "checkbox" ? "recommendation checkbox" : "recommendation"}>
          {type === "checkbox" ? (
            <input
              type="checkbox"
              checked={Boolean(selections[item.id])}
              onChange={(event) => onToggle(item.id, event.target.checked)}
            />
          ) : null}
          <div>
            <strong>{item.name}</strong>
            <span>
              {item.credits ?? 0} з.е. · семестр {item.semester ?? "не указан"} · {item.source}
            </span>
            {item.competency_codes?.length ? (
              <small>{item.competency_codes.join(", ")}</small>
            ) : null}
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
          setError(getErrorMessage(loadError, "Не удалось загрузить Таблицу 1."));
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
      setGlobalNotice(
        `Перенос завершён. Создано: ${result.created_count}, обновлено: ${result.updated_count}.`,
      );
      onRefresh();
      onNavigate("table2");
    } catch (transferError) {
      setGlobalNotice(getErrorMessage(transferError, "Не удалось перенести элементы в Таблицу 2."));
    } finally {
      setTransferring(false);
    }
  };

  if (!plan) {
    return (
      <section className="card">
        <h2>Таблица 1</h2>
        <p>Сначала выбери или создай учебный план.</p>
      </section>
    );
  }

  return (
    <section className="stack-panel">
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Таблица 1</p>
            <h2>Витрина рекомендаций</h2>
          </div>
          <button className="primary-button" type="button" onClick={handleTransfer} disabled={transferring}>
            {transferring ? "Перенос..." : "Перенести в Таблицу 2"}
          </button>
        </div>
        <p className="status-muted">
          План: <strong>{plan.name}</strong>. Обязательные элементы переносятся автоматически, вариативные
          дисциплины — по отмеченным чекбоксам.
        </p>
        {loading ? <p className="status-muted">Загрузка рекомендаций...</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

      {sections.map((section) => (
        <article key={section.competency.id} className="card competency-card">
          <div className="section-header">
            <div>
              <p className="card-kicker">{section.competency.type}</p>
              <h3>{section.competency.code}</h3>
            </div>
            <span className={section.mode === "manual" ? "mode-badge manual" : "mode-badge auto"}>
              {section.mode === "manual" ? "Ручной режим" : "Auto"}
            </span>
          </div>
          <p>{section.competency.name}</p>
          <p className="status-muted">{section.competency.description}</p>

          {section.mode === "manual" ? (
            <div className="manual-note">
              Для ПКС автоподбор отключён. Добавляй дисциплины и практики вручную в Таблице 2.
            </div>
          ) : (
            <div className="three-columns">
              <div>
                <h4>Обязательные дисциплины</h4>
                <RecommendationList items={section.mandatory_disciplines} selections={selections} />
              </div>
              <div>
                <h4>Вариативные дисциплины</h4>
                <RecommendationList
                  items={section.variative_disciplines}
                  type="checkbox"
                  selections={selections}
                  onToggle={handleToggle}
                />
              </div>
              <div>
                <h4>Обязательные практики</h4>
                <RecommendationList items={section.mandatory_practices} selections={selections} />
              </div>
            </div>
          )}
        </article>
      ))}
    </section>
  );
}
