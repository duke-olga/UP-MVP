import { useEffect, useState } from "react";

import { getErrorMessage, getExportUrl, getTable3, updatePlanStatus, validatePlan } from "../api";
import StatusBadge from "../components/StatusBadge";

const levelLabels = {
  critical: "Критическое нарушение",
  error: "Ошибка",
  warning: "Предупреждение",
};

const summaryMap = {
  ok: {
    tone: "approved",
    title: "Нарушения не обнаружены",
    description: "План можно утверждать. Блокирующих нарушений и ошибок нет.",
  },
  critical: {
    tone: "critical",
    title: "Есть критические нарушения",
    description: "План нельзя утвердить, пока критические нарушения не устранены.",
  },
  error: {
    tone: "error",
    title: "Есть ошибки",
    description: "План нельзя утвердить, пока ошибки не устранены.",
  },
  warning: {
    tone: "warning",
    title: "Есть предупреждения",
    description: "Предупреждения не блокируют утверждение, но требуют внимания методиста.",
  },
};

function DeviationRow({ label, item }) {
  return (
    <div className="deviation-row">
      <span>{label}</span>
      <strong>{item.actual}</strong>
      <span>{item.expected}</span>
      <span className={item.delta > 0 ? "delta positive" : item.delta < 0 ? "delta negative" : "delta"}>
        {item.delta}
      </span>
    </div>
  );
}

export default function Table3({ plan, planId, refreshToken, onRefresh, setGlobalNotice }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState("");

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
        const table3 = await getTable3(planId);
        if (!cancelled) {
          setData(table3);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, "Не удалось загрузить экран проверки."));
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

  const handleValidate = async () => {
    setBusyAction("validate");
    try {
      await validatePlan(planId);
      onRefresh("Проверка плана выполнена.");
    } catch (validateError) {
      setGlobalNotice(getErrorMessage(validateError, "Не удалось выполнить проверку плана."));
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
    return (
      <section className="card">
        <h2>Проверка</h2>
        <p>Сначала выберите учебный план на стартовом экране.</p>
      </section>
    );
  }

  const validationSummary = data?.validation_summary || {
    status: "ok",
    critical_count: 0,
    error_count: 0,
    warning_count: 0,
  };
  const summary = summaryMap[validationSummary.status] || summaryMap.ok;
  const issues = data?.latest_report?.results || [];

  return (
    <section className="stack-panel">
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Проверка</p>
            <h2>Проверка и утверждение учебного плана</h2>
          </div>
          <div className="toolbar">
            <button className="primary-button" type="button" onClick={handleValidate} disabled={busyAction !== ""}>
              {busyAction === "validate" ? "Проверка..." : "Проверить план"}
            </button>
            <button className="secondary-button" type="button" onClick={handleApprove} disabled={busyAction !== ""}>
              {busyAction === "approve" ? "Утверждение..." : "Утвердить план"}
            </button>
            <button className="secondary-button" type="button" onClick={handleExport}>
              Скачать в Excel
            </button>
          </div>
        </div>
        <p className="status-muted">
          Утверждение блокируется при критических нарушениях и ошибках. Предупреждения и рекомендации ИИ не блокируют
          утверждение.
        </p>
        {loading ? <p className="status-muted">Загрузка данных проверки...</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

      <div className={`card summary-card ${summary.tone}`}>
        <div className="section-header">
          <div>
            <p className="card-kicker">Итог проверки</p>
            <h3>{summary.title}</h3>
          </div>
          <StatusBadge value={summary.tone === "approved" ? "approved" : summary.tone} />
        </div>
        <p>{summary.description}</p>
      </div>

      <div className="card totals-grid">
        <div className="metric-tile">
          <span>Критические нарушения</span>
          <strong>{validationSummary.critical_count}</strong>
        </div>
        <div className="metric-tile">
          <span>Ошибки</span>
          <strong>{validationSummary.error_count}</strong>
        </div>
        <div className="metric-tile">
          <span>Предупреждения</span>
          <strong>{validationSummary.warning_count}</strong>
        </div>
        <div className="metric-tile">
          <span>Статус плана</span>
          <strong>{plan.status === "approved" ? "Утверждён" : plan.status === "checked" ? "Проверен" : "Черновик"}</strong>
        </div>
      </div>

      {data ? (
        <>
          <div className="card">
            <div className="section-header">
              <div>
                <p className="card-kicker">Нормативные показатели</p>
                <h3>Факт / норматив / отклонение</h3>
              </div>
            </div>
            <div className="deviation-table">
              <div className="deviation-row deviation-head">
                <span>Показатель</span>
                <span>Факт</span>
                <span>Норматив</span>
                <span>Отклонение</span>
              </div>
              <DeviationRow label="Общий объём" item={data.deviations.total_credits} />
              <DeviationRow label="Обязательная часть" item={data.deviations.mandatory_percent} />
              {Object.entries(data.deviations.by_block).map(([block, item]) => (
                <DeviationRow key={block} label={`Блок ${block}`} item={item} />
              ))}
              {Object.entries(data.deviations.by_year).map(([year, item]) => (
                <DeviationRow key={year} label={`Год ${year}`} item={item} />
              ))}
            </div>
          </div>

          <div className="card">
            <div className="section-header">
              <div>
                <p className="card-kicker">Нарушения</p>
                <h3>Результаты детерминированной проверки</h3>
              </div>
            </div>
            {issues.length ? (
              <div className="issue-list">
                {issues.map((result) => (
                  <div key={`${result.rule_id}-${result.message}`} className={`issue-card ${result.level}`}>
                    <div className="issue-head">
                      <strong>Правило #{result.rule_id}</strong>
                      <StatusBadge value={result.level}>{levelLabels[result.level] || result.level}</StatusBadge>
                    </div>
                    <p>{result.message}</p>
                    <small>
                      Факт: {String(result.actual ?? "—")} · Норматив: {String(result.expected ?? "—")}
                    </small>
                  </div>
                ))}
              </div>
            ) : (
              <p className="status-muted">После запуска проверки здесь появится список нарушений и предупреждений.</p>
            )}
          </div>

          <div className="card">
            <div className="section-header">
              <div>
                <p className="card-kicker">ИИ</p>
                <h3>Пояснения и рекомендации ИИ</h3>
              </div>
            </div>
            <p className="status-muted">
              ИИ помогает интерпретировать результаты проверки, но не выполняет нормативные расчёты и не изменяет
              учебный план автоматически.
            </p>
            <div className="llm-box">
              {data.latest_report?.llm_recommendations || "После запуска проверки здесь появятся пояснения ИИ."}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
