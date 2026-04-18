import { useEffect, useState } from "react";

import { createPlan, deletePlan, getErrorMessage, listPlans } from "./api";
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

const labels = {
  table1: "Таблица 1",
  table2: "Таблица 2",
  table3: "Таблица 3",
};

export default function App() {
  const [activePage, setActivePage] = useState("table1");
  const [plans, setPlans] = useState([]);
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [newPlanName, setNewPlanName] = useState("");
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState("");
  const [refreshToken, setRefreshToken] = useState(0);
  const [globalNotice, setGlobalNotice] = useState("");
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [deletingPlanId, setDeletingPlanId] = useState(null);

  const selectedPlan = plans.find((plan) => plan.id === selectedPlanId) || null;

  useEffect(() => {
    let cancelled = false;

    const loadPlans = async () => {
      setPlansLoading(true);
      setPlansError("");
      try {
        const data = await listPlans();
        if (cancelled) {
          return;
        }
        setPlans(data);
        if (selectedPlanId !== null && !data.some((plan) => plan.id === selectedPlanId)) {
          setSelectedPlanId(null);
        }
      } catch (error) {
        if (!cancelled) {
          setPlansError(getErrorMessage(error, "Не удалось загрузить список учебных планов."));
        }
      } finally {
        if (!cancelled) {
          setPlansLoading(false);
        }
      }
    };

    loadPlans();
    return () => {
      cancelled = true;
    };
  }, [refreshToken, selectedPlanId]);

  const handleCreatePlan = async (event) => {
    event.preventDefault();
    const trimmedName = newPlanName.trim();
    if (!trimmedName) {
      setGlobalNotice("Укажите название учебного плана.");
      return;
    }

    setCreatingPlan(true);
    try {
      const createdPlan = await createPlan(trimmedName);
      setNewPlanName("");
      setSelectedPlanId(createdPlan.id);
      setGlobalNotice(`Учебный план «${createdPlan.name}» создан.`);
      setRefreshToken((value) => value + 1);
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
      if (selectedPlanId === plan.id) {
        setSelectedPlanId(null);
      }
      setGlobalNotice(`Учебный план «${plan.name}» удалён.`);
      setRefreshToken((value) => value + 1);
    } catch (error) {
      setGlobalNotice(getErrorMessage(error, "Не удалось удалить учебный план."));
    } finally {
      setDeletingPlanId(null);
    }
  };

  const handleRefresh = (message = "") => {
    if (message) {
      setGlobalNotice(message);
    }
    setRefreshToken((value) => value + 1);
  };

  const ActivePage = pages[activePage];

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Интеллектуальный методист</p>
          <h1>Формирование учебного плана</h1>
          <p className="hero-copy">
            Модуль помогает выбрать обязательные элементы ФГОС, перенести рекомендации в рабочую
            структуру плана, выполнить детерминированную проверку и подготовить итоговую выгрузку.
          </p>
        </div>
        <div className="hero-side card">
          <p className="card-kicker">Логика MVP</p>
          <ul className="simple-list compact">
            <li>Таблица 1 нужна для выбора вариантов, а не для расчётов.</li>
            <li>Все нормативные суммы и проверки считаются только по Таблице 2.</li>
            <li>Пояснения ИИ появляются только после детерминированной проверки.</li>
          </ul>
        </div>
      </header>

      {globalNotice ? <div className="notice-banner">{globalNotice}</div> : null}

      {!selectedPlan ? (
        <section className="plan-browser">
          <div className="card card-section">
            <div className="section-header">
              <div>
                <p className="card-kicker">Учебные планы</p>
                <h2>Список учебных планов</h2>
              </div>
            </div>

            <form className="stacked-form create-plan-form" onSubmit={handleCreatePlan}>
              <label className="field">
                <span>Название нового плана</span>
                <input
                  value={newPlanName}
                  onChange={(event) => setNewPlanName(event.target.value)}
                  placeholder="Например, Бакалавриат 2026"
                />
              </label>
              <button className="primary-button" type="submit" disabled={creatingPlan}>
                {creatingPlan ? "Создание..." : "Создать учебный план"}
              </button>
            </form>

            {plansError ? <p className="status-message status-error">{plansError}</p> : null}
          </div>

          <div className="plan-grid">
            {plansLoading ? (
              <EmptyState title="Загрузка" description="Получаем список учебных планов." />
            ) : null}

            {!plansLoading && plans.length === 0 ? (
              <EmptyState
                title="Планов пока нет"
                description="Создайте первый учебный план, чтобы перейти к Таблицам 1–3."
              />
            ) : null}

            {plans.map((plan) => (
              <article key={plan.id} className="card plan-card">
                <div className="section-header">
                  <div>
                    <p className="card-kicker">Учебный план</p>
                    <h3>{plan.name}</h3>
                  </div>
                  <StatusBadge value={plan.status} />
                </div>
                <p className="status-muted">
                  Последнее изменение: {new Date(plan.updated_at).toLocaleString("ru-RU")}
                </p>
                <div className="row-actions">
                  <button type="button" className="primary-button" onClick={() => setSelectedPlanId(plan.id)}>
                    Открыть
                  </button>
                  <button
                    type="button"
                    className="small-button danger"
                    onClick={() => handleDeletePlan(plan)}
                    disabled={deletingPlanId === plan.id}
                  >
                    {deletingPlanId === plan.id ? "Удаление..." : "Удалить"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : (
        <section className="workspace">
          <div className="card workspace-header">
            <div className="workspace-header-main">
              <div>
                <p className="card-kicker">Учебный план</p>
                <h2>{selectedPlan.name}</h2>
              </div>

              <div className="workspace-header-actions">
                <div className="selected-plan">
                  <span className="health-label">Статус</span>
                  <StatusBadge value={selectedPlan.status} />
                </div>
                <button type="button" className="secondary-button" onClick={() => setSelectedPlanId(null)}>
                  К списку планов
                </button>
              </div>
            </div>

            <div className="workspace-hint">
              <p className="card-kicker">Этапы работы</p>
              <ol className="step-list inline-steps">
                <li>Выберите обязательные и рекомендованные элементы в Таблице 1.</li>
                <li>Скорректируйте структуру и связи с компетенциями в Таблице 2.</li>
                <li>Запустите проверку, изучите отчёт и при необходимости утвердите план.</li>
              </ol>
            </div>
          </div>

          <section className="content-area">
            <nav className="tabs" aria-label="Навигация по разделам учебного плана">
              {Object.entries(labels).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={key === activePage ? "tab active" : "tab"}
                  onClick={() => setActivePage(key)}
                >
                  {label}
                </button>
              ))}
            </nav>

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
          </section>
        </section>
      )}
    </div>
  );
}
