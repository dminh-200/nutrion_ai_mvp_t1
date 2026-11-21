import {
  ArrowDownRight, ArrowLeft, ArrowRight, ArrowUpRight, BookOpen, ChartNoAxesColumn,
  Check, ChevronDown, ChevronLeft, ChevronRight, CircleAlert, Clock3, Coffee,
  Compass, Leaf, Moon, ShieldCheck, Sun, Sunrise, Utensils, X,
} from "lucide-react";
import { motion, MotionConfig } from "motion/react";
import { useEffect, useId, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { mount, type ComponentArgs } from "./mount";
import mealEditorial from "../../assets/meal-editorial.jpg";
import { mealArcs, mealColor } from "./meal-math.mjs";

type Nutrient = "kcal" | "protein_g" | "fat_g" | "carb_g" | "sodium_mg" | "fiber_g";
type Nutrition = Partial<Record<Nutrient, number | null>>;
type Item = Nutrition & { id: number | null; name: string; grams: number | null };
type Meal = { kind: string; label: string; kcal: number | null; items: Item[] };
type Day = { number: number; meals: Meal[]; metrics: Nutrition };
type Goals = Partial<Record<"target_kcal" | "sodium_max_mg" | "fiber_min_g" | "bmi" | "bmr" | "tdee", number | null>>;
type Source = { name: string; page: string; excerpts: string[] };
type Model = {
  identity: string;
  status: string;
  status_label: string;
  message: string;
  patient_code: string;
  days: Day[];
  goals?: Goals;
  needs?: string[];
  sources?: Source[];
  review_note: string;
  retry_count?: number | null;
  diagnostics?: { api_attempts: number | null; mock_calls: number | null; cache_hits: number | null } | null;
};

const numberFormat = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 });
const number = (value?: number | null) => value == null ? "—" : numberFormat.format(value);
const quantity = (value: number | null | undefined, unit: string) =>
  value == null ? "Chưa có dữ liệu" : `${number(value)} ${unit}`;

const icons = { breakfast: Sunrise, lunch: Sun, dinner: Moon, snack: Coffee };
const headings: { key: Nutrient; label: string; unit: string }[] = [
  { key: "kcal", label: "Năng lượng", unit: "kcal" },
  { key: "protein_g", label: "Đạm", unit: "g" },
  { key: "fat_g", label: "Chất béo", unit: "g" },
  { key: "carb_g", label: "Tinh bột", unit: "g" },
  { key: "sodium_mg", label: "Natri", unit: "mg" },
  { key: "fiber_g", label: "Chất xơ", unit: "g" },
];

function Status({ model }: { model: Model }) {
  const healthy = model.status === "approved";
  const waiting = ["pending_review", "needs_human_review"].includes(model.status);
  const Icon = healthy ? Check : waiting ? Clock3 : CircleAlert;
  return <Badge variant="outline" className={`nx-status ${healthy ? "is-ok" : waiting ? "is-pending" : "is-neutral"}`}>
    <Icon aria-hidden="true" /> {model.status_label}
  </Badge>;
}

function Plate({ day, goal, active }: { day: Day; goal?: number | null; active: string }) {
  const arcs = day.metrics.kcal == null ? [] : mealArcs(day.meals);
  const selected = arcs.find(({ kind }) => kind === active);
  const summary = arcs.map((arc) => `${arc.label}: ${quantity(arc.kcal, "kcal")}`).join(". ");
  return <div className="nx-plate-wrap">
    <div className="nx-orbit" aria-hidden="true" />
    <figure className="nx-plate" aria-label={summary ? `Phân bổ năng lượng. ${summary}` : "Năng lượng trong ngày"}>
      <svg viewBox="0 0 240 240" aria-hidden="true">
        <circle className="nx-rim" cx="120" cy="120" r="117" />
        <circle className="nx-track" cx="120" cy="120" r="93" />
        {arcs.map(({ kind, start, length, color }) =>
          <circle className="nx-sector" key={kind} cx="120" cy="120" r="93" pathLength="100"
            fill="none" stroke={color} strokeWidth="29" transform="rotate(-125 120 120)"
            strokeDashoffset={-start} strokeDasharray={`${length} 100`}
            style={{ opacity: kind === active ? 1 : 0.58 }} />
        )}
      </svg>
      <div className="nx-plate-text">
        <span>Năng lượng</span>
        <strong>{number(day.metrics.kcal)}</strong>
        <small>{day.metrics.kcal == null ? "Chưa có dữ liệu" : "kcal trong ngày"}</small>
        {goal != null && <small className="nx-goal">Mục tiêu {quantity(goal, "kcal")}</small>}
      </div>
      <figcaption>{selected ? `${selected.label} · ${quantity(selected.kcal, "kcal")}` : arcs.length ? "Năng lượng theo bữa" : "Chưa đủ số liệu để vẽ vòng"}</figcaption>
    </figure>
  </div>;
}

const fadeIn = { opacity: 0, y: 5 };
const fadeEnd = { opacity: 1, y: 0 };
const short = { duration: 0.22 };

function Hero({ day, model, meal }: { day: Day; model: Model; meal: Meal }) {
  const items = [headings[1], headings[3], headings[4]];
  return <section className="nx-hero" aria-label="Dinh dưỡng trong ngày">
    <div className="nx-hero-body">
      <div className="nx-eyebrow"><Leaf aria-hidden="true" /> Dinh dưỡng trong ngày</div>
      <motion.div key={day.number} initial={fadeIn} animate={fadeEnd} transition={short}>
        <h2>Ngày {day.number}</h2>
        <p>{model.message}</p>
        <div className="nx-metrics">{items.map(({ key, label, unit }) =>
          <div key={key}><span>{label}</span>
            <strong aria-label={quantity(day.metrics[key], unit)}>{number(day.metrics[key])}
              {day.metrics[key] != null && <small>{unit}</small>}
            </strong>
          </div>
        )}</div>
      </motion.div>
    </div>
    <Plate day={day} goal={model.goals?.target_kcal} active={meal.kind} />
  </section>;
}

function Timeline({ days, day, choose }: { days: Day[]; day: Day; choose: (number: number) => void }) {
  const groupId = useId();
  const at = days.findIndex((item) => item.number === day.number);
  return <section className="nx-timeline" aria-label="Chọn ngày">
    <div className="nx-timeline-label"><span>Lịch thực đơn</span><small>{days.length} ngày có khẩu phần</small></div>
    <fieldset aria-label="Ngày thực đơn">
      {days.map(({ number: entry }) => <label key={entry}>
        <input name={groupId} type="radio" aria-label={`Ngày ${entry}`}
          checked={entry === day.number} onChange={() => choose(entry)} />
        <span>Ngày {entry}</span>
      </label>)}
    </fieldset>
    {days.length > 1 && <div className="nx-timeline-arrows">
      <Button variant="outline" size="icon-sm" type="button" aria-label="Ngày trước" disabled={at <= 0}
        onClick={() => choose(days[at - 1].number)}><ChevronLeft aria-hidden="true" /></Button>
      <Button variant="outline" size="icon-sm" type="button" aria-label="Ngày sau" disabled={at >= days.length - 1}
        onClick={() => choose(days[at + 1].number)}><ChevronRight aria-hidden="true" /></Button>
    </div>}
  </section>;
}

function MealBoard({ day, meal, choose }: { day: Day; meal: Meal; choose: (kind: string) => void }) {
  const hasArtwork = day.meals.some(({ kind }) => ["breakfast", "lunch", "dinner"].includes(kind));
  const navigate = (event: KeyboardEvent<HTMLDivElement>) => {
    const steps: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1 };
    if (!(event.key in steps) && event.key !== "Home" && event.key !== "End") return;
    const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
    const target = (event.target as HTMLElement).closest('[role="tab"]');
    const index = tabs.findIndex((tab) => tab === target);
    if (index < 0) return;
    // Radix's document-level focus lookup sees the Streamlit shadow host.
    event.preventDefault();
    event.stopPropagation();
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1
      : (index + steps[event.key] + tabs.length) % tabs.length;
    choose(day.meals[next].kind);
    tabs[next].focus({ preventScroll: true });
  };
  return <Card className="nx-board" aria-label="Các bữa trong ngày">
    <div className="nx-board-head"><h2>Các bữa trong ngày</h2>{hasArtwork && <span>Ảnh minh họa</span>}</div>
    <Tabs value={meal.kind} onValueChange={choose} className="nx-meals">
      <TabsList className="nx-meal-options" aria-label="Chọn bữa ăn" onKeyDownCapture={navigate}>
        {day.meals.map((item) => {
          const Icon = icons[item.kind as keyof typeof icons] ?? Utensils;
          return <TabsTrigger key={item.kind} value={item.kind} aria-label={item.label}
            style={{ "--meal-color": mealColor(item.kind), "--meal-art": `url("${mealEditorial}")` } as CSSProperties}>
            <span className="nx-meal-art" data-meal={item.kind} aria-hidden="true">
              <span className="nx-meal-icon"><Icon /></span>
            </span>
            <span className="nx-meal-choice-label"><strong>{item.label}</strong>
              <small>{quantity(item.kcal, "kcal")}</small>
            </span>
            {item.kind === meal.kind && <motion.span className="nx-meal-selection" layoutId="meal-selection" />}
          </TabsTrigger>;
        })}
      </TabsList>
      {day.meals.map((entry) => <TabsContent value={entry.kind} key={entry.kind}>
        <motion.div className="nx-dishes" key={`${day.number}/${entry.kind}`} initial={fadeIn} animate={fadeEnd} transition={short}>
          <div className="nx-dish-label"><span>Món ăn · {entry.label}</span><span>Khẩu phần</span></div>
          <ul>{entry.items.map((item, index) => <li key={item.id ?? index}>
            <span>{item.name}</span><b>{quantity(item.grams, "g")}</b>
          </li>)}</ul>
        </motion.div>
      </TabsContent>)}
    </Tabs>
  </Card>;
}

function NutritionDetails({ day, goals }: { day: Day; goals: Goals }) {
  return <>
    <div className="nx-detail-metrics">
      {headings.map(({ key, label, unit }) => <div key={key}><span>{label}</span><b>{quantity(day.metrics[key], unit)}</b></div>)}
    </div>
    <h3>Khẩu phần từng món</h3>
    <Table className="nx-dish-table">
      <TableHeader><TableRow><TableHead scope="col">Món ăn</TableHead><TableHead scope="col">g</TableHead><TableHead scope="col">kcal</TableHead>
        <TableHead scope="col">Đạm (g)</TableHead><TableHead scope="col">Béo (g)</TableHead><TableHead scope="col">Tinh bột (g)</TableHead>
        <TableHead scope="col">Natri (mg)</TableHead></TableRow></TableHeader>
      {day.meals.map((meal) => <TableBody key={meal.kind}>
        <TableRow><TableHead scope="rowgroup" colSpan={7}>{meal.label}</TableHead></TableRow>
        {meal.items.map((item, index) => <TableRow key={item.id ?? index}>
          <TableHead scope="row">{item.name}</TableHead>
          {([item.grams, item.kcal, item.protein_g, item.fat_g, item.carb_g, item.sodium_mg]).map((value, i) =>
            <TableCell key={i}>{number(value)}</TableCell>)}
        </TableRow>)}
      </TableBody>)}
    </Table>
    <p className="nx-subtle">Dấu — biểu thị giá trị chưa có.</p>
    <h3>Mục tiêu và chỉ số hồ sơ</h3>
    <dl className="nx-facts">
      {([
        ["Năng lượng mục tiêu", goals.target_kcal, "kcal"],
        ["Natri tối đa", goals.sodium_max_mg, "mg"],
        ["Chất xơ tối thiểu", goals.fiber_min_g, "g"],
        ["BMI", goals.bmi, ""], ["BMR", goals.bmr, "kcal"], ["TDEE", goals.tdee, "kcal"],
      ] as const).map(([label, value, unit]) => <div key={label}><dt>{label}</dt>
        <dd>{quantity(value, unit).trim()}</dd></div>)}
    </dl>
  </>;
}

function Evidence({ model }: { model: Model }) {
  const sources = model.sources ?? [];
  return <>
    <h3>Nhu cầu theo hồ sơ</h3>
    {model.needs?.length ? <ul className="nx-tags">{model.needs.map((need) => <li key={need}>{need}</li>)}</ul>
      : <p className="nx-subtle">Ca này chưa có nhu cầu lưu kèm.</p>}
    {model.review_note && <div className="nx-review-note"><strong>Ghi chú chuyên gia</strong><p>{model.review_note}</p></div>}
    <h3>Tài liệu tham khảo</h3>
    {!sources.length && <p className="nx-subtle">Chưa có tài liệu lưu kèm cho ca này.</p>}
    <ul className="nx-source-list">{sources.map(({ name, page, excerpts }) =>
      <li key={JSON.stringify([name, page])}>
        {excerpts.length ? <details>
          <summary><BookOpen aria-hidden="true" /><span>{name}{page && <small>Trang {page}</small>}</span>
            <ChevronDown aria-hidden="true" /></summary>
          {excerpts.map((excerpt) => <p key={excerpt}>{excerpt}</p>)}
        </details> : <div className="nx-source-label"><BookOpen aria-hidden="true" />
          <span>{name}{page && <small>Trang {page}</small>}</span></div>}
      </li>
    )}</ul>
    {model.retry_count != null && <p className="nx-subtle">Số lần điều chỉnh tự động: {number(model.retry_count)}</p>}
  </>;
}

function Insight({ model, day, portal }: { model: Model; day: Day; portal: HTMLElement | null }) {
  const [panel, setPanel] = useState<"nutrition" | "sources">("nutrition");
  const [open, setOpen] = useState(false);
  const returnTo = useRef<HTMLButtonElement | null>(null);
  const launch = (name: typeof panel, trigger: HTMLButtonElement) => {
    returnTo.current = trigger;
    setPanel(name);
    setOpen(true);
  };
  return <Card className="nx-insight" aria-label="Hiểu kế hoạch">
    <div className="nx-insight-head"><span><Compass aria-hidden="true" /></span><h2>Hiểu kế hoạch</h2></div>
    {Boolean(model.needs?.length) && <ul className="nx-tags">{model.needs?.map((need) => <li key={need}>{need}</li>)}</ul>}
    <div className="nx-insight-actions">
      <Button variant="ghost" type="button" onClick={(event) => launch("nutrition", event.currentTarget)}><ChartNoAxesColumn aria-hidden="true" />
        Chi tiết dinh dưỡng <ArrowUpRight aria-hidden="true" /></Button>
      <Button variant="ghost" type="button" onClick={(event) => launch("sources", event.currentTarget)}><BookOpen aria-hidden="true" />
        Nhu cầu và nguồn <ArrowUpRight aria-hidden="true" /></Button>
    </div>
    <Sheet open={open} onOpenChange={setOpen}>
      {portal && <SheetContent container={portal} showCloseButton={false} overlayClassName="nx-sheet-overlay" className="nx-sheet" onCloseAutoFocus={(event) => {
          event.preventDefault();
          returnTo.current?.focus({ preventScroll: true });
        }}>
          <div className="nx-sheet-head">
            <div><SheetTitle>{panel === "nutrition" ? "Chi tiết dinh dưỡng" : "Nhu cầu và nguồn"}</SheetTitle>
              <SheetDescription>{panel === "nutrition" ? `Ngày ${day.number} · Số liệu khẩu phần` : "Thông tin lưu cùng kế hoạch"}</SheetDescription>
            </div>
            <SheetClose className="nx-close" aria-label="Đóng"><X aria-hidden="true" /></SheetClose>
          </div>
          <div className="nx-sheet-body">
            {panel === "nutrition" ? <NutritionDetails day={day} goals={model.goals ?? {}} /> : <Evidence model={model} />}
          </div>
      </SheetContent>}
    </Sheet>
  </Card>;
}

function Empty({ model, goBack }: { model: Model; goBack: () => void }) {
  const redirect = model.status === "redirect_to_doctor";
  const Icon = redirect ? ShieldCheck : model.status === "empty" ? Utensils : CircleAlert;
  const unavailable = ["pending_review", "needs_human_review", "approved"].includes(model.status);
  return <section className={`nx-empty ${redirect ? "is-redirect" : ""}`}>
    <div className="nx-empty-symbol"><Icon aria-hidden="true" /></div>
    <h2>{unavailable ? "Chưa có khẩu phần để hiển thị" : model.status_label}</h2>
    <p>{unavailable ? "Bản ghi này chưa có món ăn. Bạn có thể quay lại Hồ sơ để thử một ca khác." : model.message}</p>
    {model.review_note && <div className="nx-review-note"><strong>Ghi chú chuyên gia</strong><p>{model.review_note}</p></div>}
    <Button type="button" className="nx-primary" onClick={goBack}>Về Hồ sơ <ArrowRight aria-hidden="true" /></Button>
  </section>;
}

function MealStudio({ model, goBack }: { model: Model; goBack: () => void }) {
  const [dayNumber, setDayNumber] = useState(model.days[0]?.number);
  const [mealKind, setMealKind] = useState("");
  const [portal, setPortal] = useState<HTMLDivElement | null>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const day = model.days.find((item) => item.number === dayNumber) ?? model.days[0];
  const meal = day?.meals.find((item) => item.kind === mealKind) ?? day?.meals[0];
  const { sodium_max_mg, fiber_min_g } = model.goals ?? {};
  const sodium = day?.metrics.sodium_mg;
  const fiber = day?.metrics.fiber_g;
  const sodiumWarn = sodium != null && sodium_max_mg != null && sodium > sodium_max_mg;
  const fiberWarn = fiber != null && fiber_min_g != null && fiber < fiber_min_g;

  useEffect(() => {
    const frame = requestAnimationFrame(() => title.current?.scrollIntoView({block: "start", behavior: "instant"}));
    return () => cancelAnimationFrame(frame);
  }, [model.identity]);

  return <MotionConfig reducedMotion="user">
    <article className="nx-studio" aria-label="Thực đơn Nutri AI">
      <div className="nx-top">
        <Button type="button" variant="ghost" className="nx-back" onClick={goBack}><ArrowLeft aria-hidden="true" /> Hồ sơ</Button>
        <span className="nx-top-slash" aria-hidden="true">/</span><span aria-current="page">Thực đơn</span>
        <span className="nx-preview"><span /> Dữ liệu giả lập</span>
      </div>
      <header className="nx-title">
        <div><h1 ref={title}>Thực đơn của bạn</h1>
          {model.patient_code && <p>Hồ sơ {model.patient_code}{model.days.length > 0 && ` · Kế hoạch ${model.days.length} ngày`}</p>}
        </div>
        {model.status !== "empty" && <Status model={model} />}
      </header>
      {day && meal ? <>
        <Timeline days={model.days} day={day} choose={setDayNumber} />
        <div className="nx-overview">
          <Hero day={day} model={model} meal={meal} />
          <Insight model={model} day={day} portal={portal} />
        </div>
        {(sodiumWarn || fiberWarn) && <Alert className="nx-warning" role="status">
          <CircleAlert aria-hidden="true" /><AlertDescription>
            {sodiumWarn && <p>Natri vượt giới hạn ghi trong hồ sơ ({quantity(sodium_max_mg, "mg")}).</p>}
            {fiberWarn && <p>Chất xơ dưới mục tiêu ghi trong hồ sơ ({quantity(fiber_min_g, "g")}).</p>}
          </AlertDescription>
        </Alert>}
        <MealBoard day={day} meal={meal} choose={setMealKind} />
        {model.review_note && <div className="nx-review-note"><ShieldCheck aria-hidden="true" />
          <div><strong>Ghi chú chuyên gia</strong><p>{model.review_note}</p></div></div>}
        {model.diagnostics && <details className="nx-demo-details">
          <summary><ArrowDownRight aria-hidden="true" /> Thông tin bản thử</summary>
          <p>Lượt gửi API: {number(model.diagnostics.api_attempts)} · Giả lập: {number(model.diagnostics.mock_calls)}
            {" · Đọc cache: "}{number(model.diagnostics.cache_hits)}</p>
        </details>}
      </> : <Empty model={model} goBack={goBack} />}
      <div ref={setPortal} />
    </article>
  </MotionConfig>;
}

export default function render({ data, parentElement, setTriggerValue }: ComponentArgs<Model>) {
  return mount(parentElement, ".nutri-meal-root",
    <MealStudio model={data} key={data.identity} goBack={() => setTriggerValue("go_profile", true)} />);
}
