import type React from "react";
import {
  AlertTriangle,
  Bell,
  Check,
  Film,
  Scissors,
  Server,
  UserCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { navItems } from "./constants";
import { formatDuration } from "./format";
import type { PageKey, ReviewSegment } from "./types";

export function Sidebar({
  page,
  onPageChange,
}: {
  page: PageKey;
  onPageChange: (page: PageKey) => void;
}) {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex h-16 items-center gap-3 border-b border-slate-100 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white">
          <Scissors size={18} />
        </div>
        <div>
          <div className="text-sm font-semibold text-slate-950">ClipFlow AI</div>
          <div className="text-xs text-slate-400">直播智能剪辑后台</div>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = page === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onPageChange(item.key)}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                active
                  ? "bg-blue-50 font-medium text-blue-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-950",
              )}
            >
              <Icon size={17} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="border-t border-slate-100 p-4">
        <div className="rounded-lg bg-slate-50 p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-700">
            <Server size={14} />
            Worker 资源
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-slate-200">
            <div className="h-1.5 w-full rounded-full bg-slate-300" />
          </div>
          <p className="mt-2 text-xs text-slate-400">在任务队列页查看实时资源</p>
        </div>
      </div>
    </aside>
  );
}

export function Header({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="flex min-h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-950">{title}</h1>
        <p className="mt-0.5 text-xs text-slate-500">{description}</p>
      </div>
      <div className="flex items-center gap-2">
        {action}
        <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="通知">
          <Bell size={18} />
        </button>
        <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="账号">
          <UserCircle size={20} />
        </button>
      </div>
    </header>
  );
}

export function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{hint}</div>
    </div>
  );
}

export function EmptyPreview() {
  return (
    <div className="flex h-full min-h-40 flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50 text-slate-400">
      <Film size={28} />
      <p className="mt-2 text-sm">选择一个项目查看详情</p>
    </div>
  );
}

export function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-900">{value}</div>
    </div>
  );
}

export function ChecklistItem({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-slate-600">
      <Check className="h-4 w-4 text-emerald-500" />
      {label}
    </div>
  );
}

export function LogLine({ time, text }: { time: string; text: string }) {
  return (
    <div className="flex gap-2">
      <span className="shrink-0 font-mono text-slate-400">{time}</span>
      <span>{text}</span>
    </div>
  );
}

export function IconButton({
  icon: Icon,
  label,
  danger,
  onClick,
  disabled,
}: {
  icon: React.ElementType;
  label: string;
  danger?: boolean;
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700",
        danger && "hover:bg-red-50 hover:text-red-500",
        disabled && "cursor-not-allowed opacity-40 hover:bg-transparent hover:text-slate-400",
      )}
      aria-label={label}
    >
      <Icon size={15} />
    </button>
  );
}

export function ResourceLine({
  icon: Icon,
  label,
  value,
  tone,
  percent,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  tone: "blue" | "emerald" | "amber";
  percent?: number;
}) {
  const barClass = {
    blue: "bg-blue-500",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
  }[tone];
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="flex items-center gap-2 text-slate-600">
          <Icon size={14} />
          {label}
        </span>
        <span className="font-medium text-slate-900">{value}</span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-100">
        <div className={cn("h-1.5 rounded-full", barClass)} style={{ width: `${percent ?? 100}%` }} />
      </div>
    </div>
  );
}

export function Field({ label, value }: { label: string; value: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      <input
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-400 focus:outline-none"
        defaultValue={value}
      />
    </label>
  );
}

export function SegmentTimeline({
  segments,
  duration,
  selectedIndex,
  onSelect,
}: {
  segments: ReviewSegment[];
  duration: number;
  selectedIndex: number;
  onSelect: (index: number) => void;
}) {
  if (!segments.length || duration <= 0) {
    return (
      <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-400">
        暂无可绘制的片段时间轴
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-lg bg-slate-50 p-2">
      <div className="relative h-12 rounded bg-slate-200">
        {segments.map((segment, index) => {
          const left = Math.max(0, Math.min(100, (segment.start_time / duration) * 100));
          const width = Math.max(1, Math.min(100 - left, ((segment.end_time - segment.start_time) / duration) * 100));
          return (
            <button
              key={segment.segment_id}
              onClick={() => onSelect(index)}
              title={`${segment.product_name || segment.segment_id} ${formatDuration(segment.start_time)}-${formatDuration(segment.end_time)}`}
              className={cn(
                "absolute top-1 h-10 rounded transition-colors",
                selectedIndex === index ? "bg-blue-600" : "bg-blue-400/70 hover:bg-blue-500",
              )}
              style={{ left: `${left}%`, width: `${width}%` }}
            />
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-xs text-slate-400">
        <span>0:00</span>
        <span>{formatDuration(duration)}</span>
      </div>
    </div>
  );
}

export function Chip({ label, tone }: { label: string; tone: "amber" | "blue" | "emerald" }) {
  const className = {
    amber: "bg-amber-50 text-amber-700",
    blue: "bg-blue-50 text-blue-700",
    emerald: "bg-emerald-50 text-emerald-700",
  }[tone];
  return <span className={cn("rounded-full px-2 py-1 text-xs font-medium", className)}>{label}</span>;
}

export function TranscriptLine({ time, text }: { time: string; text: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2">
      <span className="font-mono text-slate-400">{time}</span>
      <span className="ml-2">{text}</span>
    </div>
  );
}

export function TagGroup({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <div className="mb-2 text-xs text-slate-500">{label}</div>
      <div className="flex flex-wrap gap-2">
        {values.map((value) => (
          <span key={value} className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

export function MultiSelectField({
  label,
  options,
  values,
  onChange,
}: {
  label: string;
  options: string[];
  values: string[];
  onChange: (values: string[]) => void;
}) {
  const toggle = (option: string) => {
    if (values.includes(option)) {
      onChange(values.filter((value) => value !== option));
      return;
    }
    onChange([...values, option]);
  };

  return (
    <div>
      <div className="mb-2 text-xs text-slate-500">{label}</div>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const checked = values.includes(option);
          return (
            <button
              key={option}
              type="button"
              onClick={() => toggle(option)}
              className={cn(
                "rounded-full px-2 py-1 text-xs font-medium ring-1",
                checked
                  ? "bg-blue-50 text-blue-700 ring-blue-100"
                  : "bg-white text-slate-500 ring-slate-200 hover:bg-slate-50",
              )}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function Warning({ text }: { text: string }) {
  return (
    <div className="flex gap-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{text}</span>
    </div>
  );
}

export function SettingsPanel({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-xs text-slate-500">{desc}</p>
      </div>
      {children}
    </section>
  );
}

export function InputField({
  label,
  value,
  onChange,
  password,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  password?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      <input
        type={password ? "password" : "text"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-400 focus:outline-none"
      />
    </label>
  );
}

export function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[] | [string, string][];
}) {
  const normalized = options.map((option) => (Array.isArray(option) ? option : [option, option]));
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-blue-400 focus:outline-none"
      >
        {normalized.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
      <span className="text-sm text-slate-700">{label}</span>
      <button
        onClick={() => onChange(!checked)}
        className={cn("h-6 w-11 rounded-full p-0.5 transition-colors", checked ? "bg-blue-600" : "bg-slate-300")}
        aria-label={label}
      >
        <span className={cn("block h-5 w-5 rounded-full bg-white transition-transform", checked && "translate-x-5")} />
      </button>
    </div>
  );
}

export function SliderField({
  label,
  value,
  max,
  onChange,
}: {
  label: string;
  value: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-slate-500">{label}</span>
        <span className="font-medium text-slate-700">{Math.round(value * 100)}%</span>
      </div>
      <input
        type="range"
        min={0}
        max={max}
        step={0.05}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full"
      />
    </label>
  );
}
