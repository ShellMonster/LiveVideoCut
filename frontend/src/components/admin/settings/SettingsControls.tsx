import { useState, type PointerEvent, type ReactNode } from "react";
import { Check, Eye, EyeOff, Info, Move } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SubtitlePosition } from "@/stores/settingsStore";
import { subtitlePositionLabels } from "./labels";

export const fieldClassName =
  "h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-400 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400";

export function SettingsCard({
  id,
  title,
  desc,
  badge,
  children,
}: {
  id: string;
  title: string;
  desc: string;
  badge?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-6 rounded-lg border border-slate-200 bg-white">
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">{desc}</p>
        </div>
        {badge && <span className="shrink-0 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">{badge}</span>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

export function PresetCard({
  title,
  desc,
  selected,
  tags,
  onClick,
}: {
  title: string;
  desc: string;
  selected: boolean;
  tags: string[];
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-lg border p-4 text-left transition",
        selected ? "border-blue-300 bg-blue-50 ring-2 ring-blue-100" : "border-slate-200 bg-white hover:bg-slate-50",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
        <span className={cn("grid h-5 w-5 place-items-center rounded-full border", selected ? "border-blue-600 bg-blue-600 text-white" : "border-slate-300")}>
          {selected && <Check size={13} />}
        </span>
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-500">{desc}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {tags.map((tag) => (
          <span key={tag} className="rounded-full bg-white px-2 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
            {tag}
          </span>
        ))}
      </div>
    </button>
  );
}

export function OptionCard({
  title,
  desc,
  selected,
  onClick,
}: {
  title: string;
  desc: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-lg border p-4 text-left transition",
        selected ? "border-blue-300 bg-blue-50" : "border-slate-200 bg-white hover:bg-slate-50",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
        {selected && <span className="rounded-full bg-blue-600 px-2 py-0.5 text-xs font-medium text-white">当前</span>}
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-500">{desc}</p>
    </button>
  );
}

export function Field({
  label,
  hint,
  tooltip,
  className,
  children,
}: {
  label: string;
  hint?: string;
  tooltip?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 flex items-center justify-between gap-3 text-xs">
        <span className="flex items-center gap-1.5 font-medium text-slate-600">
          {label}
          {tooltip && <Tooltip text={tooltip} />}
        </span>
        {hint && <span className="text-slate-400">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

export function SecretInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`${fieldClassName} pr-10`}
        placeholder={placeholder}
      />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        className="absolute right-2 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        aria-label={visible ? "隐藏密钥" : "显示密钥"}
        title={visible ? "隐藏密钥" : "显示密钥"}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}

export function Tooltip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex">
      <Info size={13} className="cursor-help text-slate-400" aria-hidden="true" />
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-5 z-20 hidden w-64 -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-3 text-xs font-normal leading-5 text-slate-600 shadow-lg group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
  );
}

export function SegmentedControl({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
}) {
  return (
    <div className="grid gap-1 rounded-lg bg-slate-100 p-1 sm:grid-flow-col sm:auto-cols-fr">
      {options.map(([optionValue, label]) => (
        <button
          key={optionValue}
          onClick={() => onChange(optionValue)}
          className={cn(
            "rounded-md px-3 py-2 text-sm font-medium transition",
            value === optionValue ? "bg-white text-blue-700 shadow-sm" : "text-slate-500 hover:text-slate-800",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function ToggleCard({
  title,
  desc,
  checked,
  disabled,
  onChange,
}: {
  title: string;
  desc: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className={cn("flex items-center justify-between gap-4 rounded-lg bg-slate-50 px-4 py-3", disabled && "opacity-60")}>
      <div className="min-w-0">
        <div className="text-sm font-medium text-slate-800">{title}</div>
        <p className="mt-1 text-xs leading-5 text-slate-500">{desc}</p>
      </div>
      <button
        onClick={() => !disabled && onChange(!checked)}
        disabled={disabled}
        className={cn("h-6 w-11 shrink-0 rounded-full p-0.5 transition-colors", checked ? "bg-blue-600" : "bg-slate-300", disabled && "cursor-not-allowed")}
        aria-label={title}
      >
        <span className={cn("block h-5 w-5 rounded-full bg-white transition-transform", checked && "translate-x-5")} />
      </button>
    </div>
  );
}

export function RangeField({
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
    <label className="block rounded-lg bg-slate-50 p-4">
      <span className="mb-2 flex items-center justify-between text-xs">
        <span className="font-medium text-slate-600">{label}</span>
        <span className="font-semibold text-slate-800">{Math.round(value * 100)}%</span>
      </span>
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

export function NumberField({
  label,
  value,
  min,
  max,
  tooltip,
  onChange,
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  tooltip?: string;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={label} tooltip={tooltip}>
      <input
        type="number"
        step="any"
        min={min}
        max={max}
        value={String(value)}
        onChange={(event) => {
          const nextValue = event.target.value;
          if (nextValue === "") return;
          const parsed = Number(nextValue);
          if (Number.isFinite(parsed)) onChange(parsed);
        }}
        className={fieldClassName}
      />
    </Field>
  );
}

export function Notice({ text }: { text: string }) {
  return (
    <div className="mt-4 flex gap-3 rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-blue-800">
      <Info className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{text}</span>
    </div>
  );
}

export function MetricBox({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="mt-2 text-xl font-semibold text-slate-950">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{hint}</div>
    </div>
  );
}

export function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <span className="text-slate-500">{label}</span>
      <span className="text-right font-medium text-slate-900">{value}</span>
    </div>
  );
}

export function DependencyRow({ label, ok, inactive }: { label: string; ok: boolean; inactive?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className={inactive ? "text-slate-400" : "text-slate-700"}>{label}</span>
      <span
        className={cn(
          "rounded-full px-2.5 py-1 text-xs font-medium",
          inactive ? "bg-slate-100 text-slate-500" : ok ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700",
        )}
      >
        {inactive ? "未启用" : ok ? "已配置" : "需确认"}
      </span>
    </div>
  );
}

const subtitlePresetMeta: Record<SubtitlePosition, { label: string; y: number; desc: string }> = {
  top: { label: "顶部", y: 12, desc: "适合商品画面在下方" },
  middle: { label: "中部", y: 50, desc: "适合画面上下都较干净" },
  bottom: { label: "底部", y: 88, desc: "默认位置，适合口播画面" },
  custom: { label: "自定义", y: 72, desc: "拖动预览字幕记录坐标" },
};

export function SubtitlePositionEditor({
  disabled,
  position,
  customY,
  fontSize,
  hoveredPreset,
  onHoverPreset,
  onPresetChange,
  onCustomYChange,
  onPreviewPointer,
}: {
  disabled: boolean;
  position: SubtitlePosition;
  customY: number;
  fontSize: number;
  hoveredPreset: SubtitlePosition | null;
  onHoverPreset: (position: SubtitlePosition | null) => void;
  onPresetChange: (position: SubtitlePosition) => void;
  onCustomYChange: (value: number) => void;
  onPreviewPointer: (event: PointerEvent<HTMLDivElement>) => void;
}) {
  const effectiveY = position === "custom" ? customY : subtitlePresetMeta[position].y;
  const previewPosition = hoveredPreset ?? position;
  const previewY = previewPosition === "custom" ? effectiveY : subtitlePresetMeta[previewPosition].y;

  return (
    <div className={cn("rounded-lg border border-slate-200 bg-slate-50 p-4", disabled && "opacity-60")}>
      <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="min-w-0">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-950">字幕位置调整</h3>
              <p className="mt-1 text-xs leading-5 text-slate-500">左侧设置位置，右侧拖动视频预览中的字幕条。</p>
            </div>
            <span className="shrink-0 rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">Y {effectiveY}%</span>
          </div>

          <div className="relative mt-4">
            <div className="grid grid-cols-2 gap-2">
              {(Object.keys(subtitlePresetMeta) as SubtitlePosition[]).map((item) => (
                <button
                  key={item}
                  disabled={disabled}
                  aria-pressed={position === item}
                  onMouseEnter={() => onHoverPreset(item)}
                  onMouseLeave={() => onHoverPreset(null)}
                  onClick={() => onPresetChange(item)}
                  className={cn(
                    "group rounded-lg border bg-white px-3 py-2.5 text-left transition hover:border-blue-200 hover:bg-blue-50/50",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-200",
                    position === item ? "border-blue-400 bg-blue-50 text-blue-800 shadow-sm" : "border-slate-200 text-slate-600",
                    disabled && "cursor-not-allowed",
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold">{subtitlePresetMeta[item].label}</span>
                    {position === item ? (
                      <span className="grid h-4 w-4 shrink-0 place-items-center rounded-full bg-blue-600 text-white">
                        <Check size={11} />
                      </span>
                    ) : (
                      <span className="h-4 w-4 shrink-0 rounded-full border border-slate-300 bg-white group-hover:border-blue-300" />
                    )}
                  </span>
                  <span className="mt-1 block text-[11px] leading-4 text-slate-500">
                    Y {item === "custom" ? effectiveY : subtitlePresetMeta[item].y}%
                  </span>
                </button>
              ))}
            </div>
            {hoveredPreset && (
              <div className="absolute left-0 top-24 z-20 w-36 rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
                <MiniSubtitlePreview y={subtitlePresetMeta[hoveredPreset].y} />
                <div className="mt-1 text-center text-[11px] font-medium text-slate-600">{subtitlePresetMeta[hoveredPreset].desc}</div>
              </div>
            )}
          </div>

          <div className="mt-4">
            <RangeField label="垂直位置" value={effectiveY / 100} max={1} onChange={(value) => onCustomYChange(Math.round(value * 100))} />
          </div>
          <div className="mt-3 grid gap-2 text-xs">
            <div className="rounded-lg bg-white p-2 ring-1 ring-slate-200">
              <div className="text-slate-400">字幕位置</div>
              <div className="mt-1 font-medium text-slate-800">{subtitlePositionLabels[position]}</div>
            </div>
            <div className="rounded-lg bg-white p-2 ring-1 ring-slate-200">
              <div className="text-slate-400">自定义纵向坐标</div>
              <div className="mt-1 font-medium text-slate-800">{position === "custom" ? `${effectiveY}%` : "未启用"}</div>
            </div>
          </div>
        </div>

        <div className="min-w-0">
          <div
            className={cn("relative mx-auto aspect-[9/16] max-h-[430px] overflow-hidden rounded-lg border border-slate-200 bg-slate-900", !disabled && "cursor-grab active:cursor-grabbing")}
            onPointerDown={(event) => {
              if (disabled) return;
              event.currentTarget.setPointerCapture(event.pointerId);
              onPreviewPointer(event);
            }}
            onPointerMove={(event) => {
              if (disabled || !event.currentTarget.hasPointerCapture(event.pointerId)) return;
              onPreviewPointer(event);
            }}
            onPointerUp={(event) => {
              if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                event.currentTarget.releasePointerCapture(event.pointerId);
              }
            }}
          >
            <img
              src="/images/subtitle-preview-live-demo.png"
              alt=""
              className="absolute inset-0 h-full w-full object-cover"
              draggable={false}
            />
            <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/35 to-transparent" />
            {[12, 50, 88].map((line) => (
              <div key={line} className="absolute left-0 right-0 border-t border-white/15" style={{ top: `${line}%` }} />
            ))}
            <div
              className="absolute left-1/2 inline-flex w-[82%] -translate-x-1/2 -translate-y-1/2 items-center justify-center gap-2 rounded-lg border border-blue-300 bg-black/55 px-3 py-1.5 text-center text-sm font-semibold text-white shadow-lg"
              style={{
                top: `${previewY}%`,
                fontSize: `${Math.min(Math.max(fontSize, 24), 120) / 4}px`,
              }}
            >
              <Move size={14} />
              这款连衣裙显瘦又好搭
            </div>
            <div className="absolute left-1/2 rounded-full bg-blue-600 px-2 py-0.5 text-[11px] font-medium text-white" style={{ top: `calc(${previewY}% + 22px)`, transform: "translateX(-50%)" }}>
              X 50%, Y {previewY}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MiniSubtitlePreview({ y }: { y: number }) {
  return (
    <div className="relative mx-auto aspect-[9/16] h-24 overflow-hidden rounded-md bg-slate-900">
      <div className="absolute inset-0 bg-gradient-to-b from-slate-600 to-slate-900" />
      <div className="absolute left-1/2 h-1.5 w-16 -translate-x-1/2 rounded-full bg-white" style={{ top: `${y}%` }} />
    </div>
  );
}
