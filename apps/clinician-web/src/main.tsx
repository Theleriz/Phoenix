import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type View = "dashboard" | "patient" | "prescription" | "alerts" | "messages";
type Lang = "ru" | "kz" | "en";
type Status = "stable" | "review" | "urgent";
type Trend = "up" | "flat" | "down";

type DemoPatient = {
  id: string;
  display_name: string;
  procedure: string;
  pod: number;
  adherence_pct: number;
  rom_trend: Trend;
  pain: number;
  status: Status;
};

type PrescriptionVersion = { id: number; sets: number; reps: number; targetRom: number; hold: number; tempo: string; savedAt: string };

const fallbackPatients: DemoPatient[] = [
  { id: "demo-ak", display_name: "A.K.", procedure: "Right TKA", pod: 8, adherence_pct: 92, rom_trend: "up", pain: 3, status: "stable" },
  { id: "demo-ms", display_name: "M.S.", procedure: "Left TKA", pod: 15, adherence_pct: 48, rom_trend: "flat", pain: 6, status: "review" },
  { id: "demo-dt", display_name: "D.T.", procedure: "Right TKA", pod: 6, adherence_pct: 70, rom_trend: "down", pain: 8, status: "urgent" },
];

const copy = {
  ru: {
    language: "Язык", brand: "PHOENIX", dashboardTab: "Мои пациенты", alertsTab: "Alerts", messagesTab: "Сообщения",
    dashboardTitle: "Кому сегодня нужно внимание?", dashboardSubtitle: "Очередь отсортирована по приоритету клинического статуса.",
    colPatient: "Пациент", colProcedure: "Операция", colPod: "POD", colAdherence: "Adherence", colRom: "ROM trend", colPain: "Боль", colStatus: "Статус",
    statusStable: "Stable", statusReview: "Review", statusUrgent: "Attention",
    openCard: "Открыть карточку", back: "К очереди",
    patientCardEyebrow: "Карточка пациента", timeline: "Таймлайн", timelineNote1: "Операция → выписка → домашняя реабилитация",
    timelineNote2: "Последняя сессия синхронизирована через synthetic replay", timelineNote3: "Ожидает clinician review",
    editPrescription: "Изменить назначение", reviewAlert: "Открыть в Alerts",
    prescriptionEyebrow: "Prescription builder", prescriptionTitle: "Назначение упражнения",
    sets: "Sets", reps: "Reps", targetRom: "Target ROM, °", hold: "Hold, сек", tempo: "Tempo",
    save: "Сохранить версию", history: "История версий", noHistory: "Изменений пока нет — это будет первая версия.",
    saved: "Версия сохранена в локальном demo-состоянии.",
    alertsEyebrow: "Review queue", alertsTitle: "Требуют внимания врача", noAlerts: "Все пациенты в статусе stable — открытых alert нет.",
    acknowledge: "Acknowledge", dismiss: "Dismiss", acknowledgedTag: "Просмотрено", dismissedTag: "Отклонено",
    messagesEyebrow: "Messaging", messagesTitle: "Сообщение пациенту", choosePatient: "Пациент", messagePlaceholder: "Например: пожалуйста, снизьте темп heel slide и сообщите о боли завтра.",
    send: "Отправить", sentList: "Отправленные сообщения (demo)", noMessages: "Сообщений пока нет.",
    notice: "Это synthetic demo-стенд. Данные не являются измерениями пациента и не используются для клинических решений.",
    demoTag: "Demo",
  },
  kz: {
    language: "Тіл", brand: "PHOENIX", dashboardTab: "Менің пациенттерім", alertsTab: "Alerts", messagesTab: "Хабарламалар",
    dashboardTitle: "Бүгін кімге назар аудару керек?", dashboardSubtitle: "Кезек клиникалық басымдық бойынша сұрыпталған.",
    colPatient: "Пациент", colProcedure: "Операция", colPod: "POD", colAdherence: "Adherence", colRom: "ROM trend", colPain: "Ауырсыну", colStatus: "Статус",
    statusStable: "Stable", statusReview: "Review", statusUrgent: "Attention",
    openCard: "Картаны ашу", back: "Кезекке",
    patientCardEyebrow: "Пациент картасы", timeline: "Таймлайн", timelineNote1: "Операция → шығару → үйдегі оңалту",
    timelineNote2: "Соңғы сессия synthetic replay арқылы синхрондалды", timelineNote3: "Clinician review күтуде",
    editPrescription: "Тағайындауды өзгерту", reviewAlert: "Alerts ішінде ашу",
    prescriptionEyebrow: "Prescription builder", prescriptionTitle: "Жаттығуды тағайындау",
    sets: "Sets", reps: "Reps", targetRom: "Target ROM, °", hold: "Hold, сек", tempo: "Tempo",
    save: "Нұсқаны сақтау", history: "Нұсқалар тарихы", noHistory: "Әзірге өзгеріс жоқ — бұл бірінші нұсқа болады.",
    saved: "Нұсқа local demo-күйінде сақталды.",
    alertsEyebrow: "Review queue", alertsTitle: "Дәрігердің назарын қажет етеді", noAlerts: "Барлық пациенттер stable — ашық alert жоқ.",
    acknowledge: "Acknowledge", dismiss: "Dismiss", acknowledgedTag: "Қаралды", dismissedTag: "Қабылданбады",
    messagesEyebrow: "Messaging", messagesTitle: "Пациентке хабарлама", choosePatient: "Пациент", messagePlaceholder: "Мысалы: heel slide қарқынын азайтып, ертең ауырсыну туралы хабарлаңыз.",
    send: "Жіберу", sentList: "Жіберілген хабарламалар (demo)", noMessages: "Хабарламалар әзірге жоқ.",
    notice: "Бұл synthetic demo-стенд. Деректер пациент өлшемі емес және клиникалық шешімдерде қолданылмайды.",
    demoTag: "Demo",
  },
  en: {
    language: "Language", brand: "PHOENIX", dashboardTab: "My patients", alertsTab: "Alerts", messagesTab: "Messages",
    dashboardTitle: "Who needs attention today?", dashboardSubtitle: "Queue is sorted by clinical priority.",
    colPatient: "Patient", colProcedure: "Procedure", colPod: "POD", colAdherence: "Adherence", colRom: "ROM trend", colPain: "Pain", colStatus: "Status",
    statusStable: "Stable", statusReview: "Review", statusUrgent: "Attention",
    openCard: "Open patient card", back: "Back to queue",
    patientCardEyebrow: "Patient card", timeline: "Timeline", timelineNote1: "Surgery → discharge → home rehab",
    timelineNote2: "Last session synced via synthetic replay", timelineNote3: "Awaiting clinician review",
    editPrescription: "Edit prescription", reviewAlert: "Open in Alerts",
    prescriptionEyebrow: "Prescription builder", prescriptionTitle: "Exercise prescription",
    sets: "Sets", reps: "Reps", targetRom: "Target ROM, °", hold: "Hold, sec", tempo: "Tempo",
    save: "Save version", history: "Version history", noHistory: "No changes yet — this will be the first version.",
    saved: "Version saved to local demo state.",
    alertsEyebrow: "Review queue", alertsTitle: "Need clinician attention", noAlerts: "All patients are stable — no open alerts.",
    acknowledge: "Acknowledge", dismiss: "Dismiss", acknowledgedTag: "Acknowledged", dismissedTag: "Dismissed",
    messagesEyebrow: "Messaging", messagesTitle: "Message to patient", choosePatient: "Patient", messagePlaceholder: "e.g. please slow down heel slide tempo and report pain tomorrow.",
    send: "Send", sentList: "Sent messages (demo)", noMessages: "No messages yet.",
    notice: "This is a synthetic demo stand. Data are not patient measurements and are not used for clinical decisions.",
    demoTag: "Demo",
  },
};

const Icon = ({ name, size = 18 }: { name: string; size?: number }) => {
  const paths: Record<string, string> = {
    home: "M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z",
    users: "M16 11a4 4 0 1 0-4-4M6 20v-1a4 4 0 0 1 4-4h1m3-6a4 4 0 1 1-4 4M14 20v-1a4 4 0 0 0-4-4",
    bell: "M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0",
    message: "M4 5h16v11H8l-4 4z",
    arrow: "m9 18 6-6-6-6",
    check: "m5 12 4 4L19 6",
    close: "M6 6l12 12M18 6 6 18",
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
};

const statusRank: Record<Status, number> = { urgent: 0, review: 1, stable: 2 };

function App() {
  const [lang, setLang] = useState<Lang>("ru");
  const [view, setView] = useState<View>("dashboard");
  const [clinicianName, setClinicianName] = useState("Врач");
  const [organizationName, setOrganizationName] = useState("PHOENIX Clinic");
  const [patients, setPatients] = useState<DemoPatient[]>(fallbackPatients);
  const [selectedId, setSelectedId] = useState<string>(fallbackPatients[0].id);
  const [ackMap, setAckMap] = useState<Record<string, "acknowledged" | "dismissed">>({});
  const [history, setHistory] = useState<Record<string, PrescriptionVersion[]>>({});
  const [form, setForm] = useState({ sets: 3, reps: 10, targetRom: 90, hold: 2, tempo: "slow" });
  const [savedNotice, setSavedNotice] = useState(false);
  const [messageDraft, setMessageDraft] = useState("");
  const [messageTarget, setMessageTarget] = useState<string>(fallbackPatients[0].id);
  const [sentMessages, setSentMessages] = useState<{ to: string; text: string; at: string }[]>([]);
  const t = copy[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    fetch("/api/v1/demo")
      .then((r) => r.json())
      .then((d) => {
        setClinicianName(d.clinician?.display_name ?? "Врач");
        setOrganizationName(d.organization?.name ?? "PHOENIX Clinic");
        if (Array.isArray(d.patients) && d.patients.length > 0) {
          setPatients(d.patients as DemoPatient[]);
          setSelectedId((d.patients as DemoPatient[])[0].id);
          setMessageTarget((d.patients as DemoPatient[])[0].id);
        }
      })
      .catch(() => undefined);
  }, []);

  const sortedPatients = useMemo(
    () => [...patients].sort((a, b) => statusRank[a.status] - statusRank[b.status]),
    [patients]
  );
  const selected = patients.find((p) => p.id === selectedId) ?? patients[0];
  const openAlerts = patients.filter((p) => p.status !== "stable");
  const statusLabel = (s: Status) => (s === "stable" ? t.statusStable : s === "review" ? t.statusReview : t.statusUrgent);

  const openPatient = (id: string) => {
    setSelectedId(id);
    setSavedNotice(false);
    setView("patient");
  };

  const saveVersion = (event: React.FormEvent) => {
    event.preventDefault();
    const version: PrescriptionVersion = { id: Date.now(), ...form, savedAt: new Date().toLocaleTimeString() };
    setHistory((prev) => ({ ...prev, [selected.id]: [version, ...(prev[selected.id] ?? [])] }));
    setSavedNotice(true);
  };

  const setAck = (id: string, state: "acknowledged" | "dismissed") => setAckMap((prev) => ({ ...prev, [id]: state }));

  const sendMessage = (event: React.FormEvent) => {
    event.preventDefault();
    if (!messageDraft.trim()) return;
    setSentMessages((prev) => [{ to: messageTarget, text: messageDraft.trim(), at: new Date().toLocaleTimeString() }, ...prev]);
    setMessageDraft("");
  };

  let content: React.ReactNode;

  if (view === "dashboard") {
    content = (
      <>
        <div className="eyebrow">{organizationName}</div>
        <h2>{t.dashboardTitle}</h2>
        <p className="intro">{t.dashboardSubtitle}</p>
        <table className="queue-table">
          <thead>
            <tr>
              <th>{t.colPatient}</th><th>{t.colProcedure}</th><th>{t.colPod}</th><th>{t.colAdherence}</th><th>{t.colRom}</th><th>{t.colPain}</th><th>{t.colStatus}</th>
            </tr>
          </thead>
          <tbody>
            {sortedPatients.map((p) => (
              <tr className="queue-row" key={p.id} onClick={() => openPatient(p.id)}>
                <td><b>{p.display_name}</b></td>
                <td>{p.procedure}</td>
                <td>{p.pod}</td>
                <td>{p.adherence_pct}%</td>
                <td><span className={`trend ${p.rom_trend}`}>{p.rom_trend === "up" ? "↑" : p.rom_trend === "down" ? "↓" : "→"}</span></td>
                <td>{p.pain}</td>
                <td><span className={`badge ${p.status}`}>{statusLabel(p.status)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </>
    );
  } else if (view === "patient") {
    content = (
      <>
        <button className="text-button" onClick={() => setView("dashboard")}><Icon name="arrow" size={14} />{t.back}</button>
        <div className="eyebrow">{t.patientCardEyebrow}</div>
        <h2>{selected.display_name}</h2>
        <div className="patient-header">
          <span className={`badge ${selected.status}`}>{statusLabel(selected.status)}</span>
          <dl>
            <div><dt>{t.colProcedure}</dt><dd>{selected.procedure}</dd></div>
            <div><dt>{t.colPod}</dt><dd>{selected.pod}</dd></div>
            <div><dt>{t.colAdherence}</dt><dd>{selected.adherence_pct}%</dd></div>
            <div><dt>{t.colRom}</dt><dd className={`trend ${selected.rom_trend}`}>{selected.rom_trend === "up" ? "↑" : selected.rom_trend === "down" ? "↓" : "→"}</dd></div>
            <div><dt>{t.colPain}</dt><dd>{selected.pain}/10</dd></div>
          </dl>
        </div>
        <div className="metric-grid">
          <div className="metric"><span>Correctness</span><strong>—</strong></div>
          <div className="metric"><span>Execution effectiveness</span><strong>—</strong></div>
          <div className="metric"><span>Signal confidence</span><strong>—</strong></div>
        </div>
        <h3>{t.timeline}</h3>
        <ul className="timeline">
          <li>🏥 <b>{t.timelineNote1}</b></li>
          <li>📶 {t.timelineNote2}</li>
          {selected.status !== "stable" && <li>⚠️ {t.timelineNote3}</li>}
        </ul>
        <button className="primary full" onClick={() => setView("prescription")}>{t.editPrescription}</button>
        {selected.status !== "stable" && <button className="secondary full" onClick={() => setView("alerts")}>{t.reviewAlert}</button>}
      </>
    );
  } else if (view === "prescription") {
    const versions = history[selected.id] ?? [];
    content = (
      <>
        <button className="text-button" onClick={() => setView("patient")}><Icon name="arrow" size={14} />{t.back}</button>
        <div className="eyebrow">{t.prescriptionEyebrow} · {selected.display_name}</div>
        <h2>{t.prescriptionTitle}</h2>
        <form className="form-grid" onSubmit={saveVersion}>
          <label>{t.sets}<input type="number" min={1} value={form.sets} onChange={(e) => setForm({ ...form, sets: Number(e.target.value) })} /></label>
          <label>{t.reps}<input type="number" min={1} value={form.reps} onChange={(e) => setForm({ ...form, reps: Number(e.target.value) })} /></label>
          <label>{t.targetRom}<input type="number" min={0} value={form.targetRom} onChange={(e) => setForm({ ...form, targetRom: Number(e.target.value) })} /></label>
          <label>{t.hold}<input type="number" min={0} value={form.hold} onChange={(e) => setForm({ ...form, hold: Number(e.target.value) })} /></label>
          <label>{t.tempo}
            <select value={form.tempo} onChange={(e) => setForm({ ...form, tempo: e.target.value })}>
              <option value="slow">slow</option><option value="moderate">moderate</option><option value="patient-paced">patient-paced</option>
            </select>
          </label>
          <button className="primary" type="submit" style={{ alignSelf: "end" }}>{t.save}</button>
        </form>
        {savedNotice && <div className="replay-notice" role="status"><Icon name="check" size={14} />{t.saved}</div>}
        <h3>{t.history}</h3>
        {versions.length === 0 ? (
          <p className="intro">{t.noHistory}</p>
        ) : (
          <ul className="history-list">
            {versions.map((v) => (
              <li key={v.id}><span>{v.savedAt} · {t.sets} {v.sets} · {t.reps} {v.reps} · {t.targetRom} {v.targetRom}° · {t.hold} {v.hold}s · {v.tempo}</span></li>
            ))}
          </ul>
        )}
      </>
    );
  } else if (view === "alerts") {
    content = (
      <>
        <div className="eyebrow">{t.alertsEyebrow}</div>
        <h2>{t.alertsTitle}</h2>
        {openAlerts.length === 0 ? (
          <div className="empty"><Icon name="bell" size={26} /><p>{t.noAlerts}</p></div>
        ) : (
          openAlerts.map((p) => {
            const state = ackMap[p.id];
            return (
              <div className={`alert-card ${state ? "acknowledged" : ""}`} key={p.id}>
                <div>
                  <span className={`badge ${p.status}`}>{statusLabel(p.status)}</span>
                  <div><b>{p.display_name}</b> · {p.procedure} · POD {p.pod} · Adherence {p.adherence_pct}% · Pain {p.pain}/10</div>
                  {state && <small>{state === "acknowledged" ? t.acknowledgedTag : t.dismissedTag}</small>}
                </div>
                <div className="actions">
                  <button className="ack" onClick={() => setAck(p.id, "acknowledged")}>{t.acknowledge}</button>
                  <button className="dismiss" onClick={() => setAck(p.id, "dismissed")}>{t.dismiss}</button>
                </div>
              </div>
            );
          })
        )}
      </>
    );
  } else {
    content = (
      <>
        <div className="eyebrow">{t.messagesEyebrow}</div>
        <h2>{t.messagesTitle}</h2>
        <form className="compose" onSubmit={sendMessage}>
          <label>{t.choosePatient}
            <select value={messageTarget} onChange={(e) => setMessageTarget(e.target.value)}>
              {patients.map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
            </select>
          </label>
          <textarea placeholder={t.messagePlaceholder} value={messageDraft} onChange={(e) => setMessageDraft(e.target.value)} />
          <button className="primary full" type="submit"><Icon name="message" size={16} />{t.send}</button>
        </form>
        <h3>{t.sentList}</h3>
        {sentMessages.length === 0 ? (
          <p className="intro">{t.noMessages}</p>
        ) : (
          <ul className="message-list">
            {sentMessages.map((m, i) => {
              const target = patients.find((p) => p.id === m.to);
              return <li key={i}><b>{target?.display_name ?? m.to}</b> · {m.at} — {m.text}</li>;
            })}
          </ul>
        )}
      </>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#dashboard" onClick={() => setView("dashboard")}><span>p</span>{t.brand}</a>
        <label className="language"><span>{t.language}</span>
          <select value={lang} onChange={(e) => setLang(e.target.value as Lang)} aria-label={t.language}>
            <option value="ru">РУ</option><option value="kz">ҚЗ</option><option value="en">EN</option>
          </select>
        </label>
      </header>
      <div className="replay-notice"><i /><span>{t.demoTag} · {clinicianName}</span><button aria-label="Information" title={t.notice}>i</button></div>
      <nav className="tabs">
        <button className={view === "dashboard" || view === "patient" || view === "prescription" ? "active" : ""} onClick={() => setView("dashboard")}><Icon name="users" size={14} />{t.dashboardTab}</button>
        <button className={view === "alerts" ? "active" : ""} onClick={() => setView("alerts")}><Icon name="bell" size={14} />{t.alertsTab} {openAlerts.length > 0 && `(${openAlerts.length})`}</button>
        <button className={view === "messages" ? "active" : ""} onClick={() => setView("messages")}><Icon name="message" size={14} />{t.messagesTab}</button>
      </nav>
      <main><section className="content" aria-live="polite">{content}</section></main>
      <p className="footnote">{t.notice}</p>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
