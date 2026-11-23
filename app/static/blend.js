const field = (id) => document.getElementById(id);
const formatKg = (grams) =>
  grams === null || grams === undefined
    ? "—"
    : (grams / 1000).toLocaleString("en-US", {
        minimumFractionDigits: 3,
        maximumFractionDigits: 3,
      });
const ratio = (value) => `${(value / 10000).toFixed(3)}%`;
const reasons = {
  MISSING_MOISTURE: "缺上下层含水样",
  MISSING_GRADE: "缺分级样",
  GRADE_CONFLICT: "颜色冲突",
  IMPURITY_LIMIT: "杂质预算不足",
  GRADE_LIMIT: "余料色级不符",
  NO_STOCK: "符合条件的干料不足",
};
let run,
  revision = 0,
  source = "dirty",
  signed;
function item(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
async function read(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw Error(data.message || "操作失败，请重试");
  return data;
}
function ledger(headers, records) {
  if (!records.length) return item("p", "暂无证据记录", "empty");
  const table = item("table");
  const head = table.createTHead().insertRow();
  headers.forEach((title) => {
    const th = item("th", title);
    th.scope = "col";
    head.append(th);
  });
  const body = table.createTBody();
  records.forEach((record) => {
    const row = body.insertRow();
    record.forEach((value, i) =>
      row.append(item("td", value, i > 0 ? "num" : "")),
    );
  });
  return table;
}
function options(id, values, labels) {
  field(id).replaceChildren(
    ...values.map((value, i) => new Option(labels?.[i] ?? value, value)),
  );
}
function stats(values) {
  const group = item("div", undefined, "numbers");
  for (const [label, value] of values) {
    const block = item("div");
    block.append(item("span", label), item("strong", value));
    group.append(block);
  }
  return group;
}
async function refresh(id) {
  const stamp = ++revision;
  const confirm = field("sign-form").querySelector("button");
  confirm.disabled = true;
  field("balance").textContent = "正在折算";
  try {
    const parts = [
      "weighing",
      "moisture",
      "grading",
      "drymass",
      "loading",
      "reconcile",
    ];
    const result = await Promise.all(
      parts.map((part) => read(`/api/${part}/${encodeURIComponent(id)}`)),
    );
    if (stamp !== revision) return;
    source = id;
    run = Object.fromEntries(parts.map((part, i) => [part, result[i]]));
    field("batch").textContent = `批次 ${run.weighing.batch}`;
    field("balance").textContent =
      run.reconcile.status === "MATCHED" ? "湿干双账已对平" : "湿干账有差异";
    options("lot", Object.keys(run.drymass.lots));
    options(
      "target",
      run.loading.targets.map((r) => r.target),
    );
    field("actions").hidden = true;
    field("receipt").textContent = "";
    signed = undefined;
    overview();
    confirm.disabled = false;
  } catch (error) {
    if (stamp === revision) field("balance").textContent = error.message;
  }
}
function overview() {
  const r = run.reconcile;
  const figures = [
    ["有效湿重", r.effective_wet_g],
    ["折算水重", r.water_g],
    ["折算干重", r.dry_g],
    ["已装载", r.loaded_g],
    ["可追溯余料", r.remaining_g],
  ];
  field("metrics").replaceChildren(
    ...figures.map(([label, value]) => {
      const metric = item("div", undefined, "kpi");
      metric.append(
        item("span", label),
        item("strong", formatKg(value)),
        item("small", "kg"),
      );
      return metric;
    }),
  );
  field("remainder").textContent = `待折干 ${formatKg(r.pending_wet_g)} kg`;
  lotDetail();
  targetDetail();
  ticketDetail();
}
function lotDetail() {
  const key = field("lot").value;
  const lot = run.drymass.lots[key];
  if (!lot) {
    field("lot-summary").replaceChildren(item("p", "暂无采信批料"));
    field("samples").replaceChildren();
    return;
  }
  const moisture = run.moisture.lots[key],
    grade = run.grading.lots[key];
  const tags = item("div", undefined, "labels");
  tags.append(
    item(
      "span",
      grade.code ? reasons[grade.code] : `${grade.color} · ${grade.grade} 级`,
      "square" + (grade.code ? " warning" : ""),
    ),
  );
  tags.append(
    item(
      "span",
      moisture.code
        ? reasons[moisture.code]
        : `含水 ${ratio(moisture.weighted_ppm_g / moisture.mass_g)}`,
      "square" + (moisture.code ? " warning" : ""),
    ),
  );
  field("lot-summary").replaceChildren(
    tags,
    stats([
      ["湿重 kg", formatKg(lot.wet_g)],
      ["水重 kg", formatKg(lot.water_g)],
      ["干重 kg", formatKg(lot.dry_g)],
    ]),
  );
  const evidence = moisture.samples.map((row) => [
    row.position,
    `${row.mass_g} g`,
    ratio(row.water_ppm),
    row.row,
  ]);
  evidence.push(
    ...grade.samples.map((row) => [
      "分级样",
      row.color,
      `杂质 ${ratio(row.impurity_ppm)}`,
      row.row,
    ]),
  );
  field("samples").replaceChildren(
    ledger(["样位", "样重 / 颜色", "测值", "来源行"], evidence),
  );
}
function targetDetail() {
  const target = run.loading.targets.find(
    (entry) => entry.target === field("target").value,
  );
  if (!target) {
    field("load-plan").replaceChildren(item("p", "暂无有效装车目标"));
    field("allocation").replaceChildren();
    return;
  }
  const summary = item("div", undefined, "labels");
  summary.append(
    item(
      "span",
      target.code ? reasons[target.code] : "可按目标装车",
      `square${target.code ? " warning" : ""}`,
    ),
    item("span", `杂质上限 ${ratio(target.max_impurity_ppm)}`, "square"),
  );
  const mix = item("div", undefined, "mix");
  mix.setAttribute("aria-label", "各批料装载比例");
  const tones = ["#aa842a", "#c3a14d", "#e4c76e"];
  for (const [index, row] of target.sections.entries()) {
    const part = item("span");
    part.style.setProperty("--share", row.dry_g);
    part.style.setProperty("--part", tones[index % tones.length]);
    part.title = `${row.lot} · ${formatKg(row.dry_g)} kg`;
    mix.append(part);
  }
  const empty = item("span");
  empty.style.setProperty("--share", target.short_g);
  mix.append(empty);
  field("load-plan").replaceChildren(
    summary,
    stats([
      ["目标 kg", formatKg(target.target_g)],
      ["装载 kg", formatKg(target.loaded_g)],
      ["欠装 kg", formatKg(target.short_g)],
    ]),
    mix,
  );
  field("allocation").replaceChildren(
    ledger(
      ["批料", "干重 kg", "起位 kg", "末位 kg", "杂质"],
      target.sections.map((row) => [
        row.lot,
        formatKg(row.dry_g),
        formatKg(row.start_g),
        formatKg(row.end_g),
        ratio(row.impurity_ppm),
      ]),
    ),
  );
}
function ticketDetail() {
  const w = run.weighing;
  if (field("ticket-view").value === "all") {
    field("tickets").replaceChildren(
      ledger(
        ["单号", "批料", "净重 kg", "来源行"],
        w.accepted.map((row) => [
          row.ticket,
          row.lot,
          formatKg(row.wet_g),
          row.row,
        ]),
      ),
    );
    return;
  }
  field("tickets").replaceChildren(
    ledger(
      ["单号", "来源行", "判定"],
      [...w.isolated, ...w.duplicates].map((row) => [
        row.raw?.ticket || "—",
        row.row,
        row.message,
      ]),
    ),
  );
}
field("lot").onchange = lotDetail;
field("target").onchange = targetDetail;
field("ticket-view").onchange = ticketDetail;
field("sample").onchange = (e) => refresh(e.target.value);
field("import").onchange = async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const data = await read("/api/sources", { method: "POST", body: file });
    field("sample").add(new Option(file.name, data.source, true, true));
    refresh(data.source);
  } catch (error) {
    field("balance").textContent = error.message;
  } finally {
    event.target.value = "";
  }
};
field("sign-form").onsubmit = async (event) => {
  event.preventDefault();
  const input = source;
  const button = event.submitter;
  button.disabled = true;
  try {
    const record = await read("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: input,
        operator: field("operator").value,
      }),
    });
    if (input !== source) return;
    signed = record.id;
    field("receipt").textContent = record.approval.decision;
    field("download").href = `/api/runs/${signed}/export`;
    field("actions").hidden = false;
  } catch (error) {
    field("receipt").textContent = error.message;
  } finally {
    button.disabled = false;
  }
};
field("verify").onclick = async () => {
  try {
    const record = await read(`/api/runs/${signed}/rerun`, { method: "POST" });
    field("receipt").textContent =
      `复算一致 · ${record.manifest.digest.slice(0, 12)}`;
  } catch (error) {
    field("receipt").textContent = error.message;
  }
};
refresh(source);
