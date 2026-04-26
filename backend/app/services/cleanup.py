import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class TempFileCleaner:
    """Cleans up temporary files after processing stages."""

    def cleanup_chunks(self, task_dir: str | Path) -> None:
        """Remove audio chunks after transcription."""
        chunks_dir = Path(task_dir) / "chunks"
        if chunks_dir.exists():
            shutil.rmtree(chunks_dir, ignore_errors=True)
            logger.info("Cleaned up chunks: %s", chunks_dir)

    def cleanup_frames(self, task_dir: str | Path) -> None:
        """Remove extracted frame directory after all downstream reuse is complete."""
        frames_dir = Path(task_dir) / "frames"
        if not frames_dir.exists():
            return
        shutil.rmtree(frames_dir, ignore_errors=True)
        logger.info("Cleaned up frames: %s", frames_dir)

    def cleanup_srt(self, task_dir: str | Path) -> None:
        """Remove SRT files after video export."""
        task_path = Path(task_dir)
        srt_dir = task_path / "srt"
        if srt_dir.exists():
            shutil.rmtree(srt_dir, ignore_errors=True)
            logger.info("Cleaned up SRT: %s", srt_dir)
        for srt_file in task_path.glob("*.srt"):
            srt_file.unlink()

    def cleanup_all_temp(self, task_dir: str | Path) -> None:
        """Remove all temporary files, keep only final clips."""
        task_path = Path(task_dir)
        keep_dirs = {"clips", "thumbnails"}
        keep_files = {"state.json", "error.json", "meta.json", "enriched_segments.json"}

        for item in task_path.iterdir():
            if item.is_dir():
                if item.name not in keep_dirs:
                    shutil.rmtree(item, ignore_errors=True)
                    logger.info("Cleaned up temp dir: %s", item)
            elif item.is_file():
                if item.name not in keep_files and not item.suffix.lower() in (
                    ".mp4",
                    ".mov",
                    ".avi",
                ):
                    item.unlink()
                    logger.info("Cleaned up temp file: %s", item)

    def check_disk_space(self, required_bytes: int) -> bool:
        """Check if enough disk space available (>= required_bytes * 3)."""
        try:
            usage = shutil.disk_usage("/")
            needed = required_bytes * 3
            return usage.free >= needed
        except OSError:
            return True
