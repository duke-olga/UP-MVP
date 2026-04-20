import { useEffect, useMemo, useRef, useState } from "react";

import { createPlan, deletePlan, getErrorMessage, listPlans, listPrograms } from "./api";
import AiChat from "./components/AiChat";
import EmptyState from "./components/EmptyState";
import StatusBadge from "./components/StatusBadge";
import PlanSetup from "./pages/PlanSetup";
import Table1 from "./pages/Table1";
import Table2 from "./pages/Table2";
import Table3 from "./pages/Table3";
import "./styles.css";

const STEPS = [
  { key: "setup",  num: 1, label: "Настройка плана",    sub: "Программа и название" },
  { key: "table1", num: 2, label: "Рекомендации ФГОС",  sub: "Выбор дисциплин" },
  { key: "table2", num: 3, label: "Учебный план",        sub: "Структура и нагрузка" },
  { key: "table3", num: 4, label: "Проверка и экспорт", sub: "Валидация и утверждение" },
];

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" });
}

export default function App() {
  const [activeStep, setActiveStep] = useState("setup");
  const [plans, setPlans] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [plansLoading, setPlansLoading] = useState(true);
  const [programsLoading, setProgramsLoading] = useState(true);
  const [refreshToken, setRefreshToken] = useState(0);
  const [notice, setNotice] = useState({ msg: "", type: "success" });
  const [deletingId, setDeletingId] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createProgram, setCreateProgram] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const noticeTimer = useRef(null);

  const selectedPlan = useMemo(
    () => plans.find((p) => p.id === selectedPlanId) || null,
    [plans, selectedPlanId],
  );

  const showNotice = (msg, type = "success") => {
    setNotice({ msg, type });
    clearTimeout(noticeTimer.current);
    noticeTimer.current = setTimeout(() => setNotice({ msg: "", type: "success" }), 4000);
  };

  const refresh = () => setRefreshToken((t) => t + 1);

  /* Load plans */
  useEffect(() => {
    let cancelled = false;
    setPlansLoading(true);
    listPlans()
      .then((data) => { if (!cancelled) { setPlans(data); setPlansLoading(false); } })
      .catch(() => { if (!cancelled) setPlansLoading(false); });
    return () => { cancelled = true; };
  }, [refreshToken]);

  /* Load programs */
  useEffect(() => {
    let cancelled = false;
    setProgramsLoading(true);
    listPrograms()
      .then((data) => { if (!cancelled) { setPrograms(data); setProgramsLoading(false); } })
      .catch(() => { if (!cancelled) setProgramsLoading(false); });
    return () => { cancelled = true; };
  }, []);

  /* Open create modal */
  const openCreate = () => {
    setCreateName("");
    setCreateProgram(programs[0]?.code || "");
    setCreateError("");
    setShowCreateModal(true);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!createName.trim()) { setCreateError("Введите название плана"); return; }
    if (!createProgram)     { setCreateError("Выберите программу"); return; }
    setCreating(true);
    setCreateError("");
    try {
      const plan = await createPlan(createName.trim(), createProgram);
      setShowCreateModal(false);
      refresh();
      setSelectedPlanId(plan.id);
      setActiveStep("setup");
    } catch (err) {
      setCreateError(getErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Удалить этот учебный план? Это действие необратимо.")) return;
    setDeletingId(id);
    try {
      await deletePlan(id);
      if (selectedPlanId === id) setSelectedPlanId(null);
      refresh();
      showNotice("План удалён");
    } catch (err) {
      showNotice(getErrorMessage(err), "error");
    } finally {
      setDeletingId(null);
    }
  };

  const openPlan = (plan) => {
    setSelectedPlanId(plan.id);
    setActiveStep("setup");
  };

  const backToList = () => {
    setSelectedPlanId(null);
    refresh();
  };

  /* ================================================================= */
  /*  Header                                                             */
  /* ================================================================= */
  const renderHeader = () => (
    <header className="app-header">
      <div className="app-header__brand">
        <div className="app-header__logo">М</div>
        Интеллектуальный методист
      </div>

      {selectedPlan && (
        <>
          <span className="app-header__divider">/</span>
          <nav className="app-header__breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); backToList(); }}>Планы</a>
            <span className="sep">›</span>
            <span className="current">{selectedPlan.name}</span>
          </nav>
        </>
      )}

      <div className="app-header__spacer" />

      <div className="app-header__actions">
        {selectedPlan && <StatusBadge value={selectedPlan.status} />}
        {selectedPlan && (
          <button className="btn btn-ghost btn-sm" onClick={backToList}>
            ← К планам
          </button>
        )}
      </div>
    </header>
  );

  /* ================================================================= */
  /*  Plans Browser                                                      */
  /* ================================================================= */
  const renderPlans = () => (
    <main className="plans-page page-panel">
      {notice.msg && (
        <div className={`notice notice-${notice.type}`}>
          <span className="notice-icon">{notice.type === "success" ? "✓" : "⚠"}</span>
          {notice.msg}
        </div>
      )}

      <div className="plans-page__header">
        <h1 className="plans-page__title">Учебные планы</h1>
        {!plansLoading && (
          <span className="plans-page__count">{plans.length}</span>
        )}
        <div className="plans-page__header-spacer" />
        <button className="btn btn-primary" onClick={openCreate}>
          + Новый план
        </button>
      </div>

      {plansLoading ? (
        <EmptyState icon="⏳" title="Загрузка…" description="Получаем список планов" />
      ) : plans.length === 0 ? (
        <EmptyState
          icon="📋"
          title="Планов пока нет"
          description="Создайте первый учебный план, чтобы начать проектирование ОПОП"
          action={<button className="btn btn-primary" onClick={openCreate}>Создать план</button>}
        />
      ) : (
        <div className="plans-grid">
          {plans.map((plan) => (
            <PlanCard
              key={plan.id}
              plan={plan}
              deleting={deletingId === plan.id}
              onOpen={() => openPlan(plan)}
              onDelete={(e) => handleDelete(plan.id, e)}
            />
          ))}
        </div>
      )}
    </main>
  );

  /* ================================================================= */
  /*  Workspace                                                          */
  /* ================================================================= */
  const stepsWithStatus = useMemo(() => {
    return STEPS.map((step, i) => {
      const activeIdx = STEPS.findIndex((s) => s.key === activeStep);
      return {
        ...step,
        active: step.key === activeStep,
        done: i < activeIdx,
      };
    });
  }, [activeStep]);

  const ActivePage = useMemo(() => {
    if (activeStep === "setup")  return PlanSetup;
    if (activeStep === "table1") return Table1;
    if (activeStep === "table2") return Table2;
    if (activeStep === "table3") return Table3;
    return PlanSetup;
  }, [activeStep]);

  const program = useMemo(
    () => programs.find((p) => p.code === selectedPlan?.program_code),
    [programs, selectedPlan],
  );

  const renderWorkspace = () => (
    <div className="workspace">
      {/* Left sidebar */}
      <aside className="workspace-sidebar">
        <div className="sidebar-section-label">Шаги</div>
        <nav className="step-nav">
          {stepsWithStatus.map((step) => (
            <button
              key={step.key}
              className={`step-nav-item${step.active ? " active" : ""}${step.done ? " done" : ""}`}
              onClick={() => setActiveStep(step.key)}
            >
              <div className="step-nav-item__num">
                {step.done ? "✓" : step.num}
              </div>
              <div className="step-nav-item__text">
                <div className="step-nav-item__label">{step.label}</div>
                <div className="step-nav-item__sub">{step.sub}</div>
              </div>
              <span className="step-nav-item__check">✓</span>
            </button>
          ))}
        </nav>

        {selectedPlan && (
          <div className="sidebar-plan-info">
            <div className="sidebar-plan-info__label">Текущий план</div>
            <div className="sidebar-plan-info__name">{selectedPlan.name}</div>
            {program && (
              <div className="sidebar-plan-info__program">
                {program.code} · {program.title}
              </div>
            )}
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="workspace-main">
        {notice.msg && (
          <div className={`notice notice-${notice.type}`}>
            <span className="notice-icon">{notice.type === "success" ? "✓" : notice.type === "error" ? "✗" : "⚠"}</span>
            {notice.msg}
          </div>
        )}

        <div className="page-panel" key={activeStep}>
          <ActivePage
            planId={selectedPlanId}
            plan={selectedPlan}
            programs={programs}
            onNotice={showNotice}
            onRefresh={refresh}
            onNext={() => {
              const idx = STEPS.findIndex((s) => s.key === activeStep);
              if (idx < STEPS.length - 1) setActiveStep(STEPS[idx + 1].key);
            }}
          />
        </div>
      </main>

      {/* AI Chat */}
      {selectedPlanId && (
        <AiChat
          planId={selectedPlanId}
          open={aiPanelOpen}
          onToggle={() => setAiPanelOpen((o) => !o)}
        />
      )}
    </div>
  );

  /* ================================================================= */
  /*  Create Plan Modal                                                  */
  /* ================================================================= */
  const renderModal = () => (
    <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowCreateModal(false); }}>
      <div className="modal">
        <div className="modal__header">
          <h2 className="modal__title">Новый учебный план</h2>
          <button className="btn-icon" onClick={() => setShowCreateModal(false)}>✕</button>
        </div>
        <form onSubmit={handleCreate}>
          <div className="modal__body">
            <div className="field">
              <label>Образовательная программа</label>
              {programsLoading ? (
                <select disabled><option>Загрузка…</option></select>
              ) : programs.length === 0 ? (
                <select disabled><option>Программы не найдены</option></select>
              ) : (
                <select
                  value={createProgram}
                  onChange={(e) => setCreateProgram(e.target.value)}
                >
                  {programs.map((p) => (
                    <option key={p.code} value={p.code}>
                      {p.code} — {p.title}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="field">
              <label>Название плана</label>
              <input
                type="text"
                placeholder="Например: Учебный план 2025–2029"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                autoFocus
              />
            </div>
            {createError && <p className="field-error">{createError}</p>}
          </div>
          <div className="modal__footer">
            <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
              Отмена
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={creating || !createName.trim() || !createProgram}
            >
              {creating ? <><span className="spinner" /> Создание…</> : "Создать план"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  /* ================================================================= */
  /*  Root render                                                        */
  /* ================================================================= */
  return (
    <>
      {renderHeader()}
      {selectedPlan ? renderWorkspace() : renderPlans()}
      {showCreateModal && renderModal()}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Plan Card                                                           */
/* ------------------------------------------------------------------ */
function PlanCard({ plan, deleting, onOpen, onDelete }) {
  return (
    <article className="plan-card" onClick={onOpen}>
      <div className="plan-card__header">
        <h3 className="plan-card__name">{plan.name}</h3>
        <StatusBadge value={plan.status} />
      </div>
      <div className="plan-card__meta">
        <span className="plan-card__program">Программа: {plan.program_code || "—"}</span>
        <span className="plan-card__date">
          Обновлён {plan.updated_at ? new Date(plan.updated_at).toLocaleDateString("ru-RU", { day: "2-digit", month: "short" }) : "—"}
        </span>
      </div>
      <div className="plan-card__footer">
        <div className="plan-card__footer-spacer" />
        <button
          className="btn btn-danger btn-xs"
          onClick={onDelete}
          disabled={deleting}
        >
          {deleting ? <span className="spinner" /> : "Удалить"}
        </button>
        <button className="btn btn-primary btn-sm" onClick={onOpen}>
          Открыть →
        </button>
      </div>
    </article>
  );
}
