import { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import {
  Button,
  Icon,
  LanguageSwitcher,
  MetricGrid,
  ReplayNotice,
  connectWt901Sensor,
  createPhoenixApi,
  createTokenStore,
  ingestImuPacket,
  useAuth,
  useGatewayStream,
  type BleConnectionStatus,
  type CurrentProtocol,
  type GatewayIMUPacket,
  type Lang,
  type ParsedWt901Frame,
  type PatientWithEpisode,
  type SensorConnection,
} from "@phoenix/ui";

type View = "login" | "plan" | "setup" | "calibration" | "exercise" | "pause" | "result" | "check" | "progress" | "messages";
type SensorRole = "thigh" | "shank" | "foot";
type SensorUiStatus = "idle" | BleConnectionStatus;

const copy = {
  ru: { language: "Язык", greeting: "Добрый день", today: "План на сегодня", start: "Начать занятие", continue: "Продолжить", next: "Далее", calibrate: "Начать калибровку", pause: "Пауза", resume: "Продолжить занятие", finish: "Завершить", setup: "Подключите датчики", calibration: "Калибровка", exercise: "Текущее упражнение", result: "Занятие завершено", check: "Как вы себя чувствуете?", progress: "Прогресс", messages: "Сообщения", save: "Сохранить ответы", saved: "Спасибо, ответы сохранены.", plan: "План", synthetic: "Режим демонстрации · synthetic replay", notice: "Это synthetic replay для разработки. Данные не являются измерениями пациента и не используются для score, feedback или клинических решений.", notCalculated: "Не рассчитано", waiting: "Ожидает", connected: "Готов", ready: "Датчики готовы", placement: "Разместите датчики как показано на схеме", stayStill: "Пожалуйста, сохраняйте неподвижность", calibrationDone: "Калибровка завершена", cue: "Выполняйте движение в комфортном темпе", before: "Боль до занятия", after: "Боль после занятия", difficulty: "Насколько сложным было занятие?", symptoms: "Новые симптомы", no: "Нет", yes: "Да", easy: "Легко", normal: "Нормально", hard: "Сложно", exerciseName: "Скольжение пяткой", duration: "~ 8 минут", reps: "10 повторений", pod: "день после операции", completed: "Выполнено занятий", adherence: "Выполнение плана", emptyMessages: "Новых сообщений пока нет", back: "К плану", stop: "Завершить занятие?", stopNote: "Вы сможете сообщить о самочувствии на следующем шаге.", confirmStop: "Да, завершить", cancel: "Вернуться к занятию", loginTitle: "Вход", email: "Email", password: "Пароль", organization: "Организация", loginSubmit: "Войти", loginError: "Не удалось войти: проверьте данные", logout: "Выйти", demoDataLabel: "Демо-данные · нет привязанного пациента", reconnecting: "Переподключение — статус мог устареть", signalConfidence: "Достоверность сигнала", registerSensor: "Подключить", sensorRegistered: "Зарегистрирован", safetyReasons: "Причины", bleRequesting: "Выбор устройства…", bleConnecting: "Подключение…", bleConnected: "Подключено", bleDisconnected: "Отключено", bleError: "Ошибка подключения", bleUnsupported: "Bluetooth недоступен в этом браузере (нужен Chrome/Edge, HTTPS или localhost)", bleRetry: "Повторить", goBack: "Назад", resetSensors: "Сбросить конфигурацию датчиков", savedSensorLabel: "Сохранённый датчик", noSavedSensor: "Датчик ещё не сохранён", sensorsRemembered: "Адреса датчиков сохранены на этом устройстве — не нужно каждый раз вспоминать, где какой", targetReps: "Целевое количество повторений", repsUnit: "повторений", videoExample: "Видео-пример", videoComingSoon: "Видео-пример скоро появится", readyToStart: "Всё готово к упражнению", repsRemaining: "Осталось повторений", repDone: "Повторение выполнено", exerciseDoneHint: "Все повторения выполнены", autoReps: "Повторения считаются автоматически по датчикам", manualRepFallback: "Отметить повторение вручную", skipCalibrationDev: "Пропустить калибровку (dev)" },
  kz: { language: "Тіл", greeting: "Қайырлы күн", today: "Бүгінгі жоспар", start: "Жаттығуды бастау", continue: "Жалғастыру", next: "Келесі", calibrate: "Калибрлеуді бастау", pause: "Кідірту", resume: "Жаттығуды жалғастыру", finish: "Аяқтау", setup: "Датчиктерді қосыңыз", calibration: "Калибрлеу", exercise: "Ағымдағы жаттығу", result: "Жаттығу аяқталды", check: "Өзіңізді қалай сезінесіз?", progress: "Прогресс", messages: "Хабарламалар", save: "Жауаптарды сақтау", saved: "Рақмет, жауаптар сақталды.", plan: "Жоспар", synthetic: "Демо режимі · synthetic replay", notice: "Бұл әзірлеуге арналған synthetic replay. Деректер пациент өлшемі емес және score, alert не клиникалық шешімдерде қолданылмайды.", notCalculated: "Есептелмеді", waiting: "Күтуде", connected: "Дайын", ready: "Датчиктер дайын", placement: "Датчиктерді сызбада көрсетілгендей орналастырыңыз", stayStill: "Қозғалмай тұрыңыз", calibrationDone: "Калибрлеу аяқталды", cue: "Қозғалысты ыңғайлы қарқынмен орындаңыз", before: "Жаттығуға дейінгі ауырсыну", after: "Жаттығудан кейінгі ауырсыну", difficulty: "Жаттығу қаншалықты қиын болды?", symptoms: "Жаңа симптомдар", no: "Жоқ", yes: "Иә", easy: "Оңай", normal: "Қалыпты", hard: "Қиын", exerciseName: "Өкшені сырғыту", duration: "~ 8 минут", reps: "10 қайталау", pod: "операциядан кейінгі күн", completed: "Орындалған жаттығулар", adherence: "Жоспарды орындау", emptyMessages: "Әзірге жаңа хабарламалар жоқ", back: "Жоспарға", stop: "Жаттығуды аяқтау керек пе?", stopNote: "Келесі қадамда өзіңізді қалай сезінетініңізді хабарлай аласыз.", confirmStop: "Иә, аяқтау", cancel: "Жаттығуға оралу", loginTitle: "Кіру", email: "Email", password: "Құпия сөз", organization: "Ұйым", loginSubmit: "Кіру", loginError: "Кіру мүмкін болмады: деректерді тексеріңіз", logout: "Шығу", demoDataLabel: "Демо деректер · пациент байланыстырылмаған", reconnecting: "Қайта қосылуда — күй ескіруі мүмкін", signalConfidence: "Сигнал сенімділігі", registerSensor: "Қосу", sensorRegistered: "Тіркелген", safetyReasons: "Себептер", bleRequesting: "Құрылғы таңдау…", bleConnecting: "Қосылуда…", bleConnected: "Қосылды", bleDisconnected: "Ажыратылды", bleError: "Қосылу қатесі", bleUnsupported: "Bluetooth бұл браузерде қолжетімсіз (Chrome/Edge, HTTPS немесе localhost қажет)", bleRetry: "Қайталау", goBack: "Артқа", resetSensors: "Датчиктер конфигурациясын тастау", savedSensorLabel: "Сақталған датчик", noSavedSensor: "Датчик әлі сақталмаған", sensorsRemembered: "Датчик адрестері осы құрылғыда сақталды — қайсысы қайда екенін еске сақтаудың қажеті жоқ", targetReps: "Мақсатты қайталау саны", repsUnit: "қайталау", videoExample: "Бейне мысал", videoComingSoon: "Бейне мысал жақында қосылады", readyToStart: "Жаттығуға дайын", repsRemaining: "Қалған қайталау", repDone: "Қайталау орындалды", exerciseDoneHint: "Барлық қайталау орындалды", autoReps: "Қайталаулар датчиктер бойынша автоматты түрде саналады", manualRepFallback: "Қайталауды қолмен белгілеу", skipCalibrationDev: "Калибрлеуді өткізіп жіберу (dev)" },
  en: { language: "Language", greeting: "Good day", today: "Today’s plan", start: "Start session", continue: "Continue", next: "Next", calibrate: "Start calibration", pause: "Pause", resume: "Resume session", finish: "Finish", setup: "Connect your sensors", calibration: "Calibration", exercise: "Current exercise", result: "Session complete", check: "How are you feeling?", progress: "Progress", messages: "Messages", save: "Save answers", saved: "Thank you, responses are saved.", plan: "Plan", synthetic: "Demo mode · synthetic replay", notice: "This is a synthetic replay for development. Data are not patient measurements and are not used for scoring, alerts, or clinical decisions.", notCalculated: "Not calculated", waiting: "Waiting", connected: "Ready", ready: "Sensors ready", placement: "Place the sensors as shown in the guide", stayStill: "Please stay still", calibrationDone: "Calibration complete", cue: "Move at a comfortable pace", before: "Pain before session", after: "Pain after session", difficulty: "How difficult was the session?", symptoms: "New symptoms", no: "No", yes: "Yes", easy: "Easy", normal: "Normal", hard: "Hard", exerciseName: "Heel slide", duration: "~ 8 min", reps: "10 repetitions", pod: "day after surgery", completed: "Sessions completed", adherence: "Plan adherence", emptyMessages: "No new messages yet", back: "Back to plan", stop: "Finish this session?", stopNote: "You can tell us how you feel in the next step.", confirmStop: "Yes, finish", cancel: "Back to exercise", loginTitle: "Sign in", email: "Email", password: "Password", organization: "Organization", loginSubmit: "Sign in", loginError: "Could not sign in: check your details", logout: "Log out", demoDataLabel: "Demo data · no linked patient", reconnecting: "Reconnecting — status may be out of date", signalConfidence: "Signal confidence", registerSensor: "Connect", sensorRegistered: "Registered", safetyReasons: "Reasons", bleRequesting: "Choosing device…", bleConnecting: "Connecting…", bleConnected: "Connected", bleDisconnected: "Disconnected", bleError: "Connection error", bleUnsupported: "Bluetooth is unavailable in this browser (needs Chrome/Edge, HTTPS or localhost)", bleRetry: "Retry", goBack: "Back", resetSensors: "Reset sensor configuration", savedSensorLabel: "Saved sensor", noSavedSensor: "No sensor saved yet", sensorsRemembered: "Sensor addresses are stored on this device — no need to remember which one goes where", targetReps: "Target repetitions", repsUnit: "repetitions", videoExample: "Video example", videoComingSoon: "Video example coming soon", readyToStart: "Ready to start", repsRemaining: "Repetitions left", repDone: "Repetition done", exerciseDoneHint: "All repetitions done", autoReps: "Repetitions are counted automatically from the sensors", manualRepFallback: "Mark repetition manually", skipCalibrationDev: "Skip calibration (dev)" },
};

const SENSOR_ROLES: { role: "thigh" | "shank" | "foot"; label: string }[] = [
  { role: "thigh", label: "Upper leg" },
  { role: "shank", label: "Lower leg" },
  { role: "foot", label: "Foot" },
];

const tokenStore = createTokenStore("phoenix.patient.token");
let handleUnauthorized = () => {};
const api = createPhoenixApi({ tokenStore, onUnauthorized: () => handleUnauthorized() });
const GATEWAY_TOKEN = import.meta.env.VITE_PHOENIX_GATEWAY_TOKEN ?? null;

// --- Client-side sensor registry -----------------------------------------
// Web Bluetooth never exposes the physical MAC, but it does hand back a
// stable per-origin device id plus the advertised name (the label printed on
// WitMotion sensors). We persist {id, name} per body location in
// localStorage so the patient does not have to remember which physical
// sensor is the "thigh" one every session -- the setup screen can show the
// remembered device and the pairing picker pre-selects it by name.
const SENSOR_STORE_KEY = "phoenix.patient.sensors";
type SavedSensor = { deviceId: string; deviceName: string | null; savedAt: string };
type SavedSensorMap = Partial<Record<SensorRole, SavedSensor>>;

function loadSavedSensors(): SavedSensorMap {
  try {
    const raw = window.localStorage.getItem(SENSOR_STORE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as SavedSensorMap;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function persistSavedSensors(map: SavedSensorMap): void {
  try {
    window.localStorage.setItem(SENSOR_STORE_KEY, JSON.stringify(map));
  } catch {
    // Private-mode / storage-disabled: the app still works, it just won't
    // remember sensors between sessions.
  }
}

function clearSavedSensors(): void {
  try {
    window.localStorage.removeItem(SENSOR_STORE_KEY);
  } catch {
    // ignore -- nothing to clear if storage is unavailable
  }
}

function App() {
  const [lang, setLang] = useState<Lang>("ru");
  const [view, setView] = useState<View>("login");
  const t = copy[lang];
  const { identity, loading: authLoading, login, logout } = useAuth(api, tokenStore);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  // Navigation history so every screen past the plan has a working "back".
  const historyRef = useRef<View[]>([]);
  const viewRef = useRef<View>(view);
  useEffect(() => {
    viewRef.current = view;
  }, [view]);

  const go = useCallback((next: View) => {
    setStopOpen(false);
    // "login" and "plan" are roots -- nothing meaningful to go back to.
    if (next === "login" || next === "plan") {
      historyRef.current = [];
    } else if (viewRef.current !== next) {
      historyRef.current = [...historyRef.current, viewRef.current];
    }
    setView(next);
  }, []);

  const back = useCallback(() => {
    setStopOpen(false);
    const prev = historyRef.current.pop();
    setView(prev ?? "plan");
  }, []);

  useEffect(() => {
    handleUnauthorized = () => go("login");
  }, [go]);

  useEffect(() => {
    if (authLoading) return;
    if (identity && view === "login") go("plan");
    if (!identity && view !== "login") go("login");
  }, [authLoading, identity, view, go]);

  // --- Login screen -------------------------------------------------------
  const [orgId, setOrgId] = useState("org-demo");
  const [email, setEmail] = useState("patient@example.test");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState(false);
  useEffect(() => {
    api.demo
      .get()
      .then((d) => setOrgId(d.organization.id))
      .catch(() => undefined);
  }, []);
  const submitLogin = (event: React.FormEvent) => {
    event.preventDefault();
    setLoginError(false);
    login(email, password, orgId).catch(() => setLoginError(true));
  };

  // --- Patient / protocol (real data, demo fallback) -----------------------
  const [patient, setPatient] = useState<PatientWithEpisode | null>(null);
  const [usingDemoData, setUsingDemoData] = useState(false);
  const [demoName, setDemoName] = useState("Пациент");
  const [demoPod, setDemoPod] = useState("—");
  const [protocol, setProtocol] = useState<CurrentProtocol | null>(null);

  useEffect(() => {
    if (!identity) return;
    let cancelled = false;
    api.patients
      .me()
      .then((p) => {
        if (!cancelled) {
          setPatient(p);
          setUsingDemoData(false);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setUsingDemoData(true);
        api.demo
          .get()
          .then((d) => {
            if (cancelled) return;
            setDemoName(d.patient.display_name);
            setDemoPod(String(d.patient.post_op_day));
          })
          .catch(() => undefined);
      });
    return () => {
      cancelled = true;
    };
  }, [identity]);

  useEffect(() => {
    if (!patient?.active_episode_id) {
      setProtocol(null);
      return;
    }
    let cancelled = false;
    api.protocol
      .current(patient.active_episode_id)
      .then((p) => !cancelled && setProtocol(p))
      .catch(() => !cancelled && setProtocol(null));
    return () => {
      cancelled = true;
    };
  }, [patient]);

  const currentExercise = protocol?.exercises[0];
  const exerciseName = currentExercise?.name ?? t.exerciseName;
  const repsLabel = currentExercise?.prescription.repetitions
    ? `${currentExercise.prescription.repetitions} reps`
    : t.reps;
  const targetReps = currentExercise?.prescription.repetitions ?? 10;

  // --- Real session lifecycle (gateway) ------------------------------------
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const canUseRealSession = Boolean(
    !usingDemoData && patient?.active_episode_id && currentExercise?.prescription_id && GATEWAY_TOKEN
  );
  const bleSupported = typeof navigator !== "undefined" && "bluetooth" in navigator;

  const startRealSession = useCallback(async () => {
    if (!patient?.active_episode_id || !currentExercise) return;
    try {
      // "hardware": this session backs real Web Bluetooth sensor packets, not
      // the Python synthetic-replay gateway (which posts its own "synthetic"
      // sessions independently).
      const { session_id, exercise_attempt_id } = await api.gateway.startExerciseAttempt(
        patient.active_episode_id,
        { source_kind: "hardware", exercise_prescription_id: currentExercise.prescription_id }
      );
      setSessionId(session_id);
      setAttemptId(exercise_attempt_id);
    } catch {
      setSessionId(null);
      setAttemptId(null);
    }
  }, [patient, currentExercise]);

  // Dev mode: open patient-web with ?hw=1 to stream real BLE sensors even
  // without a linked-patient login. The API opens a hardware gateway session
  // bound to the demo episode (needs PHOENIX_DEV_HARDWARE_SESSION=1).
  const hwDev =
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).get("hw") === "1";

  const startDevHardwareSession = useCallback(async () => {
    try {
      const { session_id, exercise_attempt_id } = await api.gateway.startDevHardwareSession();
      setSessionId(session_id);
      setAttemptId(exercise_attempt_id);
    } catch {
      setSessionId(null);
      setAttemptId(null);
    }
  }, []);

  // Deliberately NOT created on entering Setup: signal_quality evaluates the
  // *earliest* events of the session as "the" static calibration window
  // (services/api/app/signal_quality.py). Sensors are paired one at a time
  // over Web Bluetooth (each requestDevice() is a separate native picker),
  // so if the session existed while that pairing was happening, its first
  // packets would span the staggered connect sequence, not an actual
  // simultaneous stay-still hold -- guaranteeing
  // static_calibration_motion_detected / sensor_synchronization_out_of_range
  // forever for that session. Opening it only once the patient leaves Setup
  // (all three presumably already connected) keeps the window meaningful.

  // --- Real sensor connections (Web Bluetooth) ------------------------------
  const [sensorStates, setSensorStates] = useState<Record<SensorRole, SensorUiStatus>>({
    thigh: "idle",
    shank: "idle",
    foot: "idle",
  });
  // Devices the patient paired on a previous visit, kept in localStorage so
  // they don't have to re-identify which physical sensor is which every time.
  const [savedSensors, setSavedSensors] = useState<SavedSensorMap>(() => loadSavedSensors());
  const connectionsRef = useRef<Partial<Record<SensorRole, SensorConnection>>>({});
  const sequenceRef = useRef<Partial<Record<SensorRole, number>>>({});

  const resetSensorConfig = useCallback(() => {
    for (const connection of Object.values(connectionsRef.current)) connection?.disconnect();
    connectionsRef.current = {};
    sequenceRef.current = {};
    clearSavedSensors();
    setSavedSensors({});
    setSensorStates({ thigh: "idle", shank: "idle", foot: "idle" });
  }, []);

  const sendFrame = useCallback((role: SensorRole, frame: ParsedWt901Frame) => {
    if (!sessionIdRef.current || !GATEWAY_TOKEN) return;
    const sequence = sequenceRef.current[role] ?? 0;
    sequenceRef.current[role] = sequence + 1;
    const packet: GatewayIMUPacket = {
      session_id: sessionIdRef.current,
      device_id: `ble-${role}`,
      sensor_role: role,
      timestamp_device: null,
      timestamp_gateway: new Date().toISOString(),
      sequence_number: sequence,
      ax: frame.accelerometerRaw[0],
      ay: frame.accelerometerRaw[1],
      az: frame.accelerometerRaw[2],
      gx: frame.gyroscopeRaw[0],
      gy: frame.gyroscopeRaw[1],
      gz: frame.gyroscopeRaw[2],
      orientation_euler_degrees: frame.eulerDegrees,
      battery: null,
      origin: "hardware",
      validation_status: "unverified_checksum",
      adapter_version: "phoenix-patient-web-ble-0.1.0",
    };
    // Fire-and-forget: the live signal-quality reflection in the UI comes
    // back through the WebSocket subscription below, not this response.
    ingestImuPacket("", GATEWAY_TOKEN, packet).catch(() => undefined);
  }, []);

  const connectSensor = useCallback(
    async (role: SensorRole) => {
      setSensorStates((prev) => ({ ...prev, [role]: "requesting" }));
      try {
        // A fixed per-role identifier (not the BLE device's opaque id) --
        // one physical sensor per role/org at a time is enough for this
        // scaffold and avoids a register-vs-first-packet race.
        await api.gateway.registerSensorDevice({ device_identifier: `ble-${role}`, model: "WT901BLE68" });
        const connection = await connectWt901Sensor({
          onStatusChange: (status) => setSensorStates((prev) => ({ ...prev, [role]: status })),
          onFrame: (frame) => sendFrame(role, frame),
          onError: () => setSensorStates((prev) => ({ ...prev, [role]: "error" })),
        });
        connectionsRef.current[role] = connection;
        // Remember this physical sensor for this body location on this device.
        setSavedSensors((prev) => {
          const next: SavedSensorMap = {
            ...prev,
            [role]: {
              deviceId: connection.deviceId,
              deviceName: connection.deviceName,
              savedAt: new Date().toISOString(),
            },
          };
          persistSavedSensors(next);
          return next;
        });
      } catch {
        setSensorStates((prev) => ({ ...prev, [role]: "error" }));
      }
    },
    [sendFrame]
  );

  // Disconnect real sensors only when the whole app unmounts, not on every
  // view change -- requestDevice() opens a native picker each time and
  // should not be repeated while the patient just navigates between screens.
  useEffect(() => {
    return () => {
      for (const connection of Object.values(connectionsRef.current)) connection?.disconnect();
    };
  }, []);

  // --- Calibration: real signal_quality if a live stream arrives, else the
  // existing synthetic timer (clearly labeled) as a fallback. -----------------
  const [calibration, setCalibration] = useState(0);
  const [calibrationReasons, setCalibrationReasons] = useState<string[]>([]);
  const [liveEventSeen, setLiveEventSeen] = useState(false);
  const [saved, setSaved] = useState(false);
  const [stopOpen, setStopOpen] = useState(false);
  const [painBefore, setPainBefore] = useState(0);
  const [painAfter, setPainAfter] = useState(0);
  const [safetyNote, setSafetyNote] = useState<string | null>(null);
  const [resultSignal, setResultSignal] = useState<string | null>(null);

  // Repetitions completed in the current attempt. The backend emits a
  // `just_completed` edge per detected rep (deterministic segmentation); the
  // screen owns the cumulative counter and de-dups on `last_completed_at`.
  const [repsDone, setRepsDone] = useState(0);
  const [repSignalSeen, setRepSignalSeen] = useState(false);
  const [repPulse, setRepPulse] = useState(false);
  const lastRepAtRef = useRef<number | null>(null);
  const targetRepsRef = useRef(targetReps);
  targetRepsRef.current = targetReps;

  // A dev/demo stream to watch when there is no real hardware session: open
  // the patient app with ?stream=<rehab_session_id> and it subscribes to that
  // session's gateway feed (drive it with scripts/stream_capture_loop.py).
  const demoStreamSession =
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("stream")
      : null;
  const streamSessionId = sessionId ?? demoStreamSession;

  const stream = useGatewayStream(streamSessionId, GATEWAY_TOKEN, {
    onEvent: (event) => {
      setLiveEventSeen(true);
      const quality = event.signal_quality;
      setCalibrationReasons(quality.reasons);
      if (quality.level === "HIGH") {
        setCalibration(Math.min(100, Math.round((quality.calibration_duration_seconds / 5) * 100)));
      }
      // The backend reports the timestamp of the latest detected rep in its
      // recent window; that value only moves forward. Count a rep whenever it
      // advances. The first event just sets the baseline (reps completed before
      // the patient was watching are not counted).
      const rep = event.repetitions;
      if (rep && rep.last_completed_at != null) {
        if (lastRepAtRef.current === null) {
          lastRepAtRef.current = rep.last_completed_at;
          setRepSignalSeen(true);
        } else if (rep.last_completed_at > lastRepAtRef.current) {
          lastRepAtRef.current = rep.last_completed_at;
          setRepSignalSeen(true);
          setRepsDone((n) => Math.min(targetRepsRef.current, n + 1));
          setRepPulse(true);
          window.setTimeout(() => setRepPulse(false), 600);
        }
      }
    },
  });

  useEffect(() => {
    if (view !== "calibration" || liveEventSeen) return;
    if (calibration > 0 && calibration < 100) {
      const timer = window.setTimeout(() => setCalibration((value) => Math.min(100, value + 25)), 480);
      return () => window.clearTimeout(timer);
    }
  }, [view, calibration, liveEventSeen]);

  useEffect(() => {
    if (view === "setup") {
      setRepsDone(0);
      setRepSignalSeen(false);
      lastRepAtRef.current = null;
    }
  }, [view]);
  const repsRemaining = Math.max(0, targetReps - repsDone);

  const bleStatusLabel: Record<SensorUiStatus, string> = {
    idle: t.registerSensor,
    requesting: t.bleRequesting,
    connecting: t.bleConnecting,
    connected: t.bleConnected,
    disconnected: t.bleDisconnected,
    error: t.bleError,
  };

  const sensorList = (
    <div className="sensor-list">
      {SENSOR_ROLES.map(({ role, label }) => {
        const status = sensorStates[role];
        const isBusy = status === "requesting" || status === "connecting";
        const isConnected = status === "connected";
        const saved = savedSensors[role];
        return (
          <div className="sensor" key={role}>
            <span className="sensor-icon">
              <Icon name="sensor" size={18} />
            </span>
            <div>
              <b>{role.toUpperCase()}</b>
              <small>{label}</small>
              <small className="sensor-saved">
                {saved ? `${t.savedSensorLabel}: ${saved.deviceName ?? saved.deviceId}` : t.noSavedSensor}
              </small>
            </div>
            {view === "setup" ? (
              <Button
                variant="secondary"
                onClick={() => connectSensor(role)}
                disabled={!bleSupported || isBusy || isConnected}
                title={bleSupported ? undefined : t.bleUnsupported}
              >
                {status === "error" ? t.bleRetry : bleStatusLabel[status]}
              </Button>
            ) : (
              <span className={`status ${isConnected || liveEventSeen ? "" : "is-waiting"}`}>
                <i />
                {isConnected || liveEventSeen ? t.connected : t.waiting}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );

  const metricCards = (
    <MetricGrid
      metrics={[
        { label: "ROM", value: t.notCalculated },
        { label: "Score", value: t.notCalculated },
        { label: "Signal", value: resultSignal ?? t.notCalculated },
      ]}
    />
  );

  const finishSession = async () => {
    if (attemptId) {
      api.gateway.completeExerciseAttempt(attemptId).catch(() => undefined);
    }
    if (sessionId) {
      api.gateway
        .signalQuality(sessionId)
        .then((quality) => setResultSignal(quality.level))
        .catch(() => undefined);
    }
    go("result");
  };

  const submitCheck = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!sessionId) {
      setSaved(true);
      return;
    }
    try {
      const response = await api.symptomCheck.submit(sessionId, {
        pain_before: painBefore,
        pain_after: painAfter,
        reported_symptoms: [],
      });
      if (response.safety_assessment.level) {
        setSafetyNote(`${response.safety_assessment.level}: ${response.safety_assessment.reasons.join(", ")}`);
      }
      setSaved(true);
    } catch {
      setSaved(true);
    }
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
  } else if (view === "plan") {
    content = (
      <>
        <div className="eyebrow">
          {t.plan} · POD {usingDemoData ? demoPod : patient?.post_op_day ?? "—"}
        </div>
        <h2>{t.today}</h2>
        <p className="intro">
          {t.greeting}, <b>{usingDemoData ? demoName : patient?.display_name ?? "—"}</b>.
        </p>
        {usingDemoData && <p className="demo-note">{t.demoDataLabel}</p>}
        <article className="exercise-card">
          <div className="exercise-art">
            <span className="leg leg-top" />
            <span className="leg leg-bottom" />
            <span className="exercise-dot" />
          </div>
          <div className="exercise-info">
            <span className="tag">01</span>
            <h3>{exerciseName}</h3>
            <p>
              {t.duration} · {repsLabel}
            </p>
            <Button onClick={() => go("setup")}>
              <Icon name="play" />
              {t.start}
            </Button>
          </div>
        </article>
        <div className="tip">
          <Icon name="heart" size={18} />
          <span>{t.cue}</span>
        </div>
      </>
    );
  } else if (view === "setup") {
    content = (
      <>
        <div className="step">
          <span>01</span>
          <div>
            <small>{t.setup}</small>
            <b>{t.placement}</b>
          </div>
        </div>
        <div className="placement">
          <div className="body-guide">
            <span className="head" />
            <span className="torso" />
            <span className="guide-leg one" />
            <span className="guide-leg two" />
            <i className="pin thigh">1</i>
            <i className="pin shank">2</i>
            <i className="pin foot">3</i>
          </div>
          <p>THIGH · SHANK · FOOT</p>
        </div>
        {!bleSupported && <p className="demo-note">{t.bleUnsupported}</p>}
        {sensorList}
        {Object.keys(savedSensors).length > 0 && (
          <>
            <p className="sensor-remembered-note">{t.sensorsRemembered}</p>
            <Button variant="text-button" full onClick={resetSensorConfig}>
              <Icon name="close" size={16} />
              {t.resetSensors}
            </Button>
          </>
        )}
        <Button
          full
          onClick={async () => {
            if (canUseRealSession && !sessionId) await startRealSession();
            else if (hwDev && !sessionId) await startDevHardwareSession();
            go("calibration");
          }}
        >
          {t.continue}
          <Icon name="arrow" />
        </Button>
      </>
    );
  } else if (view === "calibration") {
    content = (
      <>
        <div className="step">
          <span>02</span>
          <div>
            <small>{t.calibration}</small>
            <b>{calibration === 100 ? t.calibrationDone : t.stayStill}</b>
          </div>
        </div>
        <div className="calibration-orb">
          <div className={calibration ? "orb active" : "orb"}>
            <Icon name={calibration === 100 ? "check" : "sensor"} size={48} />
          </div>
          <strong>{calibration ? `${calibration}%` : "—"}</strong>
          <p>{calibration === 100 ? t.readyToStart : "Static technical check"}</p>
        </div>
        <div className="progress-line">
          <span style={{ width: `${calibration}%` }} />
        </div>
        {liveEventSeen && stream.reconnectCount > 0 && <p className="demo-note">{t.reconnecting}</p>}
        {liveEventSeen && calibrationReasons.length > 0 && calibration < 100 && (
          <p className="demo-note">
            {t.safetyReasons}: {calibrationReasons.join(", ")}
          </p>
        )}
        <Button full onClick={() => (calibration === 100 ? go("exercise") : setCalibration(1))}>
          {calibration === 100 ? t.continue : t.calibrate}
          <Icon name="arrow" />
        </Button>
        {hwDev && calibration < 100 && (
          <Button variant="text-button" full onClick={() => go("exercise")}>
            {t.skipCalibrationDev}
          </Button>
        )}
      </>
    );
  } else if (view === "exercise") {
    content = (
      <>
        <div className="session-top">
          <div>
            <span className="live">
              <i /> {liveEventSeen ? "LIVE" : "LIVE REPLAY"}
            </span>
            <h2>{exerciseName}</h2>
          </div>
          <button className="round" aria-label={t.pause} onClick={() => go("pause")}>
            <Icon name="pause" />
          </button>
        </div>
        <div className="exercise-video">
          <div className="exercise-video-frame">
            <Icon name="play" size={56} />
            <span>{t.videoComingSoon}</span>
          </div>
        </div>
        <div className={repPulse ? "reps-counter pulse" : "reps-counter"}>
          <span>{repsRemaining === 0 ? t.exerciseDoneHint : t.repsRemaining}</span>
          <strong>{repsRemaining}</strong>
          <small>
            {repsDone} / {targetReps}
          </small>
        </div>
        {repSignalSeen ? (
          <div className="demo-cue">
            <span>
              <Icon name="check" size={17} />
            </span>
            {t.autoReps}
          </div>
        ) : (
          <Button
            variant="secondary"
            full
            onClick={() => setRepsDone((n) => Math.min(targetReps, n + 1))}
            disabled={repsRemaining === 0}
          >
            {t.manualRepFallback}
          </Button>
        )}
        <div className="demo-cue">
          <span>
            <Icon name="heart" size={17} />
          </span>
          {t.cue}
        </div>
        <Button variant="secondary" full onClick={() => setStopOpen(true)}>
          {t.finish}
        </Button>
        {stopOpen && (
          <div className="modal-backdrop">
            <div className="modal" role="dialog" aria-modal="true">
              <button className="modal-close" aria-label="Close" onClick={() => setStopOpen(false)}>
                <Icon name="close" />
              </button>
              <h3>{t.stop}</h3>
              <p>{t.stopNote}</p>
              <Button full onClick={finishSession}>
                {t.confirmStop}
              </Button>
              <Button variant="text-button" full onClick={() => setStopOpen(false)}>
                {t.cancel}
              </Button>
            </div>
          </div>
        )}
      </>
    );
  } else if (view === "pause") {
    content = (
      <>
        <div className="pause-visual">
          <Icon name="pause" size={52} />
        </div>
        <h2>{t.pause}</h2>
        <p className="intro">Сделайте короткий перерыв. Когда будете готовы, вернитесь к движению.</p>
        <Button full onClick={() => go("exercise")}>
          <Icon name="play" />
          {t.resume}
        </Button>
        <Button variant="text-button" full onClick={finishSession}>
          {t.finish}
        </Button>
      </>
    );
  } else if (view === "result") {
    content = (
      <>
        <div className="success-mark">
          <Icon name="check" size={40} />
        </div>
        <h2>{t.result}</h2>
        <p className="intro">{exerciseName}</p>
        {metricCards}
        <div className="demo-note">
          <b>{liveEventSeen ? t.signalConfidence : t.synthetic}</b>
          <span>{t.notCalculated}</span>
        </div>
        <Button full onClick={() => go("check")}>
          {t.continue}
          <Icon name="arrow" />
        </Button>
      </>
    );
  } else if (view === "check") {
    content = (
      <>
        <div className="step">
          <span>03</span>
          <div>
            <small>{t.check}</small>
            <b>Ваши ответы помогут врачу увидеть динамику</b>
          </div>
        </div>
        <form onSubmit={submitCheck}>
          <div className="pain-row">
            <label>
              {t.before}
              <output>{painBefore}</output>
              <input
                aria-label={t.before}
                type="range"
                min="0"
                max="10"
                value={painBefore}
                onChange={(e) => setPainBefore(Number(e.target.value))}
              />
            </label>
            <label>
              {t.after}
              <output>{painAfter}</output>
              <input
                aria-label={t.after}
                type="range"
                min="0"
                max="10"
                value={painAfter}
                onChange={(e) => setPainAfter(Number(e.target.value))}
              />
            </label>
          </div>
          <fieldset>
            <legend>{t.difficulty}</legend>
            <div className="choices">
              {[t.easy, t.normal, t.hard].map((value, i) => (
                <label key={value}>
                  <input type="radio" required name="difficulty" value={i} defaultChecked={i === 1} />
                  <span>{value}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend>{t.symptoms}</legend>
            <div className="choices">
              {[t.no, t.yes].map((value, i) => (
                <label key={value}>
                  <input type="radio" required name="symptoms" value={i} defaultChecked={!i} />
                  <span>{value}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <Button type="submit">{t.save}</Button>
        </form>
        {saved && (
          <div role="status" className="saved">
            <Icon name="check" />
            {t.saved}
            {safetyNote && <small> · {safetyNote}</small>}
            <button onClick={() => go("plan")}>{t.back}</button>
          </div>
        )}
      </>
    );
  } else if (view === "progress") {
    content = (
      <>
        <div className="eyebrow">Последние 7 дней</div>
        <h2>{t.progress}</h2>
        <div className="progress-summary">
          <div>
            <strong>3</strong>
            <span>{t.completed}</span>
          </div>
          <div>
            <strong>—</strong>
            <span>ROM</span>
          </div>
        </div>
        <section className="chart-card">
          <div className="chart-title">
            <b>{t.adherence}</b>
            <span>Demo</span>
          </div>
          <div className="bars">
            {[38, 55, 42, 72, 61, 82, 67].map((height, i) => (
              <i key={i} style={{ height: `${height}%` }} />
            ))}
          </div>
          <div className="week">
            <span>Пн</span>
            <span>Вт</span>
            <span>Ср</span>
            <span>Чт</span>
            <span>Пт</span>
            <span>Сб</span>
            <span>Вс</span>
          </div>
        </section>
        <p className="footnote">{t.notice}</p>
      </>
    );
  } else {
    content = (
      <>
        <div className="eyebrow">PHOENIX CARE</div>
        <h2>{t.messages}</h2>
        <div className="empty">
          <span>
            <Icon name="message" size={30} />
          </span>
          <b>{t.emptyMessages}</b>
          <p>Здесь будут отображаться сообщения вашей команды восстановления.</p>
        </div>
      </>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#plan" onClick={() => go(identity ? "plan" : "login")}>
          <span>p</span>PHOENIX
        </a>
        <div className="topbar-actions">
          <LanguageSwitcher lang={lang} onChange={setLang} />
          {identity && (
            <button className="text-button" onClick={logout}>
              {t.logout}
            </button>
          )}
        </div>
      </header>
      <main>
        {view !== "login" && <ReplayNotice label={t.synthetic} detail={t.notice} />}
        {view !== "login" && view !== "plan" && (
          <button className="back-button" onClick={back}>
            <Icon name="arrow" size={16} />
            {t.goBack}
          </button>
        )}
        <section className="content" aria-live="polite">
          {content}
        </section>
      </main>
      {view !== "login" && (
        <nav className="bottom-nav">
          <button className={view === "plan" ? "active" : ""} onClick={() => go("plan")}>
            <Icon name="home" />
            <span>{t.plan}</span>
          </button>
          <button className={view === "progress" ? "active" : ""} onClick={() => go("progress")}>
            <Icon name="chart" />
            <span>{t.progress}</span>
          </button>
          <button className={view === "messages" ? "active" : ""} onClick={() => go("messages")}>
            <Icon name="message" />
            <span>{t.messages}</span>
          </button>
        </nav>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
