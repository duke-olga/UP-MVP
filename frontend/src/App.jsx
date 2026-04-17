import { useEffect, useState } from "react";

import { createPlan, getErrorMessage, listPlans } from "./api";
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
  table1: "Рекомендации",
  table2: "Структура плана",
  table3: "Проверка",
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
        if (data.length > 0 && selectedPlanId !== null && !data.some((plan) => plan.id === selectedPlanId)) {
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
            Модуль помогает перенести рекомендации по компетенциям в структуру плана, проверить нормативные
            ограничения и подготовить итоговую выгрузку.
          </p>
        </div>
        <div className="hero-side card">
          <p className="card-kicker">Логика MVP</p>
          <ul className="simple-list compact">
            <li>Рекомендации не являются самим учебным планом.</li>
            <li>Структура плана редактируется отдельно.</li>
            <li>Проверка и утверждение выполняются на финальном этапе.</li>
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
              <div className="card empty-state">
                <h3>Загрузка</h3>
                <p>Получаем список учебных планов.</p>
              </div>
            ) : null}
            {!plansLoading && plans.length === 0 ? (
              <div className="card empty-state">
                <h3>Планов пока нет</h3>
                <p>Создайте первый учебный план, чтобы перейти к рекомендациям и проверке.</p>
              </div>
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
                <p className="status-muted">Последнее изменение: {new Date(plan.updated_at).toLocaleString("ru-RU")}</p>
                <button type="button" className="primary-button" onClick={() => setSelectedPlanId(plan.id)}>
                  Открыть
                </button>
              </article>
            ))}
          </div>
        </section>
      ) : (
        <section className="workspace">
          <aside className="sidebar card">
            <div className="section-header">
              <div>
                <p className="card-kicker">Учебный план</p>
                <h2>{selectedPlan.name}</h2>
              </div>
            </div>

            <div className="selected-plan">
              <span className="health-label">Статус</span>
              <StatusBadge value={selectedPlan.status} />
            </div>

            <div className="sidebar-actions">
              <button type="button" className="secondary-button" onClick={() => setSelectedPlanId(null)}>
                К списку планов
              </button>
            </div>

            <div className="sidebar-hint">
              <p className="card-kicker">Этапы работы</p>
              <ol className="step-list">
                <li>Проверьте рекомендации по компетенциям.</li>
                <li>Скорректируйте структуру учебного плана.</li>
                <li>Запустите проверку и при необходимости утвердите план.</li>
              </ol>
            </div>
          </aside>

          <section className="content-area">
            <nav className="tabs" aria-label="Навигация по разделам плана">
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
