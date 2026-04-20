const STATUS_LABELS = { draft: "Черновик", checked: "Проверен", approved: "Утверждён" };

export default function PlanSetup({ plan, programs, onNext }) {
  if (!plan) return null;

  const program = programs?.find((p) => p.code === plan.program_code);

  const created = plan.created_at
    ? new Date(plan.created_at).toLocaleDateString("ru-RU", { day: "2-digit", month: "long", year: "numeric" })
    : "—";
  const updated = plan.updated_at
    ? new Date(plan.updated_at).toLocaleDateString("ru-RU", { day: "2-digit", month: "long", year: "numeric" })
    : "—";

  return (
    <div className="setup-layout page-panel">
      <div className="section-header">
        <div>
          <div className="section-header__title">Настройка плана</div>
          <div className="section-header__sub">Основные сведения об учебном плане</div>
        </div>
      </div>

      {/* Meta card */}
      <div className="setup-meta-card">
        <div className="setup-meta-card__header">
          <span className="setup-meta-card__label">Сведения о плане</span>
        </div>
        <div className="setup-meta-card__body">
          <div className="meta-row">
            <span className="meta-row__icon">📄</span>
            <span className="meta-row__label">Название</span>
            <span className="meta-row__value">{plan.name}</span>
          </div>
          <div className="meta-row">
            <span className="meta-row__icon">🎓</span>
            <span className="meta-row__label">Программа</span>
            <span className="meta-row__value">
              {program ? `${program.code} — ${program.title}` : plan.program_code || "—"}
            </span>
          </div>
          <div className="meta-row">
            <span className="meta-row__icon">🔖</span>
            <span className="meta-row__label">Статус</span>
            <span className="meta-row__value">{STATUS_LABELS[plan.status] || plan.status}</span>
          </div>
          <div className="meta-row">
            <span className="meta-row__icon">📅</span>
            <span className="meta-row__label">Создан</span>
            <span className="meta-row__value">{created}</span>
          </div>
          <div className="meta-row">
            <span className="meta-row__icon">🕐</span>
            <span className="meta-row__label">Обновлён</span>
            <span className="meta-row__value">{updated}</span>
          </div>
        </div>
      </div>

      {/* Next steps hint */}
      <div className="next-steps-card">
        <div className="next-steps-title">Что дальше?</div>
        <div className="next-step-row">
          <div className="next-step-num">2</div>
          <div className="next-step-text">
            <strong>Рекомендации ФГОС</strong> — просмотрите рекомендованные дисциплины
            и практики для вашей программы и перенесите их в план.
          </div>
        </div>
        <div className="next-step-row">
          <div className="next-step-num">3</div>
          <div className="next-step-text">
            <strong>Учебный план</strong> — отредактируйте структуру: блоки, нагрузку,
            семестры и привязку компетенций.
          </div>
        </div>
        <div className="next-step-row">
          <div className="next-step-num">4</div>
          <div className="next-step-text">
            <strong>Проверка и экспорт</strong> — запустите автоматическую проверку,
            получите рекомендации ИИ и выгрузите план в XLSX.
          </div>
        </div>

        <div style={{ marginTop: 20, display: "flex", justifyContent: "flex-end" }}>
          <button className="btn btn-primary" onClick={onNext}>
            Перейти к рекомендациям →
          </button>
        </div>
      </div>
    </div>
  );
}
