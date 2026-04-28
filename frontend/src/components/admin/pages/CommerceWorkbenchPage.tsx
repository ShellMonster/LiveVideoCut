import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Copy,
  Download,
  FileText,
  Image,
  Loader2,
  Play,
  RefreshCw,
  Settings2,
  Sparkles,
  Wand2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCommerceAction, useCommerceAsset } from "@/hooks/useAdminQueries";
import { useToastStore } from "@/stores/toastStore";
import { API_BASE } from "../api";
import { formatConfidence, formatDuration } from "../format";
import type { CommerceImageItem } from "../types";

type WorkbenchTab = "copywriting" | "model_images" | "detail_page";

const visibleAttributeLabels: Record<string, string> = {
  color: "颜色",
  fit: "版型",
  sleeve: "袖型",
  scene: "场景",
};

export function CommerceWorkbenchPage() {
  const { taskId, segmentId } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState<WorkbenchTab>("model_images");
  const { data, isLoading, isError } = useCommerceAsset(taskId, segmentId);
  const commerceAction = useCommerceAction(taskId, segmentId);
  const showToast = useToastStore((state) => state.showToast);

  const modelImages = useMemo(
    () => data?.images.items.filter((item) => item.key !== "detail_page") ?? [],
    [data?.images.items],
  );
  const detailImage = data?.images.items.find((item) => item.key === "detail_page");

  const copyText = async (text: string, label: string) => {
    if (!text.trim()) {
      showToast(`${label}尚未生成`, "error");
      return;
    }
    await navigator.clipboard.writeText(text);
    showToast(`${label}已复制`, "success");
  };

  if (isLoading) {
    return (
      <main className="flex min-h-[70vh] items-center justify-center p-6">
        <div className="inline-flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          正在加载 AI 商品素材工作台
        </div>
      </main>
    );
  }

  if (isError || !data) {
    return (
      <main className="p-6">
        <button onClick={() => navigate("/assets")} className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-950">
          <ArrowLeft size={16} />
          返回片段资产
        </button>
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
          无法加载该片段的 AI 商品素材信息。
        </div>
      </main>
    );
  }

  const clip = data.clip;
  const thumbnailUrl = `${API_BASE}${clip.thumbnail_url}`;
  const videoUrl = `${API_BASE}${clip.video_url}`;

  return (
    <>
      <header className="border-b border-slate-200 bg-white px-4 py-4 sm:px-6">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <button onClick={() => navigate("/assets")} className="mb-2 inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900">
              <ArrowLeft size={16} />
              片段资产
            </button>
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <span>片段资产</span>
              <span>/</span>
              <span className="max-w-56 truncate">{clip.product_name}</span>
              <span>/</span>
              <span>AI 商品素材</span>
            </div>
            <h1 className="mt-1 truncate text-xl font-semibold text-slate-950">AI 商品素材工作台</h1>
          </div>
          <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-3 xl:w-auto xl:flex xl:flex-wrap xl:items-center">
            <StatusPill label="Gemini 识图" status={data.analysis.status} />
            <StatusPill label="平台文案" status={data.copywriting.status} />
            <StatusPill label="图片生成" status={data.images.status} />
          </div>
        </div>
      </header>

      <main className="grid gap-5 p-4 sm:p-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <div className="relative aspect-video bg-slate-950">
              {clip.has_thumbnail ? (
                <img src={thumbnailUrl} alt="" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full items-center justify-center text-slate-500">
                  <Image size={28} />
                </div>
              )}
              <a
                href={videoUrl}
                target="_blank"
                rel="noreferrer"
                className="absolute left-3 top-3 inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/95 text-slate-900 shadow-sm hover:bg-white"
                aria-label="播放片段"
              >
                <Play size={16} />
              </a>
              <span className="absolute bottom-3 right-3 rounded bg-black/75 px-2 py-1 text-xs font-medium text-white">
                {formatDuration(clip.duration)}
              </span>
            </div>
            <div className="p-4">
              <h2 className="text-base font-semibold text-slate-950">{clip.product_name || "未命名片段"}</h2>
              <p className="mt-1 break-all text-xs text-slate-400">{clip.clip_id}</p>
              <div className="mt-4 grid grid-cols-3 gap-2">
                <MiniMetric label="置信度" value={formatConfidence(clip.confidence)} />
                <MiniMetric label="开始" value={formatDuration(clip.start_time)} />
                <MiniMetric label="结束" value={formatDuration(clip.end_time)} />
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-slate-950">商品识别摘要</h2>
              <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
                {formatConfidence(data.analysis.confidence)}
              </span>
            </div>
            <div className="mt-4 space-y-2">
              <MetadataLine label="品类" value={data.analysis.product_type} />
              {Object.entries(data.analysis.visible_attributes).map(([key, value]) => (
                <MetadataLine key={key} label={visibleAttributeLabels[key] ?? key} value={value} />
              ))}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {data.analysis.uncertain_fields.map((field) => (
                <span key={field} className="rounded-full bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700">
                  {field}待确认
                </span>
              ))}
            </div>
            <button
              onClick={() => commerceAction.mutate("analyze")}
              disabled={commerceAction.isPending}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {commerceAction.isPending ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
              {commerceAction.isPending ? "处理中" : "重新识别"}
            </button>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
              <AlertTriangle size={16} className="text-amber-500" />
              平台规则提醒
            </div>
            <div className="mt-3 space-y-2 text-sm text-slate-600">
              {["标题控制在 30 字内", "避免绝对化宣传词", "材质/尺码需人工确认", "AI 图需标注示意"].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <CheckCircle2 size={14} className="text-emerald-500" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
              <Settings2 size={16} />
              生成参数
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <ParameterChip label="模特风格" value="自然通勤" />
              <ParameterChip label="背景" value="浅色棚拍" />
              <ParameterChip label="尺寸" value="竖图优先" />
              <ParameterChip label="模型" value="gpt-image-2" />
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-slate-950">生成任务</div>
              <StatusPill label="Job" status={data.job?.status ?? data.state.status} />
            </div>
            <div className="mt-3 space-y-2 text-xs text-slate-500">
              <MetadataLine label="当前动作" value={commerceActionText(data.job?.current_action)} />
              <MetadataLine label="当前图片" value={data.job?.current_item || "—"} />
              <MetadataLine label="任务 ID" value={data.job?.celery_id || "—"} />
            </div>
            {data.job?.error && (
              <div className="mt-3 rounded-lg bg-red-50 p-3 text-xs leading-5 text-red-700">
                {data.job.error}
              </div>
            )}
          </section>
        </aside>

        <section className="min-w-0 rounded-lg border border-slate-200 bg-white">
          <div className="flex flex-col gap-3 border-b border-slate-200 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-950">生成结果</h2>
              <p className="mt-0.5 text-xs text-slate-500">{data.state.message ?? "素材状态会在这里同步，长耗时生成会自动轮询更新。"}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => commerceAction.mutate("copywriting")}
                disabled={commerceAction.isPending}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {commerceAction.isPending ? <Loader2 size={15} className="animate-spin" /> : <Wand2 size={15} />}
                {commerceAction.isPending ? "生成中" : "生成文案"}
              </button>
              <button
                onClick={() => commerceAction.mutate("images")}
                disabled={commerceAction.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {commerceAction.isPending ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
                {commerceAction.isPending ? "生成中" : "生成图片"}
              </button>
            </div>
          </div>

          <div className="border-b border-slate-200 px-4">
            <div className="flex gap-6 overflow-x-auto">
              <TabButton active={tab === "copywriting"} onClick={() => setTab("copywriting")} icon={FileText} label="平台文案" />
              <TabButton active={tab === "model_images"} onClick={() => setTab("model_images")} icon={Sparkles} label="AI 模特图" />
              <TabButton active={tab === "detail_page"} onClick={() => setTab("detail_page")} icon={Image} label="详情页示例" />
            </div>
          </div>

          <div className="p-4 sm:p-5">
            {tab === "copywriting" && (
              <div className="grid gap-4 xl:grid-cols-2">
                <CopywritingCard
                  title="抖音短视频"
                  primaryLabel="视频标题"
                  primaryText={data.copywriting.douyin.title}
                  secondaryLabel="描述文案"
                  secondaryText={data.copywriting.douyin.description}
                  tags={data.copywriting.douyin.hashtags}
                  compliance={data.copywriting.douyin.compliance}
                  onCopyTitle={() => copyText(data.copywriting.douyin.title, "抖音标题")}
                  onCopyBody={() => copyText(data.copywriting.douyin.description, "抖音描述")}
                />
                <CopywritingCard
                  title="淘宝商品视频"
                  primaryLabel="商品标题"
                  primaryText={data.copywriting.taobao.title}
                  secondaryLabel="卖点与详情模块"
                  secondaryText={[...data.copywriting.taobao.selling_points, ...data.copywriting.taobao.detail_modules].join("\n")}
                  tags={[]}
                  compliance={data.copywriting.taobao.compliance}
                  onCopyTitle={() => copyText(data.copywriting.taobao.title, "淘宝标题")}
                  onCopyBody={() => copyText([...data.copywriting.taobao.selling_points, ...data.copywriting.taobao.detail_modules].join("\n"), "淘宝详情文案")}
                />
              </div>
            )}

            {tab === "model_images" && (
              <div className="grid gap-4 lg:grid-cols-3">
                {modelImages.map((item) => (
                  <ImageResultCard key={item.key} item={item} onRegenerate={() => commerceAction.mutate("images")} />
                ))}
              </div>
            )}

            {tab === "detail_page" && (
              <div className="grid gap-5 xl:grid-cols-[minmax(280px,420px)_minmax(0,1fr)]">
                <ImageResultCard
                  item={detailImage ?? { key: "detail_page", label: "淘宝详情页示例", status: "not_started", url: "" }}
                  tall
                  onRegenerate={() => commerceAction.mutate("images")}
                />
                <div className="rounded-lg border border-slate-200 p-4">
                  <h3 className="text-sm font-semibold text-slate-950">详情页结构</h3>
                  <div className="mt-4 space-y-3">
                    {["主视觉：商品上身效果", "核心卖点：版型 / 颜色 / 场景", "细节展示：领口 / 袖口 / 面料纹理", "穿搭场景：通勤 / 约会 / 日常", "尺码提示：需人工补充"].map((item, index) => (
                      <div key={item} className="flex gap-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white text-xs font-semibold text-slate-500 ring-1 ring-slate-200">
                          {index + 1}
                        </span>
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </>
  );
}

function StatusPill({ label, status }: { label: string; status: string }) {
  const statusMap: Record<string, { text: string; className: string }> = {
    completed: { text: "已完成", className: "bg-emerald-50 text-emerald-700" },
    queued: { text: "排队中", className: "bg-blue-50 text-blue-700" },
    running: { text: "生成中", className: "bg-blue-50 text-blue-700" },
    partial: { text: "部分完成", className: "bg-amber-50 text-amber-700" },
    failed: { text: "失败", className: "bg-rose-50 text-rose-700" },
    not_started: { text: "待生成", className: "bg-slate-100 text-slate-600" },
  };
  const meta = statusMap[status] ?? statusMap.not_started;
  return (
    <span className={cn("inline-flex min-w-0 items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium", meta.className)}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label} · {meta.text}
    </span>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function MetadataLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-slate-400">{label}</span>
      <span className="min-w-0 truncate font-medium text-slate-800">{value || "—"}</span>
    </div>
  );
}

function ParameterChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-0.5 truncate font-medium text-slate-800">{value}</div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof FileText;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex shrink-0 items-center gap-2 border-b-2 px-1 py-3 text-sm font-medium",
        active ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-900",
      )}
    >
      <Icon size={16} />
      {label}
    </button>
  );
}

function CopywritingCard({
  title,
  primaryLabel,
  primaryText,
  secondaryLabel,
  secondaryText,
  tags,
  compliance,
  onCopyTitle,
  onCopyBody,
}: {
  title: string;
  primaryLabel: string;
  primaryText: string;
  secondaryLabel: string;
  secondaryText: string;
  tags: string[];
  compliance: string[];
  onCopyTitle: () => void;
  onCopyBody: () => void;
}) {
  return (
    <article className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
          {(primaryText || "").length}/30
        </span>
      </div>
      <div className="mt-4 space-y-4">
        <TextBlock label={primaryLabel} value={primaryText || "点击生成文案后显示标题"} onCopy={onCopyTitle} />
        <TextBlock label={secondaryLabel} value={secondaryText || "点击生成文案后显示描述和卖点"} onCopy={onCopyBody} multiline />
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <span key={tag} className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
                {tag}
              </span>
            ))}
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          {compliance.map((item) => (
            <span key={item} className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
              {item}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}

function TextBlock({
  label,
  value,
  onCopy,
  multiline = false,
}: {
  label: string;
  value: string;
  onCopy: () => void;
  multiline?: boolean;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <label className="text-xs font-medium text-slate-500">{label}</label>
        <button onClick={onCopy} className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700">
          <Copy size={13} />
          复制
        </button>
      </div>
      <div
        className={cn(
          "rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700",
          multiline ? "min-h-28 whitespace-pre-line" : "min-h-11",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function ImageResultCard({ item, tall = false, onRegenerate }: { item: CommerceImageItem; tall?: boolean; onRegenerate: () => void }) {
  const completed = item.status === "completed" && item.url;
  const imageUrl = completed ? `${API_BASE}${item.url}` : "";
  return (
    <article className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className={cn("relative bg-slate-100", tall ? "aspect-[3/5]" : "aspect-[4/5]")}>
        {completed ? (
          <img src={imageUrl} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center text-slate-400">
            <Image size={34} />
            <div>
              <div className="text-sm font-medium text-slate-500">{item.label}</div>
              <div className="mt-1 text-xs">点击生成图片后显示结果</div>
            </div>
          </div>
        )}
        <span className="absolute left-3 top-3 rounded-full bg-white/95 px-2 py-1 text-xs font-medium text-slate-700 shadow-sm">
          {statusText(item.status)}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2 p-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-slate-950">{item.label}</h3>
          <p className="mt-0.5 text-xs text-slate-400">{completed ? "可下载使用" : "尚未生成"}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button onClick={onRegenerate} className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50" aria-label="重新生成">
            <RefreshCw size={15} />
          </button>
          <button
            disabled={!completed}
            onClick={() => {
              if (imageUrl) window.open(imageUrl, "_blank", "noopener,noreferrer");
            }}
            className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="下载"
          >
            <Download size={15} />
          </button>
        </div>
      </div>
    </article>
  );
}

function statusText(status: string) {
  if (status === "completed") return "已生成";
  if (status === "running") return "生成中";
  if (status === "failed") return "生成失败";
  return "待生成";
}

function commerceActionText(action?: string) {
  if (action === "analyze") return "Gemini 商品识图";
  if (action === "copywriting") return "平台文案";
  if (action === "images") return "OpenAI Image 生图";
  return "—";
}
