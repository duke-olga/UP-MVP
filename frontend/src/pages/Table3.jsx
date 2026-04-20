import { useEffect, useState } from "react";

import { getErrorMessage, getExportUrl, getTable3, updatePlanStatus, validatePlan } from "../api";
import EmptyState from "../components/EmptyState";
import HelpTooltip from "../components/HelpTooltip";
import StatusBadge from "../components/StatusBadge";

const levelLabels = {
  critical: "Критическое нарушение",
  error: "Ошибка",
  warning: "Предупреждение",
};

const summaryMap = {
  ok: {
    tone: "approved",
    title: "Нарушений не обнаружено",
    description: "Все проверки пройдены. Блокирующих нарушений и ошибок нет — план можно утверждать.",
  },
  critical: {
    tone: "critical",
    title: "Критические нарушения",
    description: "Утверждение невозможно. Устраните критические нарушения и повторите проверку.",
  },
  error: {
    tone: "error",
    title: "Обнаружены ошибки",
    description: "Утверждение заблокировано. Исправьте ошибки и запустите проверку повторно.",
  },
  warning: {
    tone: "warning",
    title: "Есть предупреждения",
    description: "Предупреждения не блокируют утверждение, но требуют внимания методиста.",
  },
};

function DeviationRow({ label, item }) {
  const deltaClass =
    item.delta > 0 ? "delta positive" : item.delta < 0 ? "delta negative" : "delta";

  return (
    <div className="deviation-row">
      <span style={{ color: "var(--text-2)" }}>{label}</span>
      <strong style={{ color: "var(--text)" }}>{item.actual}</strong>
      <span style={{ color: "var(--text-3)" }}>{item.expected}</span>
      <span className={deltaClass}>{item.delta >= 0 ? "+" : ""}{item.delta}</span>
    </div>
  );
}

export default function Table3({ plan, planId, refreshToken, onRefresh, setGlobalNotice }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState("");

  useEffect(() => {
    if (!planId) { setData(null); return; }

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const table3 = await getTable3(planId);
        if (!cancelled) setData(table3);
      } catch (loadError) {
        if (!cancelled) setError(getErrorMessage(loadError, "Не удалось загрузить данные проверки."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [planId, refreshToken]);

  const handleValidate = async () => {
    setBusyAction("validate");
    try {
      await validatePlan(planId);
      onRefresh("Проверка выполнена.");
    } catch (validateError) {
      setGlobalNotice(getErrorMessage(validateError, "Не удалось выполнить проверку."));
    } finally {
      setBusyAction("");
    }
  };

  const handleApprove = async () => {
    setBusyAction("approve");
    try {
      await updatePlanStatus(planId, "approved");
      onRefresh("План утверждён.");
    } catch (approveError) {
      setGlobalNotice(getErrorMessage(approveError, "Не удалось утвердить план."));
    } finally {
      setBusyAction("");
    }
  };

  const handleExport = () => {
    window.open(getExportUrl(planId), "_blank", "noopener,noreferrer");
  };

  if (!plan) {
    return <div className="card"><p>Сначала выберите учебный план.</p></div>;
  }

  const validationSummary = data?.validation_summary || {
    status: "ok",
    critical_count: 0,
    error_count: 0,
    warning_count: 0,
  };
  const summary = summaryMap[validationSummary.status] || summaryMap.ok;
  const issues = data?.latest_report?.results || [];
  const canApprove = validationSummary.status === "ok" || validationSummary.status === "warning";

  return (
    <section className="stack-panel">
      {/* Header + actions */}
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Шаг 3</p>
            <h2 style={{ fontSize: "18px" }}>Проверка нормативов и утверждение плана</h2>
            <p className="status-muted" style={{ marginTop: "4px" }}>
              Сначала выполняются детерминированные проверки, затем формируются рекомендации ИИ.
            </p>
          </div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
            <button
              className="primary-button"
              type="button"
              onClick={handleValidate}
              disabled={busyAction !== ""}
            >
              {busyAction === "validate" ? "Проверка…" : "Проверить план"}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={handleApprove}
              disabled={busyAction !== "" || !canApprove || !data}
              title={!canApprove ? "Устраните критические нарушения и ошибки" : undefined}
            >
              {busyAction === "approve" ? "Утверждение…" : "Утвердить"}
            </button>
            <button className="secondary-button" type="button" onClick={handleExport}>
              Скачать XLSX
            </button>
            <HelpTooltip text="Утверждение блокируется только критическими нарушениями и ошибками. Предупреждения и рекомендации ИИ носят консультативный характер." />
          </div>
        </div>
        {loading ? <p className="status-muted">Загрузка данных проверки…</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

      {/* Validation summary */}
      <div className={`card summary-card ${summary.tone}`}>
        <div className="section-header">
          <div>
            <p className="card-kicker" style={{ color: "inherit", opacity: 0.6 }}>Итог проверки</p>
            <h3 style={{ fontSize: "16px" }}>{summary.title}</h3>
          </div>
          <StatusBadge value={summary.tone === "approved" ? "approved" : summary.tone}>
            {summary.tone === "approved" && "Успешно"}
            {summary.tone === "critical" && `Критических: ${validationSummary.critical_count}`}
            {summary.tone === "error" && `Ошибок: ${validationSummary.error_count}`}
            {summary.tone === "warning" && `Предупреждений: ${validationSummary.warning_count}`}
          </StatusBadge>
        </div>
        <p style={{ fontSize: "13px", opacity: 0.85 }}>{summary.description}</p>
      </div>

      {/* Aggregates */}
      {data ? (
        <div className="card totals-grid">
          <div className="metric-tile">
            <span>Всего з.е.</span>
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

      {/* Deviations */}
      {data ? (
        <div className="card">
          <div className="section-header">
            <div>
              <p className="card-kicker">Отклонения</p>
              <h3 style={{ fontSize: "15px" }}>Факт · Норматив · Отклонение</h3>
            </div>
          </div>
          <div className="deviation-table">
            <div className="deviation-row deviation-head">
              <span>Показатель</span>
              <span>Факт</span>
              <span>Норматив</span>
              <span>Δ</span>
            </div>
            <DeviationRow label="Общий объём программы" item={data.deviations.total_credits} />
            <DeviationRow label="Обязательная часть" item={data.deviations.mandatory_percent} />
            {Object.entries(data.deviations.by_block).map(([block, item]) => (
              <DeviationRow key={block} label={`Блок ${block}`} item={item} />
            ))}
            {Object.entries(data.deviations.by_year).map(([year, item]) => (
              <DeviationRow key={year} label={`Год ${year}`} item={item} />
            ))}
          </div>
        </div>
      ) : null}

      {/* Issues */}
      {data ? (
        <div className="card">
          <div className="section-header">
            <div>
              <p className="card-kicker">Нарушения</p>
              <h3 style={{ fontSize: "15px" }}>Результаты детерминированной проверки</h3>
            </div>
            {issues.length > 0 ? (
              <div style={{ display: "flex", gap: "6px" }}>
                {validationSummary.critical_count > 0 && (
                  <StatusBadge value="critical">
                    Крит.: {validationSummary.critical_count}
                  </StatusBadge>
                )}
                {validationSummary.error_count > 0 && (
                  <StatusBadge value="error">
                    Ош.: {validationSummary.error_count}
                  </StatusBadge>
                )}
                {validationSummary.warning_count > 0 && (
                  <StatusBadge value="warning">
                    Пред.: {validationSummary.warning_count}
                  </StatusBadge>
                )}
              </div>
            ) : null}
          </div>

          {issues.length > 0 ? (
            <div className="issue-list">
              {issues.map((result) => (
                <div
                  key={`${result.rule_id}-${result.message}`}
                  className={`issue-card ${result.level}`}
                >
                  <div className="issue-head">
                    <span style={{ fontSize: "12px", fontWeight: 600, color: "inherit", opacity: 0.65 }}>
                      Правило #{result.rule_id}
                    </span>
                    <StatusBadge value={result.level}>
                      {levelLabels[result.level] || result.level}
                    </StatusBadge>
                  </div>
                  <p>{result.message}</p>
                  <small>
                    Факт: {String(result.actual ?? "—")} · Норматив: {String(result.expected ?? "—")}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="Проверка ещё не запускалась"
              description="Нажмите «Проверить план», чтобы получить список нарушений и рекомендации ИИ."
            />
          )}
        </div>
      ) : null}

      {/* LLM recommendations */}
      {data ? (
        <div className="card">
          <div className="section-header">
            <div>
              <p className="card-kicker">Рекомендации ИИ</p>
              <h3 style={{ fontSize: "15px" }}>Пояснения и предложения по корректировке</h3>
            </div>
            <HelpTooltip text="LLM получает только структурированный отчёт о нарушениях. Он не выполняет расчёты и не изменяет план автоматически." />
          </div>
          <div className="llm-box">
            {data.latest_report?.llm_recommendations
              || "После запуска проверки здесь появятся пояснения и предложения по корректировке плана."}
          </div>
        </div>
      ) : null}
    </section>
  );
}
