import { useEffect, useState } from "react";

import { getErrorMessage, getExportUrl, getTable3, updatePlanStatus, validatePlan } from "../api";

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
          setError(getErrorMessage(loadError, "Не удалось загрузить Таблицу 3."));
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
    return (
      <section className="card">
        <h2>Таблица 3</h2>
        <p>Сначала выбери или создай учебный план.</p>
      </section>
    );
  }

  return (
    <section className="stack-panel">
      <div className="card">
        <div className="section-header">
          <div>
            <p className="card-kicker">Таблица 3</p>
            <h2>Автоматический контроль</h2>
          </div>
          <div className="toolbar">
            <button className="primary-button" type="button" onClick={handleValidate} disabled={busyAction !== ""}>
              {busyAction === "validate" ? "Проверка..." : "Проверить учебный план"}
            </button>
            <button className="secondary-button" type="button" onClick={handleApprove} disabled={busyAction !== ""}>
              {busyAction === "approve" ? "Утверждение..." : "Утвердить"}
            </button>
            <button className="secondary-button" type="button" onClick={handleExport}>
              Скачать XLSX
            </button>
          </div>
        </div>
        <p className="status-muted">
          План: <strong>{plan.name}</strong>. Статус: <strong>{plan.status}</strong>.
        </p>
        {loading ? <p className="status-muted">Загрузка агрегатов и отчёта...</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}
      </div>

      {data ? (
        <>
          <div className="card">
            <div className="section-header">
              <h3>Факт / норматив / отклонение</h3>
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
              <h3>Нарушения</h3>
            </div>
            {data.latest_report?.results?.length ? (
              <div className="issue-list">
                {data.latest_report.results.map((result) => (
                  <div key={`${result.rule_id}-${result.message}`} className={`issue-card ${result.level}`}>
                    <div className="issue-head">
                      <strong>Правило #{result.rule_id}</strong>
                      <span>{result.level}</span>
                    </div>
                    <p>{result.message}</p>
                    <small>
                      Факт: {String(result.actual ?? "—")} · Норматив: {String(result.expected ?? "—")}
                    </small>
                  </div>
                ))}
              </div>
            ) : (
              <p className="status-muted">Проверка ещё не запускалась.</p>
            )}
          </div>

          <div className="card">
            <div className="section-header">
              <h3>Рекомендации ИИ</h3>
            </div>
            <div className="llm-box">
              {data.latest_report?.llm_recommendations || "После запуска проверки здесь появится текст LLM."}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
