import { useEffect, useState } from "react";
import { getErrorMessage, getExportUrl, getTable3, updatePlanStatus, validatePlan } from "../api";
import EmptyState from "../components/EmptyState";

const LEVEL_ICONS = { critical: "🔴", error: "🟠", warning: "🟡" };
const LEVEL_LABELS = { critical: "Критическое", error: "Ошибка", warning: "Предупреждение" };

const STATUS_META = {
  ok:       { cls: "ok",       icon: "✅", title: "Всё в порядке",         sub: "Все проверки пройдены. Блокирующих нарушений нет — план можно утверждать." },
  critical: { cls: "critical", icon: "🚨", title: "Критические нарушения", sub: "Утверждение невозможно. Устраните критические нарушения и повторите проверку." },
  error:    { cls: "error",    icon: "⛔", title: "Обнаружены ошибки",      sub: "Утверждение заблокировано. Исправьте ошибки и запустите проверку повторно." },
  warning:  { cls: "warning",  icon: "⚠️", title: "Есть предупреждения",   sub: "Предупреждения не блокируют утверждение, но требуют внимания методиста." },
  empty:    { cls: "",         icon: "📋", title: "Проверка не запускалась", sub: "Нажмите «Запустить проверку», чтобы получить детальный отчёт и рекомендации ИИ." },
};

function IssueGroup({ level, issues }) {
  const [open, setOpen] = useState(true);
  if (!issues.length) return null;
  return (
    <div className="issues-group">
      <button
        className={`issues-group-header igt-${level}`}
        onClick={() => setOpen((o) => !o)}
        type="button"
      >
        <span>{LEVEL_ICONS[level]} {LEVEL_LABELS[level]}</span>
        <span className="issues-group-count">{issues.length}</span>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-3)" }}>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="issues-list">
          {issues.map((r) => (
            <div key={`${r.rule_id}-${r.message}`} className={`issue-card ${level}`}>
              <div className="issue-card__stripe" />
              <div className="issue-card__body">
                <div className="issue-card__msg">{r.message}</div>
                {(r.actual !== null && r.actual !== undefined) && (
                  <div className="issue-card__detail">
                    Факт: {String(r.actual)} · Ожидалось: {String(r.expected ?? "—")} · Правило #{r.rule_id}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Table3({ plan, planId, onNotice, onRefresh }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");
  const [busy, setBusy]       = useState("");

  useEffect(() => {
    if (!planId) { setData(null); return; }
    let cancelled = false;
    setLoading(true); setError("");
    getTable3(planId)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(getErrorMessage(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [planId]);

  const handleValidate = async () => {
    setBusy("validate");
    try {
      await validatePlan(planId);
      onNotice?.("Проверка завершена", "success");
      onRefresh?.();
      // reload table3 data
      const d = await getTable3(planId);
      setData(d);
    } catch (e) { onNotice?.(getErrorMessage(e), "error"); }
    finally { setBusy(""); }
  };

  const handleApprove = async () => {
    setBusy("approve");
    try {
      await updatePlanStatus(planId, "approved");
      onNotice?.("План утверждён", "success");
      onRefresh?.();
    } catch (e) { onNotice?.(getErrorMessage(e), "error"); }
    finally { setBusy(""); }
  };

  if (!plan) return null;

  const vs = data?.validation_summary;
  const issues = data?.latest_report?.results || [];
  const hasReport = Boolean(data?.latest_report);
  const statusKey = !hasReport ? "empty" : (vs?.status || "ok");
  const meta = STATUS_META[statusKey] || STATUS_META.ok;
  const canApprove = hasReport && (vs?.status === "ok" || vs?.status === "warning");

  const criticals = issues.filter((i) => i.level === "critical");
  const errors    = issues.filter((i) => i.level === "error");
  const warnings  = issues.filter((i) => i.level === "warning");

  const agg = data?.aggregates;
  const devs = data?.deviations;

  return (
    <div className="page-panel">
      <div className="section-header">
        <div>
          <div className="section-header__title">Проверка и экспорт</div>
          <div className="section-header__sub">Валидация нормативов, рекомендации ИИ и утверждение плана</div>
        </div>
      </div>

      {error && <div className="notice notice-error"><span className="notice-icon">✗</span>{error}</div>}
      {loading && <div className="notice notice-warning"><span className="notice-icon">⏳</span>Загрузка данных…</div>}

      {/* Status block */}
      <div className={`validation-status-block${meta.cls ? " " + meta.cls : ""}`}>
        <div className="vs-icon">{meta.icon}</div>
        <div className="vs-body">
          <div className="vs-title">{meta.title}</div>
          <div className="vs-sub">{meta.sub}</div>
        </div>
        <div className="vs-actions">
          <button
            className="btn btn-primary"
            onClick={handleValidate}
            disabled={busy !== ""}
          >
            {busy === "validate"
              ? <><span className="spinner" /> Проверка…</>
              : hasReport ? "Повторить проверку" : "Запустить проверку"
            }
          </button>
          {hasReport && (
            <button
              className="btn btn-secondary"
              onClick={handleApprove}
              disabled={busy !== "" || !canApprove}
              title={!canApprove ? "Устраните критические нарушения и ошибки перед утверждением" : ""}
            >
              {busy === "approve" ? <><span className="spinner" /> Утверждение…</> : "Утвердить план"}
            </button>
          )}
          <button className="btn btn-secondary" onClick={() => window.open(getExportUrl(planId), "_blank", "noopener,noreferrer")}>
            ↓ XLSX
          </button>
        </div>
      </div>

      {/* Stat cards */}
      {agg && (
        <div className="stat-cards">
          <div className="stat-card accent">
            <div className="stat-card__label">Всего з.е.</div>
            <div className="stat-card__value">{agg.total_credits}</div>
            <div className="stat-card__sub">норма 240</div>
          </div>
          <div className={`stat-card ${(agg.mandatory_percent * 100) >= 40 ? "ok" : "warn"}`}>
            <div className="stat-card__label">Обяз. часть</div>
            <div className="stat-card__value">{(agg.mandatory_percent * 100).toFixed(1)}%</div>
            <div className="stat-card__sub">норма ≥ 40%</div>
          </div>
          <div className={`stat-card ${criticals.length === 0 && errors.length === 0 ? "ok" : "err"}`}>
            <div className="stat-card__label">Нарушений</div>
            <div className="stat-card__value">{issues.length}</div>
            <div className="stat-card__sub">{criticals.length} крит. · {errors.length} ош.</div>
          </div>
          <div className="stat-card">
            <div className="stat-card__label">Всего часов</div>
            <div className="stat-card__value">{agg.total_hours}</div>
          </div>
        </div>
      )}

      {/* Deviations table */}
      {devs && (
        <div className="card" style={{ marginBottom: "var(--s-5)" }}>
          <div className="card-body--sm">
            <div className="card-section-title">📊 Отклонения от нормативов</div>
            <table className="dev-table">
              <thead>
                <tr>
                  <th>Показатель</th>
                  <th>Факт</th>
                  <th>Норматив</th>
                  <th>Δ</th>
                </tr>
              </thead>
              <tbody>
                {devs.total_credits && (
                  <DevRow label="Общий объём программы" d={devs.total_credits} />
                )}
                {devs.mandatory_percent && (
                  <DevRow label="Обязательная часть" d={devs.mandatory_percent} />
                )}
                {devs.by_block && Object.entries(devs.by_block).map(([b, d]) => (
                  <DevRow key={b} label={`Блок ${b}`} d={d} />
                ))}
                {devs.by_year && Object.entries(devs.by_year).map(([y, d]) => (
                  <DevRow key={y} label={`Год ${y}`} d={d} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Issues */}
      {hasReport && (
        <div style={{ marginBottom: "var(--s-5)" }}>
          <div className="card-section-title" style={{ marginBottom: "var(--s-3)" }}>
            🔍 Результаты проверки
          </div>
          {issues.length === 0 ? (
            <div className="notice notice-success">
              <span className="notice-icon">✓</span>
              Нарушений не обнаружено. Все проверки пройдены успешно.
            </div>
          ) : (
            <>
              <IssueGroup level="critical" issues={criticals} />
              <IssueGroup level="error"    issues={errors} />
              <IssueGroup level="warning"  issues={warnings} />
            </>
          )}
        </div>
      )}

      {!hasReport && !loading && (
        <EmptyState
          icon="🔍"
          title="Проверка не запускалась"
          description="Нажмите «Запустить проверку», чтобы получить список нарушений, отклонения от нормативов и рекомендации ИИ."
        />
      )}

      {/* LLM recommendations */}
      {data?.latest_report?.llm_recommendations && (
        <div className="ai-rec-block">
          <div className="ai-rec-header">
            <span className="ai-rec-icon">✦</span>
            <span className="ai-rec-title">Рекомендации ИИ-ассистента</span>
          </div>
          <div className="ai-rec-body">
            {data.latest_report.llm_recommendations}
          </div>
        </div>
      )}
    </div>
  );
}

function DevRow({ label, d }) {
  if (!d) return null;
  const delta = typeof d.delta === "number" ? d.delta : null;
  const cls = delta === null ? "zero" : delta > 0 ? "pos" : delta < 0 ? "neg" : "zero";
  return (
    <tr>
      <td>{label}</td>
      <td><strong>{d.actual}</strong></td>
      <td style={{ color: "var(--text-3)" }}>{d.expected}</td>
      <td>
        <span className={`dev-delta ${cls}`}>
          {delta === null ? "—" : delta >= 0 ? `+${delta}` : delta}
        </span>
      </td>
    </tr>
  );
}
