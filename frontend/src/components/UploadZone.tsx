import { useCallback, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTaskStore } from "@/stores/taskStore";

const API_BASE = import.meta.env.VITE_API_URL || "";

export function UploadZone() {
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { status, progress, error, setTask, setStatus, setError, setProgress, reset } =
    useTaskStore();

  const upload = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".mp4")) {
        setError("请上传 MP4 格式的视频文件");
        return;
      }

      reset();
      setStatus("uploading");

      const form = new FormData();
      form.append("file", file);

      try {
        const xhr = new XMLHttpRequest();

        const done = new Promise<{ task_id: string; metadata: Record<string, unknown> }>(
          (resolve, reject) => {
            xhr.open("POST", `${API_BASE}/api/upload`);
            xhr.onload = () => {
              if (xhr.status >= 200 && xhr.status < 300) {
                resolve(JSON.parse(xhr.responseText));
              } else {
                const body = JSON.parse(xhr.responseText || "{}");
                reject(new Error(body.detail || `上传失败 (${xhr.status})`));
              }
            };
            xhr.onerror = () => reject(new Error("网络错误，请检查连接"));
            xhr.send(form);
          },
        );

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            setProgress(Math.round((e.loaded / e.total) * 100));
          }
        };

        const result = await done;
        setTask(result.task_id, result.metadata);
      } catch (err) {
        setError(err instanceof Error ? err.message : "上传失败");
      }
    },
    [reset, setTask, setStatus, setError, setProgress],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) upload(file);
    },
    [upload],
  );

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) upload(file);
    },
    [upload],
  );

  const isUploading = status === "uploading";

  return (
    <div className="w-full max-w-xl mx-auto p-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={cn(
          "upload-zone flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-12 cursor-pointer transition-colors",
          dragging
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100",
          isUploading && "pointer-events-none opacity-60",
        )}
      >
        <Upload className="h-10 w-10 text-gray-400" />
        <p className="text-sm text-gray-600">
          {isUploading ? "上传中..." : "拖拽 MP4 文件到此处，或点击选择文件"}
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp4"
          onChange={onFileChange}
          className="hidden"
        />
      </div>

      {isUploading && (
        <div className="mt-4">
          <div className="h-2 w-full rounded-full bg-gray-200">
            <div
              className="upload-progress h-2 rounded-full bg-blue-500 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-gray-500 text-right">{progress}%</p>
        </div>
      )}

      {status === "processing" && (
        <p className="mt-4 text-center text-sm text-green-600">
          上传成功！任务处理中...
        </p>
      )}

      {error && (
        <p className="mt-4 text-center text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
