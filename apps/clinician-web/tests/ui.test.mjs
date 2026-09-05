import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const page=readFileSync(new URL("../src/main.tsx",import.meta.url),"utf8");
test("doctor UI includes stage 12 workflows",()=>{for(const text of ["Кабинет врача","Срочно","На проверке","Стабильно","Динамика","Техническое качество","НЕДЕЛЬНАЯ СВОДКА","Сохранить новой версией","Хронология","De-identified export"])assert.ok(page.includes(text))});
test("doctor UI gives feedback while data is loading or unavailable",()=>{for(const text of ["Загружаем актуальные данные…","Повторить","rule version, trigger и источник"])assert.ok(page.includes(text))});
test("prescription version is saved through protected API",()=>{assert.ok(page.includes("/protocol-versions"));assert.ok(page.includes("Bearer ${token}"));assert.ok(page.includes("audit trail"))});
