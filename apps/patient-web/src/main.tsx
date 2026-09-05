import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type View = "plan" | "setup" | "calibration" | "exercise" | "pause" | "result" | "check" | "progress" | "messages";
type Lang = "ru" | "kz" | "en";
const copy = {
  ru: { language:"Язык", today:"Сегодняшний план", setup:"Подключение датчиков", calibration:"Калибровка", exercise:"Упражнение", pause:"Пауза", result:"Результат упражнения", check:"Проверка после занятия", progress:"Прогресс", messages:"Сообщения врача", start:"Начать", next:"Далее", stop:"Остановить", resume:"Продолжить", save:"Сохранить", demo:"Это synthetic replay для разработки. Он не является измерением пациента и не используется для score, alert или клинических решений.", waiting:"Ожидает", connected:"Подключён", notCalculated:"Не рассчитано", saved:"Ответы сохранены только в этом локальном demo." },
  kz: { language:"Тіл", today:"Бүгінгі жоспар", setup:"Датчиктерді қосу", calibration:"Калибрлеу", exercise:"Жаттығу", pause:"Кідірту", result:"Жаттығу нәтижесі", check:"Жаттығудан кейінгі тексеру", progress:"Прогресс", messages:"Дәрігер хабарламалары", start:"Бастау", next:"Келесі", stop:"Тоқтату", resume:"Жалғастыру", save:"Сақтау", demo:"Бұл әзірлеуге арналған synthetic replay. Ол пациент өлшемі емес және score, alert не клиникалық шешімдерде қолданылмайды.", waiting:"Күтуде", connected:"Қосылған", notCalculated:"Есептелмеді", saved:"Жауаптар тек осы local demo ішінде сақталды." },
  en: { language:"Language", today:"Today's plan", setup:"Sensor setup", calibration:"Calibration", exercise:"Exercise", pause:"Pause", result:"Exercise result", check:"Post-session check", progress:"Progress", messages:"Clinician messages", start:"Start", next:"Next", stop:"Stop", resume:"Resume", save:"Save", demo:"This is a synthetic replay for development. It is not a patient measurement and is not used for scoring, alerts, or clinical decisions.", waiting:"Waiting", connected:"Connected", notCalculated:"Not calculated", saved:"Responses are saved only in this local demo." }
};
function App() {
  const [lang,setLang]=useState<Lang>("ru"),[view,setView]=useState<View>("plan"),[patient,setPatient]=useState("—"),[pod,setPod]=useState("—"),[calibrated,setCalibrated]=useState(false),[paused,setPaused]=useState(false),[frames,setFrames]=useState(0),[saved,setSaved]=useState(false); const t=copy[lang];
  useEffect(()=>{document.documentElement.lang=lang},[lang]); useEffect(()=>{fetch("/api/v1/demo").then(r=>r.json()).then(d=>{setPatient(d.patient.display_name);setPod(String(d.patient.post_op_day))}).catch(()=>undefined)},[]); useEffect(()=>{if(view!=="exercise"||paused||frames===15)return;const id=setTimeout(()=>setFrames(n=>n+1),700);return()=>clearTimeout(id)},[view,paused,frames]);
  const sensors=<ul>{["THIGH","SHANK","FOOT"].map(s=><li key={s}><b>{s}</b><span className={calibrated?"ready":"waiting"}>{calibrated?t.connected:t.waiting}</span></li>)}</ul>;
  const metrics=<div className="metrics"><p><b>{t.notCalculated}</b>ROM</p><p><b>{t.notCalculated}</b>Correctness Score</p><p><b>{t.notCalculated}</b>Signal Confidence</p></div>;
  let content:React.ReactNode;
  if(view==="plan")content=<><h2>{t.today}</h2><p><b>{patient}</b> · POD {pod}</p><p>Heel Slide</p><button onClick={()=>setView("setup")}>{t.start}</button></>;
  else if(view==="setup")content=<><h2>{t.setup}</h2>{sensors}<button onClick={()=>setView("calibration")}>{t.next}</button></>;
  else if(view==="calibration")content=<><h2>{t.calibration}</h2><p>Static technical check</p><div className="bar"><span style={{width:calibrated?"100%":"20%"}}/></div><button onClick={()=>calibrated?setView("exercise"):setCalibrated(true)}>{calibrated?t.next:t.calibration}</button></>;
  else if(view==="exercise")content=<><h2>{t.exercise}: Heel Slide</h2>{sensors}<p><b>{frames}</b> synthetic frames</p>{metrics}<p className="cue">{t.demo}</p><button onClick={()=>{setPaused(true);setView("pause")}}>{t.pause}</button><button className="danger" onClick={()=>setView("result")}>{t.stop}</button></>;
  else if(view==="pause")content=<><h2>{t.pause}</h2><button onClick={()=>{setPaused(false);setView("exercise")}}>{t.resume}</button><button className="danger" onClick={()=>setView("result")}>{t.stop}</button></>;
  else if(view==="result")content=<><h2>{t.result}</h2>{metrics}<button onClick={()=>setView("check")}>{t.next}</button></>;
  else if(view==="check")content=<><h2>{t.check}</h2><form onSubmit={e=>{e.preventDefault();setSaved(true)}}><label>Pain before <input type="number" min="0" max="10"/></label><label>Pain after <input type="number" min="0" max="10"/></label><label>Symptoms <select><option>No</option><option>Yes</option></select></label><button>{t.save}</button></form>{saved&&<p role="status">{t.saved}</p>}</>;
  else if(view==="progress")content=<><h2>{t.progress}</h2>{metrics}</>;
  else content=<><h2>{t.messages}</h2><p>—</p></>;
  return <main><header><h1>PHOENIX</h1><label>{t.language}<select value={lang} onChange={e=>setLang(e.target.value as Lang)}><option value="ru">Русский</option><option value="kz">Қазақша</option><option value="en">English</option></select></label></header><aside>{t.demo}</aside><section aria-live="polite">{content}</section><nav><button onClick={()=>setView("plan")}>{t.today}</button><button onClick={()=>setView("progress")}>{t.progress}</button><button onClick={()=>setView("messages")}>{t.messages}</button></nav></main>;
}
createRoot(document.getElementById("root")!).render(<App/>);
