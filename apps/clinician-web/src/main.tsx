import { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import {
  Button,
  Icon,
  LanguageSwitcher,
  ReplayNotice,
  createPhoenixApi,
  createTokenStore,
  useAuth,
  type Alert,
  type CurrentProtocol,
  type ExerciseDefinition,
  type Lang,
  type PatientWithEpisode,
  type ProtocolHistoryEntry,
} from "@phoenix/ui";

type View = "login" | "dashboard" | "patient" | "prescription" | "alerts" | "messages";
type Severity = "green" | "yellow" | "red";

interface DashboardPatient {
  id: string;
  display_name: string;
  pod: number | null;
  episodeId: string | null;
  severity: Severity;
  isDemo: boolean;
  procedure?: string;
  adherence_pct?: number;
  rom_trend?: "up" | "flat" | "down";
  pain?: number;
}

const severityRank: Record<Severity, number> = { red: 0, yellow: 1, green: 2 };

const copy = {
  ru: {
    language: "Язык", brand: "PHOENIX", dashboardTab: "Мои пациенты", alertsTab: "Alerts", messagesTab: "Сообщения",
    dashboardTitle: "Кому сегодня нужно внимание?", dashboardSubtitle: "Очередь отсортирована по приоритету клинического статуса.",
    colPatient: "Пациент", colProcedure: "Операция", colPod: "POD", colAdherence: "Adherence", colRom: "ROM trend", colPain: "Боль", colStatus: "Статус",
    statusStable: "Stable", statusReview: "Review", statusUrgent: "Attention", notAvailable: "Нет данных",
    openCard: "Открыть карточку", back: "К очереди",
    patientCardEyebrow: "Карточка пациента", timeline: "Таймлайн (иллюстративно)", timelineNote1: "Операция → выписка → домашняя реабилитация",
    timelineNote2: "Реальные события сессий пока недоступны в API", timelineNote3: "Ожидает clinician review",
    editPrescription: "Изменить назначение", reviewAlert: "Открыть в Alerts",
    prescriptionEyebrow: "Prescription builder", prescriptionTitle: "Назначение упражнения",
    exerciseLabel: "Упражнение", sets: "Sets", reps: "Reps", targetRom: "Target ROM, °", hold: "Hold, сек", tempo: "Tempo",
    save: "Сохранить версию", history: "История версий", noHistory: "Изменений пока нет — это будет первая версия.",
    saved: "Версия сохранена.", noProtocol: "У этого пациента ещё нет активного протокола.",
    alertsEyebrow: "Review queue", alertsTitle: "Требуют внимания врача", noAlerts: "Открытых alert нет.",
    acknowledge: "Acknowledge", dismiss: "Dismiss", acknowledgedTag: "Просмотрено", dismissedTag: "Отклонено",
    messagesEyebrow: "Messaging", messagesTitle: "Сообщение пациенту", choosePatient: "Пациент", messagePlaceholder: "Например: пожалуйста, снизьте темп heel slide и сообщите о боли завтра.",
    send: "Отправить", sentList: "Черновики (не отправлены)", noMessages: "Сообщений пока нет.", notSent: "Не отправлено — нет messaging backend",
    notice: "Данные, отмеченные как demo, не являются измерениями пациента и не используются для клинических решений.",
    demoTag: "Demo", loginTitle: "Вход", email: "Email", password: "Пароль", organization: "Организация",
    loginSubmit: "Войти", loginError: "Не удалось войти: проверьте данные", logout: "Выйти",
  },
  kz: {
    language: "Тіл", brand: "PHOENIX", dashboardTab: "Менің пациенттерім", alertsTab: "Alerts", messagesTab: "Хабарламалар",
    dashboardTitle: "Бүгін кімге назар аудару керек?", dashboardSubtitle: "Кезек клиникалық басымдық бойынша сұрыпталған.",
    colPatient: "Пациент", colProcedure: "Операция", colPod: "POD", colAdherence: "Adherence", colRom: "ROM trend", colPain: "Ауырсыну", colStatus: "Статус",
    statusStable: "Stable", statusReview: "Review", statusUrgent: "Attention", notAvailable: "Деректер жоқ",
    openCard: "Картаны ашу", back: "Кезекке",
    patientCardEyebrow: "Пациент картасы", timeline: "Таймлайн (иллюстративті)", timelineNote1: "Операция → шығару → үйдегі оңалту",
    timelineNote2: "Нақты сессия оқиғалары әзірге API-де жоқ", timelineNote3: "Clinician review күтуде",
    editPrescription: "Тағайындауды өзгерту", reviewAlert: "Alerts ішінде ашу",
    prescriptionEyebrow: "Prescription builder", prescriptionTitle: "Жаттығуды тағайындау",
    exerciseLabel: "Жаттығу", sets: "Sets", reps: "Reps", targetRom: "Target ROM, °", hold: "Hold, сек", tempo: "Tempo",
    save: "Нұсқаны сақтау", history: "Нұсқалар тарихы", noHistory: "Әзірге өзгеріс жоқ — бұл бірінші нұсқа болады.",
    saved: "Нұсқа сақталды.", noProtocol: "Бұл пациентте әлі белсенді протокол жоқ.",
    alertsEyebrow: "Review queue", alertsTitle: "Дәрігердің назарын қажет етеді", noAlerts: "Ашық alert жоқ.",
    acknowledge: "Acknowledge", dismiss: "Dismiss", acknowledgedTag: "Қаралды", dismissedTag: "Қабылданбады",
    messagesEyebrow: "Messaging", messagesTitle: "Пациентке хабарлама", choosePatient: "Пациент", messagePlaceholder: "Мысалы: heel slide қарқынын азайтып, ертең ауырсыну туралы хабарлаңыз.",
    send: "Жіберу", sentList: "Жобалар (жіберілмеген)", noMessages: "Хабарламалар әзірге жоқ.", notSent: "Жіберілмеді — messaging backend жоқ",
    notice: "Demo деп белгіленген деректер пациент өлшемі емес және клиникалық шешімдерде қолданылмайды.",
    demoTag: "Demo", loginTitle: "Кіру", email: "Email", password: "Құпия сөз", organization: "Ұйым",
    loginSubmit: "Кіру", loginError: "Кіру мүмкін болмады: деректерді тексеріңіз", logout: "Шығу",
  },
  en: {
    language: "Language", brand: "PHOENIX", dashboardTab: "My patients", alertsTab: "Alerts", messagesTab: "Messages",
    dashboardTitle: "Who needs attention today?", dashboardSubtitle: "Queue is sorted by clinical priority.",
    colPatient: "Patient", colProcedure: "Procedure", colPod: "POD", colAdherence: "Adherence", colRom: "ROM trend", colPain: "Pain", colStatus: "Status",
    statusStable: "Stable", statusReview: "Review", statusUrgent: "Attention", notAvailable: "Not available",
    openCard: "Open patient card", back: "Back to queue",
    patientCardEyebrow: "Patient card", timeline: "Timeline (illustrative)", timelineNote1: "Surgery → discharge → home rehab",
    timelineNote2: "Real session events are not available in the API yet", timelineNote3: "Awaiting clinician review",
    editPrescription: "Edit prescription", reviewAlert: "Open in Alerts",
    prescriptionEyebrow: "Prescription builder", prescriptionTitle: "Exercise prescription",
    exerciseLabel: "Exercise", sets: "Sets", reps: "Reps", targetRom: "Target ROM, °", hold: "Hold, sec", tempo: "Tempo",
    save: "Save version", history: "Version history", noHistory: "No changes yet — this will be the first version.",
    saved: "Version saved.", noProtocol: "This patient has no active protocol yet.",
    alertsEyebrow: "Review queue", alertsTitle: "Need clinician attention", noAlerts: "No open alerts.",
    acknowledge: "Acknowledge", dismiss: "Dismiss", acknowledgedTag: "Acknowledged", dismissedTag: "Dismissed",
    messagesEyebrow: "Messaging", messagesTitle: "Message to patient", choosePatient: "Patient", messagePlaceholder: "e.g. please slow down heel slide tempo and report pain tomorrow.",
    send: "Send", sentList: "Drafts (not sent)", noMessages: "No messages yet.", notSent: "Not sent — no messaging backend",
    notice: "Data marked as demo is not a patient measurement and is not used for clinical decisions.",
    demoTag: "Demo", loginTitle: "Sign in", email: "Email", password: "Password", organization: "Organization",
    loginSubmit: "Sign in", loginError: "Could not sign in: check your details", logout: "Log out",
  },
};

const DEMO_FALLBACK: DashboardPatient[] = [
  { id: "demo-ak", display_name: "A.K.", pod: 8, episodeId: null, severity: "green", isDemo: true, procedure: "Right TKA", adherence_pct: 92, rom_trend: "up", pain: 3 },
  { id: "demo-ms", display_name: "M.S.", pod: 15, episodeId: null, severity: "yellow", isDemo: true, procedure: "Left TKA", adherence_pct: 48, rom_trend: "flat", pain: 6 },
  { id: "demo-dt", display_name: "D.T.", pod: 6, episodeId: null, severity: "red", isDemo: true, procedure: "Right TKA", adherence_pct: 70, rom_trend: "down", pain: 8 },
];

const tokenStore = createTokenStore("phoenix.clinician.token");
let handleUnauthorized = () => {};
const api = createPhoenixApi({ tokenStore, onUnauthorized: () => handleUnauthorized() });

function App() {
  const [lang, setLang] = useState<Lang>("ru");
  const [view, setView] = useState<View>("login");
  const t = copy[lang];
  const { identity, loading: authLoading, login, logout } = useAuth(api, tokenStore);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    handleUnauthorized = () => setView("login");
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (identity && view === "login") setView("dashboard");
    if (!identity && view !== "login") setView("login");
  }, [authLoading, identity, view]);

  // --- Login ---------------------------------------------------------------
  const [orgId, setOrgId] = useState("org-demo");
  const [email, setEmail] = useState("clinician@example.test");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState(false);
  useEffect(() => {
    api.demo.get().then((d) => setOrgId(d.organization.id)).catch(() => undefined);
  }, []);
  const submitLogin = (event: React.FormEvent) => {
    event.preventDefault();
    setLoginError(false);
    login(email, password, orgId).catch(() => setLoginError(true));
  };

  // --- Patients + real alerts (dashboard queue) -----------------------------
  const [patients, setPatients] = useState<DashboardPatient[]>(DEMO_FALLBACK);
  const [usingDemoData, setUsingDemoData] = useState(true);
  const [alertsByPatient, setAlertsByPatient] = useState<Record<string, Alert[]>>({});
  const [selectedId, setSelectedId] = useState<string>(DEMO_FALLBACK[0].id);
  const [organizationName, setOrganizationName] = useState("PHOENIX Clinic");
  const [clinicianName, setClinicianName] = useState("Врач");

  useEffect(() => {
    api.demo.get().then((d) => {
      setOrganizationName(d.organization.name);
      setClinicianName(d.clinician.display_name);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!identity) return;
    let cancelled = false;
    api.patients
      .list()
      .then(async (list: PatientWithEpisode[]) => {
        if (cancelled) return;
        setUsingDemoData(false);
        const withSeverity = await Promise.all(
          list.map(async (p): Promise<DashboardPatient> => {
            if (!p.active_episode_id) {
              return { id: p.id, display_name: p.display_name, pod: p.post_op_day, episodeId: null, severity: "green", isDemo: false };
            }
            try {
              const alerts = await api.alerts.list(p.active_episode_id);
              const openAlerts = alerts.filter((a) => a.status === "open");
              setAlertsByPatient((prev) => ({ ...prev, [p.id]: alerts }));
              const severity: Severity = openAlerts.some((a) => a.severity === "red")
                ? "red"
                : openAlerts.some((a) => a.severity === "yellow")
                  ? "yellow"
                  : "green";
              return { id: p.id, display_name: p.display_name, pod: p.post_op_day, episodeId: p.active_episode_id, severity, isDemo: false };
            } catch {
              return { id: p.id, display_name: p.display_name, pod: p.post_op_day, episodeId: p.active_episode_id, severity: "green", isDemo: false };
            }
          })
        );
        if (!cancelled && withSeverity.length > 0) {
          setPatients(withSeverity);
          setSelectedId(withSeverity[0].id);
        }
      })
      .catch(() => {
        if (!cancelled) setUsingDemoData(true);
      });
    return () => {
      cancelled = true;
    };
  }, [identity]);

  const sortedPatients = useMemo(
    () => [...patients].sort((a, b) => severityRank[a.severity] - severityRank[b.severity]),
    [patients]
  );
  const selected = patients.find((p) => p.id === selectedId) ?? patients[0];
  const statusLabel = (s: Severity) => (s === "green" ? t.statusStable : s === "yellow" ? t.statusReview : t.statusUrgent);
  const openPatient = (id: string) => {
    setSelectedId(id);
    setView("patient");
  };

  // --- Protocol / prescription ----------------------------------------------
  const [exerciseDefs, setExerciseDefs] = useState<ExerciseDefinition[]>([]);
  const [currentProtocol, setCurrentProtocol] = useState<CurrentProtocol | null>(null);
  const [protocolHistory, setProtocolHistory] = useState<ProtocolHistoryEntry[]>([]);
  const [form, setForm] = useState({ exerciseId: "", sets: 3, reps: 10, targetRom: 90, hold: 2, tempo: "slow" });
  const [savedNotice, setSavedNotice] = useState(false);

  useEffect(() => {
    if (view !== "prescription" || !selected?.episodeId) return;
    api.protocol.listExerciseDefinitions().then(setExerciseDefs).catch(() => setExerciseDefs([]));
    api.protocol
      .current(selected.episodeId)
      .then((protocol) => {
        setCurrentProtocol(protocol);
        const exercise = protocol.exercises[0];
        if (exercise) {
          setForm({
            exerciseId: exercise.id,
            sets: exercise.prescription.sets ?? 3,
            reps: exercise.prescription.repetitions ?? 10,
            targetRom: exercise.prescription.target_rom_degrees ?? 90,
            hold: exercise.prescription.hold_seconds ?? 2,
            tempo: exercise.prescription.tempo ?? "slow",
          });
        }
      })
      .catch(() => setCurrentProtocol(null));
    api.protocol.history(selected.episodeId).then(setProtocolHistory).catch(() => setProtocolHistory([]));
  }, [view, selected]);

  const saveVersion = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected?.episodeId || !currentProtocol) return;
    try {
      await api.protocol.createVersion(selected.episodeId, {
        protocol_template_id: currentProtocol.template.id,
        exercise_definition_id: form.exerciseId || currentProtocol.exercises[0]?.id,
        prescription: {
          sets: form.sets,
          repetitions: form.reps,
          target_rom_degrees: form.targetRom,
          hold_seconds: form.hold,
          tempo: form.tempo,
          restriction_sources: [],
        },
      });
      setSavedNotice(true);
      const history = await api.protocol.history(selected.episodeId);
      setProtocolHistory(history);
    } catch {
      setSavedNotice(false);
    }
  };

  // --- Alerts ----------------------------------------------------------------
  const openAlerts = useMemo(
    () =>
      Object.entries(alertsByPatient).flatMap(([patientId, alerts]) => {
        const patient = patients.find((p) => p.id === patientId);
        return alerts.map((alert) => ({ alert, patient }));
      }),
    [alertsByPatient, patients]
  );

  const actOnAlert = async (alertId: string, actionType: "acknowledged" | "dismissed") => {
    try {
      await api.alerts.act(alertId, { action_type: actionType });
      setAlertsByPatient((prev) => {
        const next = { ...prev };
        for (const patientId of Object.keys(next)) {
          next[patientId] = next[patientId].map((a) => (a.id === alertId ? { ...a, status: actionType } : a));
        }
        return next;
      });
    } catch {
      /* leave state unchanged; the action simply did not persist */
    }
  };

  // --- Messages (no backend) --------------------------------------------------
  const [messageDraft, setMessageDraft] = useState("");
  const [messageTarget, setMessageTarget] = useState<string>(DEMO_FALLBACK[0].id);
  const [drafts, setDrafts] = useState<{ to: string; text: string; at: string }[]>([]);
  const composeMessage = (event: React.FormEvent) => {
    event.preventDefault();
    if (!messageDraft.trim()) return;
    setDrafts((prev) => [{ to: messageTarget, text: messageDraft.trim(), at: new Date().toLocaleTimeString() }, ...prev]);
    setMessageDraft("");
  };

  let content: React.ReactNode;

  if (view === "login") {
    content = (
      <form className="login-form" onSubmit={submitLogin}>
        <h2>{t.loginTitle}</h2>
        <label>
          {t.organization}
          <input value={orgId} onChange={(e) => setOrgId(e.target.value)} />
        </label>
        <label>
          {t.email}
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          {t.password}
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {loginError && (
          <p role="alert" className="login-error">
            {t.loginError}
          </p>
        )}
        <Button type="submit" full>
          {t.loginSubmit}
        </Button>
      </form>
    );
  } else if (view === "dashboard") {
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
                <td><b>{p.display_name}</b>{p.isDemo && <small> · {t.demoTag}</small>}</td>
                <td>{p.procedure ?? t.notAvailable}</td>
                <td>{p.pod ?? "—"}</td>
                <td>{p.adherence_pct !== undefined ? `${p.adherence_pct}%` : t.notAvailable}</td>
                <td>{p.rom_trend ? <span className={`trend ${p.rom_trend}`}>{p.rom_trend === "up" ? "↑" : p.rom_trend === "down" ? "↓" : "→"}</span> : t.notAvailable}</td>
                <td>{p.pain !== undefined ? p.pain : t.notAvailable}</td>
                <td><span className={`badge ${p.severity === "green" ? "stable" : p.severity === "yellow" ? "review" : "urgent"}`}>{statusLabel(p.severity)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </>
    );
  } else if (view === "patient" && selected) {
    content = (
      <>
        <button className="text-button" onClick={() => setView("dashboard")}><Icon name="arrow" size={14} />{t.back}</button>
        <div className="eyebrow">{t.patientCardEyebrow}</div>
        <h2>{selected.display_name}</h2>
        <div className="patient-header">
          <span className={`badge ${selected.severity === "green" ? "stable" : selected.severity === "yellow" ? "review" : "urgent"}`}>{statusLabel(selected.severity)}</span>
          <dl>
            <div><dt>{t.colProcedure}</dt><dd>{selected.procedure ?? t.notAvailable}</dd></div>
            <div><dt>{t.colPod}</dt><dd>{selected.pod ?? "—"}</dd></div>
            <div><dt>{t.colAdherence}</dt><dd>{selected.adherence_pct !== undefined ? `${selected.adherence_pct}%` : t.notAvailable}</dd></div>
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
          {selected.severity !== "green" && <li>⚠️ {t.timelineNote3}</li>}
        </ul>
        <Button full onClick={() => setView("prescription")}>{t.editPrescription}</Button>
        {selected.severity !== "green" && <Button variant="secondary" full onClick={() => setView("alerts")}>{t.reviewAlert}</Button>}
      </>
    );
  } else if (view === "prescription" && selected) {
    content = (
      <>
        <button className="text-button" onClick={() => setView("patient")}><Icon name="arrow" size={14} />{t.back}</button>
        <div className="eyebrow">{t.prescriptionEyebrow} · {selected.display_name}</div>
        <h2>{t.prescriptionTitle}</h2>
        {!selected.episodeId || !currentProtocol ? (
          <p className="intro">{t.noProtocol}</p>
        ) : (
          <>
            <form className="form-grid" onSubmit={saveVersion}>
              <label>{t.exerciseLabel}
                <select value={form.exerciseId} onChange={(e) => setForm({ ...form, exerciseId: e.target.value })}>
                  {exerciseDefs.map((def) => <option key={def.id} value={def.id}>{def.name}</option>)}
                </select>
              </label>
              <label>{t.sets}<input type="number" min={1} value={form.sets} onChange={(e) => setForm({ ...form, sets: Number(e.target.value) })} /></label>
              <label>{t.reps}<input type="number" min={1} value={form.reps} onChange={(e) => setForm({ ...form, reps: Number(e.target.value) })} /></label>
              <label>{t.targetRom}<input type="number" min={0} value={form.targetRom} onChange={(e) => setForm({ ...form, targetRom: Number(e.target.value) })} /></label>
              <label>{t.hold}<input type="number" min={0} value={form.hold} onChange={(e) => setForm({ ...form, hold: Number(e.target.value) })} /></label>
              <label>{t.tempo}
                <select value={form.tempo} onChange={(e) => setForm({ ...form, tempo: e.target.value })}>
                  <option value="slow">slow</option><option value="moderate">moderate</option><option value="patient-paced">patient-paced</option>
                </select>
              </label>
              <Button type="submit" style={{ alignSelf: "end" }}>{t.save}</Button>
            </form>
            {savedNotice && <div className="replay-notice" role="status"><Icon name="check" size={14} />{t.saved}</div>}
            <h3>{t.history}</h3>
            {protocolHistory.length === 0 ? (
              <p className="intro">{t.noHistory}</p>
            ) : (
              <ul className="history-list">
                {protocolHistory.map((v) => (
                  <li key={v.assignment_id}>
                    <span>{new Date(v.created_at).toLocaleString()} · v{v.version} · {v.exercise.name} · {t.sets} {v.prescription.sets ?? "—"} · {t.reps} {v.prescription.repetitions ?? "—"} · {t.targetRom} {v.prescription.target_rom_degrees ?? "—"}°</span>
                  </li>
                ))}
              </ul>
            )}
          </>
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
          openAlerts.map(({ alert, patient }) => (
            <div className={`alert-card ${alert.status !== "open" ? "acknowledged" : ""}`} key={alert.id}>
              <div>
                <span className={`badge ${alert.severity === "red" ? "urgent" : "review"}`}>{alert.severity.toUpperCase()}</span>
                <div><b>{patient?.display_name ?? "—"}</b> · {new Date(alert.created_at).toLocaleString()}</div>
                {alert.status !== "open" && <small>{alert.status === "acknowledged" ? t.acknowledgedTag : t.dismissedTag}</small>}
              </div>
              {alert.status === "open" && (
                <div className="actions">
                  <button className="ack" onClick={() => actOnAlert(alert.id, "acknowledged")}>{t.acknowledge}</button>
                  <button className="dismiss" onClick={() => actOnAlert(alert.id, "dismissed")}>{t.dismiss}</button>
                </div>
              )}
            </div>
          ))
        )}
      </>
    );
  } else {
    content = (
      <>
        <div className="eyebrow">{t.messagesEyebrow}</div>
        <h2>{t.messagesTitle}</h2>
        <p className="demo-note">{t.notSent}</p>
        <form className="compose" onSubmit={composeMessage}>
          <label>{t.choosePatient}
            <select value={messageTarget} onChange={(e) => setMessageTarget(e.target.value)}>
              {patients.map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
            </select>
          </label>
          <textarea placeholder={t.messagePlaceholder} value={messageDraft} onChange={(e) => setMessageDraft(e.target.value)} />
          <Button full type="submit"><Icon name="message" size={16} />{t.send}</Button>
        </form>
        <h3>{t.sentList}</h3>
        {drafts.length === 0 ? (
          <p className="intro">{t.noMessages}</p>
        ) : (
          <ul className="message-list">
            {drafts.map((m, i) => {
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
        <a className="brand" href="#dashboard" onClick={() => setView(identity ? "dashboard" : "login")}><span>p</span>{t.brand}</a>
        <div className="topbar-actions">
          <LanguageSwitcher lang={lang} onChange={setLang} />
          {identity && <button className="text-button" onClick={logout}>{t.logout}</button>}
        </div>
      </header>
      {view !== "login" && <ReplayNotice label={`${t.demoTag} · ${clinicianName}`} detail={t.notice} />}
      {view !== "login" && (
        <nav className="tabs">
          <button className={view === "dashboard" || view === "patient" || view === "prescription" ? "active" : ""} onClick={() => setView("dashboard")}><Icon name="users" size={14} />{t.dashboardTab}</button>
          <button className={view === "alerts" ? "active" : ""} onClick={() => setView("alerts")}><Icon name="bell" size={14} />{t.alertsTab} {openAlerts.filter((a) => a.alert.status === "open").length > 0 && `(${openAlerts.filter((a) => a.alert.status === "open").length})`}</button>
          <button className={view === "messages" ? "active" : ""} onClick={() => setView("messages")}><Icon name="message" size={14} />{t.messagesTab}</button>
        </nav>
      )}
      <main><section className="content" aria-live="polite">{content}</section></main>
      {view !== "login" && <p className="footnote">{t.notice}</p>}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
