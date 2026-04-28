import type React from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Check,
  Cpu,
  Film,
  HardDrive,
  Scissors,
  Server,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { navItems } from "./constants";
import { formatDuration, resourcePercent } from "./format";
import { useSystemResources } from "@/hooks/useAdminQueries";
import type { PageKey, ReviewSegment } from "./types";

export function Sidebar({
  page,
  onPageChange,
}: {
  page: PageKey;
  onPageChange: (page: PageKey) => void;
}) {
  const { data: resources } = useSystemResources();
  return (
    <aside className="hidden h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
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
          <div className="mt-3 space-y-3">
            <ResourceLine icon={Cpu} label="CPU 配额" value={resources ? `${resources.cpu_cores.toFixed(1)} cores` : "—"} tone="blue" percent={resourcePercent(resources?.cpu_cores, 16)} />
            <ResourceLine icon={HardDrive} label="内存上限" value={resources ? `${resources.memory_gb.toFixed(1)}GB` : "—"} tone="emerald" percent={resourcePercent(resources?.memory_gb, 16)} />
            <ResourceLine icon={Server} label="FFmpeg 实例" value={String(resources?.clip_workers ?? "—")} tone="amber" percent={resourcePercent(resources?.clip_workers, 4)} />
            <ResourceLine icon={Server} label="Redis 状态" value={resources?.redis ?? "—"} tone={resources?.redis === "ok" ? "emerald" : "amber"} />
          </div>
        </div>
      </div>
    </aside>
  );
}

export function MobileNav({
  page,
  onPageChange,
}: {
  page: PageKey;
  onPageChange: (page: PageKey) => void;
}) {
  return (
    <div className="border-b border-slate-200 bg-white lg:hidden">
      <div className="flex h-14 items-center gap-3 px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white">
          <Scissors size={17} />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-950">ClipFlow AI</div>
          <div className="truncate text-xs text-slate-400">直播智能剪辑后台</div>
        </div>
      </div>
      <nav className="flex gap-2 overflow-x-auto px-4 pb-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = page === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onPageChange(item.key)}
              className={cn(
                "inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-1.5 text-sm transition-colors",
                active
                  ? "bg-blue-50 font-medium text-blue-700"
                  : "text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50 hover:text-slate-950",
              )}
            >
              <Icon size={15} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
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
    <header className="flex min-h-16 flex-col items-stretch gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">
      <div className="min-w-0 flex-1">
        <h1 className="text-lg font-semibold text-slate-950">{title}</h1>
        <p className="mt-0.5 text-xs text-slate-500">{description}</p>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
        {action}
      </div>
    </header>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);

  return (
    <div className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
      <span>
        {total === 0 ? "暂无数据" : `第 ${start}-${end} 条，共 ${total} 条`}
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className={cn(
            "inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50",
            page <= 1 && "cursor-not-allowed opacity-50 hover:bg-white",
          )}
        >
          <ChevronLeft size={15} />
          上一页
        </button>
        <span className="min-w-16 text-center text-xs text-slate-400">
          {page} / {totalPages}
        </span>
        <button
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          className={cn(
            "inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50",
            page >= totalPages && "cursor-not-allowed opacity-50 hover:bg-white",
          )}
        >
          下一页
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
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

export function ChecklistItem({ label, state = "done" }: { label: string; state?: "done" | "pending" | "checking" }) {
  const iconMap = {
    done: <Check className="h-4 w-4 text-emerald-500" />,
    pending: <div className="h-4 w-4 rounded-full border-2 border-slate-300" />,
    checking: <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />,
  };
  const textMap = {
    done: "text-slate-600",
    pending: "text-slate-400",
    checking: "text-blue-600",
  };
  return (
    <div className={cn("flex items-center gap-2", textMap[state])}>
      {iconMap[state]}
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
        {percent !== undefined && <div className={cn("h-1.5 rounded-full", barClass)} style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />}
      </div>
    </div>
  );
}

export function Field({ label, value }: { label: string; value: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      <div className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800">
        {value}
      </div>
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
  formatOption,
}: {
  label: string;
  options: string[];
  values: string[];
  onChange: (values: string[]) => void;
  formatOption?: (option: string) => string;
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
              {formatOption ? formatOption(option) : option}
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
