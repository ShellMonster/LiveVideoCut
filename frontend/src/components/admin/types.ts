import type { ClipData } from "@/stores/taskStore";

export type PageKey = "projects" | "create" | "queue" | "review" | "assets" | "music" | "diagnostics" | "settings";

export interface TaskItem {
  task_id: string;
  status: string;
  stage?: string;
  message?: string | null;
  created_at?: string | null;
  original_filename?: string | null;
  display_name?: string | null;
  video_duration_s?: number;
  asr_provider?: string;
  clip_count: number;
  thumbnail_url?: string | null;
}

export interface TaskListResponse {
  items?: TaskItem[];
  total?: number;
  offset?: number;
  limit?: number;
  summary?: {
    total: number;
    processing: number;
    completed: number;
    failed: number;
    uploaded: number;
    clip_count: number;
  };
}

export interface ClipListResponse {
  clips?: ClipData[];
  total?: number;
}

export interface TaskSummary {
  candidates_count: number;
  confirmed_count: number;
  transcript_segments_count: number;
  text_boundaries_count: number;
  fused_candidates_count: number;
  enriched_segments_count: number;
  clips_count: number;
  empty_screen_dropped_estimate: number;
  artifact_status: Record<string, boolean>;
}

export interface DiagnosticReport {
  pipeline: { stage: string; status: string; artifact: string; duration_s?: number | null }[];
  funnel: { label: string; count: number }[];
  warnings: { level: string; message: string }[];
  event_log: { time: string; stage: string; level: string; message: string; file: string }[];
  summary: TaskSummary;
  total_elapsed_s?: number | null;
}

export interface ReviewSegment {
  segment_id: string;
  product_name?: string;
  title?: string;
  start_time: number;
  end_time: number;
  confidence?: number;
  text?: string;
  subtitle_overrides?: { start_time: number; end_time: number; text: string }[];
  review_status: "pending" | "approved" | "skipped" | "needs_adjustment";
}

export interface ReviewData {
  segments: ReviewSegment[];
  transcript: { start_time: number; end_time: number; text: string }[];
}

export interface MusicTrack {
  id: string;
  title: string;
  mood: string[];
  genre: string;
  tempo: string;
  energy: string;
  categories: string[];
  duration_s: number;
  source: "user" | "built-in";
}

export interface ClipAsset {
  clip_id: string;
  task_id: string;
  segment_id: string;
  product_name: string;
  duration: number;
  start_time: number;
  end_time: number;
  confidence: number;
  review_status: ReviewSegment["review_status"];
  file_size: number;
  created_at: string;
  video_url: string;
  preview_url?: string;
  thumbnail_url: string;
  has_video: boolean;
  has_thumbnail: boolean;
  commerce_status?: "not_started" | "partial" | "queued" | "running" | "completed" | "failed";
  commerce_analysis_status?: string;
  commerce_copywriting_status?: string;
  commerce_images_status?: string;
}

export interface ClipAssetsResponse {
  items: ClipAsset[];
  total?: number;
  offset?: number;
  limit?: number;
  summary: {
    total: number;
    pending: number;
    approved: number;
    skipped: number;
    needs_adjustment: number;
    downloadable: number;
    total_size: number;
    commerce_completed?: number;
    commerce_failed?: number;
  };
}

export interface CommerceAnalysis {
  status: "not_started" | "running" | "completed" | "failed";
  provider: string;
  confidence: number;
  product_type: string;
  visible_attributes: Record<string, string>;
  selling_points: string[];
  uncertain_fields: string[];
  updated_at: string;
}

export interface CommerceCopywriting {
  status: "not_started" | "running" | "completed" | "failed";
  douyin: {
    title: string;
    description: string;
    hashtags: string[];
    compliance: string[];
  };
  taobao: {
    title: string;
    selling_points: string[];
    detail_modules: string[];
    compliance: string[];
  };
  updated_at: string;
}

export interface CommerceImageItem {
  key: string;
  label: string;
  status: "not_started" | "running" | "completed" | "failed";
  url: string;
}

export interface CommerceImages {
  status: "not_started" | "running" | "completed" | "failed";
  items: CommerceImageItem[];
  updated_at: string;
}

export interface CommerceAssetResponse {
  clip: Omit<ClipAsset, "review_status" | "file_size" | "created_at">;
  analysis: CommerceAnalysis;
  copywriting: CommerceCopywriting;
  images: CommerceImages;
  state: {
    status: "not_started" | "queued" | "running" | "completed" | "failed" | "partial";
    message?: string;
  };
  job?: {
    status?: "queued" | "running" | "completed" | "failed";
    actions?: string[];
    current_action?: string;
    current_item?: string;
    message?: string;
    error?: string;
    celery_id?: string;
    updated_at?: string;
  };
}

export interface CommerceBatchResponse {
  accepted: {
    task_id: string;
    segment_id: string;
    status: "queued";
    job?: CommerceAssetResponse["job"];
  }[];
  rejected: {
    clip_id: string;
    detail: string;
  }[];
  total: number;
}

export interface SystemResources {
  cpu_cores: number;
  memory_gb: number;
  clip_workers: number;
  frame_workers: number;
  queue: {
    waiting: number;
    active: number;
    completed: number;
    failed: number;
  };
  redis: string;
}

export interface ClipReprocessJob {
  status?: "queued" | "running" | "completed" | "failed";
  celery_id?: string;
  queued_at?: string;
  started_at?: string;
  finished_at?: string;
  error?: string;
  updated_at?: string;
}
