import { useEffect, useState } from "react";

import { createPlan, getErrorMessage, getHealth, listPlans } from "./api";
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
  const [health, setHealth] = useState({ status: "loading", detail: "Проверка backend..." });
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

    const loadHealth = async () => {
      try {
        const data = await getHealth();
        if (!cancelled) {
          setHealth({
            status: data.status === "ok" ? "ok" : "warning",
            detail: `Backend status: ${data.status}`,
          });
        }
      } catch {
        if (!cancelled) {
          setHealth({
            status: "error",
            detail: "Backend недоступен по /api/v1/health",
          });
        }
      }
    };

    loadHealth();
    return () => {
      cancelled = true;
    };
  }, []);

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
        if (data.length === 0) {
          setSelectedPlanId(null);
        } else if (!data.some((plan) => plan.id === selectedPlanId)) {
          setSelectedPlanId(data[0].id);
        }
      } catch (error) {
        if (!cancelled) {
          setPlansError(getErrorMessage(error, "Не удалось загрузить список планов."));
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
      setGlobalNotice("Укажи название плана.");
      return;
    }

    setCreatingPlan(true);
    try {
      const createdPlan = await createPlan(trimmedName);
      setNewPlanName("");
      setSelectedPlanId(createdPlan.id);
      setGlobalNotice(`План «${createdPlan.name}» создан.`);
      setRefreshToken((value) => value + 1);
      setActivePage("table1");
    } catch (error) {
      setGlobalNotice(getErrorMessage(error, "Не удалось создать план."));
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
            Рабочий сценарий MVP: выбрать план, перенести рекомендации, отредактировать структуру,
            проверить нормативы и выгрузить XLSX.
          </p>
        </div>
        <div className={`health health-${health.status}`}>
          <span className="health-label">Health-check</span>
          <strong>{health.detail}</strong>
        </div>
      </header>

      <section className="workspace">
        <aside className="sidebar card">
          <div className="section-header">
            <div>
              <p className="card-kicker">Планы</p>
              <h2>Главная страница</h2>
            </div>
          </div>

          <form className="stacked-form" onSubmit={handleCreatePlan}>
            <label className="field">
              <span>Название нового плана</span>
              <input
                value={newPlanName}
                onChange={(event) => setNewPlanName(event.target.value)}
                placeholder="Например, Бакалавриат 2026"
              />
            </label>
            <button className="primary-button" type="submit" disabled={creatingPlan}>
              {creatingPlan ? "Создание..." : "Создать план"}
            </button>
          </form>

          {plansError ? <p className="status-message status-error">{plansError}</p> : null}

          <div className="plan-list">
            {plansLoading ? <p className="status-muted">Загрузка списка планов...</p> : null}
            {!plansLoading && plans.length === 0 ? (
              <p className="status-muted">Пока нет ни одного плана. Начни с создания нового.</p>
            ) : null}
            {plans.map((plan) => (
              <button
                key={plan.id}
                type="button"
                className={plan.id === selectedPlanId ? "plan-chip active" : "plan-chip"}
                onClick={() => setSelectedPlanId(plan.id)}
              >
                <strong>{plan.name}</strong>
                <span>{plan.status}</span>
              </button>
            ))}
          </div>

          {selectedPlan ? (
            <div className="selected-plan">
              <span className="health-label">Выбранный план</span>
              <strong>{selectedPlan.name}</strong>
              <span>Статус: {selectedPlan.status}</span>
            </div>
          ) : null}
        </aside>

        <section className="content-area">
          <nav className="tabs" aria-label="Навигация по таблицам">
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

          {globalNotice ? <div className="notice-banner">{globalNotice}</div> : null}

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
    </div>
  );
}
