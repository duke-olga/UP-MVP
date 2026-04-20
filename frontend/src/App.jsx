import { useEffect, useMemo, useState } from "react";

import { createPlan, deletePlan, getErrorMessage, listPlans, listPrograms } from "./api";
import EmptyState from "./components/EmptyState";
import StatusBadge from "./components/StatusBadge";
import Table1 from "./pages/Table1";
import Table2 from "./pages/Table2";
import Table3 from "./pages/Table3";

const pages = {
  table1: Table1,
  table2: Table2,
  table3: Table3,
};

const tabConfig = {
  table1: { num: "1", label: "Рекомендации ФГОС" },
  table2: { num: "2", label: "Структура плана" },
  table3: { num: "3", label: "Проверка и утверждение" },
};

const statusLabels = {
  draft: "Черновик",
  checked: "Проверен",
  approved: "Утверждён",
};

export default function App() {
  const [activePage, setActivePage] = useState("table1");
  const [plans, setPlans] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [newPlanName, setNewPlanName] = useState("");
  const [newProgramCode, setNewProgramCode] = useState("");
  const [plansLoading, setPlansLoading] = useState(true);
  const [programsLoading, setProgramsLoading] = useState(true);
  const [plansError, setPlansError] = useState("");
  const [programsError, setProgramsError] = useState("");
  const [refreshToken, setRefreshToken] = useState(0);
  const [globalNotice, setGlobalNotice] = useState("");
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [deletingPlanId, setDeletingPlanId] = useState(null);

  const selectedPlan = useMemo(
    () => plans.find((plan) => plan.id === selectedPlanId) || null,
    [plans, selectedPlanId],
  );

  useEffect(() => {
    let cancelled = false;

    const loadPrograms = async () => {
      setProgramsLoading(true);
      setProgramsError("");
      try {
        const data = await listPrograms();
        if (cancelled) return;
        setPrograms(data);
        if (!newProgramCode && data.length > 0) {
          setNewProgramCode(data[0].code);
        }
      } catch (error) {
        if (!cancelled) {
          setProgramsError(getErrorMessage(error, "Не удалось загрузить список направлений."));
        }
      } finally {
        if (!cancelled) setProgramsLoading(false);
      }
    };

    loadPrograms();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadPlans = async () => {
      setPlansLoading(true);
      setPlansError("");
      try {
        const data = await listPlans();
        if (cancelled) return;
        setPlans(data);
        if (selectedPlanId !== null && !data.some((plan) => plan.id === selectedPlanId)) {
          setSelectedPlanId(null);
        }
      } catch (error) {
        if (!cancelled) {
          setPlansError(getErrorMessage(error, "Не удалось загрузить список учебных планов."));
        }
      } finally {
        if (!cancelled) setPlansLoading(false);
      }
    };

    loadPlans();
    return () => { cancelled = true; };
  }, [refreshToken, selectedPlanId]);

  const handleCreatePlan = async (event) => {
    event.preventDefault();
    const trimmedName = newPlanName.trim();
    if (!trimmedName) {
      setGlobalNotice("Укажите название учебного плана.");
      return;
    }
    if (!newProgramCode) {
      setGlobalNotice("Сначала выберите направление подготовки.");
      return;
    }

    setCreatingPlan(true);
    try {
      const createdPlan = await createPlan(trimmedName, newProgramCode);
      setNewPlanName("");
      setSelectedPlanId(createdPlan.id);
      setGlobalNotice(`Учебный план «${createdPlan.name}» создан.`);
      setRefreshToken((v) => v + 1);
      setActivePage("table1");
    } catch (error) {
      setGlobalNotice(getErrorMessage(error, "Не удалось создать учебный план."));
    } finally {
      setCreatingPlan(false);
    }
  };

  const handleDeletePlan = async (plan) => {
    if (!window.confirm(`Удалить учебный план «${plan.name}»? Это действие нельзя отменить.`)) {
      return;
    }

    setDeletingPlanId(plan.id);
    try {
      await deletePlan(plan.id);
      if (selectedPlanId === plan.id) setSelectedPlanId(null);
      setGlobalNotice(`Учебный план «${plan.name}» удалён.`);
      setRefreshToken((v) => v + 1);
    } catch (error) {
      setGlobalNotice(getErrorMessage(error, "Не удалось удалить учебный план."));
    } finally {
      setDeletingPlanId(null);
    }
  };

  const handleRefresh = (message = "") => {
    if (message) setGlobalNotice(message);
    setRefreshToken((v) => v + 1);
  };

  const handleBackToList = () => {
    setSelectedPlanId(null);
    setActivePage("table1");
  };

  const ActivePage = pages[activePage];
  const selectedProgram = programs.find((p) => p.code === newProgramCode);

  return (
    <>
      {/* ── Sticky top header ── */}
      <header className="app-header">
        <div className="app-header-inner">
          <div className="app-brand">
            <span className="app-logo-mark">ИМ</span>
            <span className="app-title-text">Интеллектуальный методист</span>
          </div>

          {selectedPlan ? (
            <>
              <span className="hdr-divider" />
              <div className="hdr-breadcrumb">
                <button className="hdr-breadcrumb-link" type="button" onClick={handleBackToList}>
                  Учебные планы
                </button>
                <span className="hdr-breadcrumb-sep">/</span>
                <span className="hdr-breadcrumb-current">{selectedPlan.name}</span>
              </div>
            </>
          ) : null}

          {selectedPlan ? (
            <div className="hdr-actions">
              <StatusBadge value={selectedPlan.status}>
                {statusLabels[selectedPlan.status] || selectedPlan.status}
              </StatusBadge>
              <button className="btn-hdr" type="button" onClick={handleBackToList}>
                ← К списку
              </button>
            </div>
          ) : null}
        </div>
      </header>

      {/* ── Main content ── */}
      <main className="app-main">
        {globalNotice ? (
          <div className="notice-banner" role="status">
            {globalNotice}
          </div>
        ) : null}

        {!selectedPlan ? (
          /* ── Plan browser ── */
          <div className="plans-layout">

            {/* Sidebar: create form */}
            <aside className="plans-sidebar">
              <div className="card">
                <p className="card-kicker">Новый план</p>
                <h2 style={{ fontSize: "16px", marginBottom: "16px" }}>Создать учебный план</h2>

                <form className="stacked-form create-plan-form" onSubmit={handleCreatePlan}>
                  <label className="field">
                    <span>Направление подготовки</span>
                    <select
                      value={newProgramCode}
                      onChange={(e) => setNewProgramCode(e.target.value)}
                      disabled={programsLoading || programs.length === 0}
                    >
                      {programs.map((program) => (
                        <option key={program.code} value={program.code}>
                          {program.title}
                        </option>
                      ))}
                    </select>
                  </label>

                  {programsLoading ? (
                    <p className="status-muted">Загрузка направлений…</p>
                  ) : null}
                  {programsError ? (
                    <p className="status-message status-error">{programsError}</p>
                  ) : null}
                  {!programsLoading && !programsError && selectedProgram ? (
                    <p className="status-muted">
                      Источники: {selectedProgram.sources.join(", ") || "не указаны"}
                    </p>
                  ) : null}

                  <label className="field">
                    <span>Название плана</span>
                    <input
                      value={newPlanName}
                      onChange={(e) => setNewPlanName(e.target.value)}
                      placeholder="Например, Бакалавриат 2026"
                    />
                  </label>

                  <button
                    className="primary-button"
                    type="submit"
                    disabled={creatingPlan || !newProgramCode}
                    style={{ width: "100%" }}
                  >
                    {creatingPlan ? "Создание…" : "Создать план"}
                  </button>
                </form>

                {plansError ? (
                  <p className="status-message status-error" style={{ marginTop: "12px" }}>
                    {plansError}
                  </p>
                ) : null}
              </div>

              {/* MVP workflow hint */}
              <div className="card" style={{ fontSize: "13px" }}>
                <p className="card-kicker">Как работает</p>
                <ol style={{ paddingLeft: "16px", margin: "8px 0 0", display: "grid", gap: "8px", listStyle: "decimal", color: "var(--text-3)" }}>
                  <li>Выберите направление подготовки и создайте план.</li>
                  <li>В Таблице 1 отметьте обязательные элементы ФГОС и перенесите их.</li>
                  <li>Откорректируйте структуру и компетенции в Таблице 2.</li>
                  <li>Запустите проверку, изучите отчёт и утвердите план.</li>
                </ol>
              </div>
            </aside>

            {/* Plans grid */}
            <div className="plans-main">
              <div className="plans-header">
                <span className="plans-section-title">
                  {plansLoading
                    ? "Загрузка…"
                    : `Учебные планы${plans.length > 0 ? ` · ${plans.length}` : ""}`}
                </span>
              </div>

              {plansLoading ? (
                <EmptyState title="Загрузка" description="Получаем список учебных планов…" />
              ) : !plans.length ? (
                <EmptyState
                  title="Планов пока нет"
                  description="Создайте первый учебный план слева, чтобы начать работу."
                />
              ) : (
                <div className="plans-grid">
                  {plans.map((plan) => (
                    <article key={plan.id} className="card plan-card">
                      <div className="plan-card-head">
                        <p className="plan-card-name">{plan.name}</p>
                        <StatusBadge value={plan.status}>
                          {statusLabels[plan.status] || plan.status}
                        </StatusBadge>
                      </div>
                      <div className="plan-card-info">
                        <span>Направление: {plan.program_code}</span>
                        <span>
                          Изменён:{" "}
                          {new Date(plan.updated_at).toLocaleString("ru-RU", {
                            day: "2-digit",
                            month: "2-digit",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <div className="plan-card-actions">
                        <button
                          type="button"
                          className="primary-button"
                          onClick={() => setSelectedPlanId(plan.id)}
                        >
                          Открыть
                        </button>
                        <button
                          type="button"
                          className="small-button danger"
                          onClick={() => handleDeletePlan(plan)}
                          disabled={deletingPlanId === plan.id}
                        >
                          {deletingPlanId === plan.id ? "Удаление…" : "Удалить"}
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          /* ── Workspace ── */
          <div className="workspace">
            {/* Step tabs */}
            <nav className="step-tabs" aria-label="Этапы работы с учебным планом">
              {Object.entries(tabConfig).map(([key, { num, label }]) => (
                <button
                  key={key}
                  type="button"
                  className={`step-tab${key === activePage ? " active" : ""}`}
                  onClick={() => setActivePage(key)}
                >
                  <span className="step-tab-num">{num}</span>
                  <span className="step-tab-label">{label}</span>
                </button>
              ))}
            </nav>

            {/* Active page */}
            <main className="page-panel">
              <ActivePage
                plan={selectedPlan}
                planId={selectedPlanId}
                refreshToken={refreshToken}
                onNavigate={setActivePage}
                onRefresh={handleRefresh}
                setGlobalNotice={setGlobalNotice}
              />
            </main>
          </div>
        )}
      </main>
    </>
  );
}
