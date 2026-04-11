from pathlib import Path

from app.services.cleanup import TempFileCleaner


class TestCleanupChunks:
    def test_removes_chunks_dir(self, tmp_path: Path):
        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()
        (chunks_dir / "chunk_001.wav").write_bytes(b"\x00" * 100)
        (chunks_dir / "chunk_002.wav").write_bytes(b"\x00" * 100)

        cleaner = TempFileCleaner()
        cleaner.cleanup_chunks(tmp_path)

        assert not chunks_dir.exists()

    def test_noop_when_no_chunks(self, tmp_path: Path):
        cleaner = TempFileCleaner()
        cleaner.cleanup_chunks(tmp_path)
        assert True


class TestCleanupFrames:
    def test_removes_frame_files(self, tmp_path: Path):
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        (frames_dir / "frame_001.jpg").write_bytes(b"\xff\xd8\xff")
        (frames_dir / "frame_002.png").write_bytes(b"\x89PNG")

        cleaner = TempFileCleaner()
        cleaner.cleanup_frames(tmp_path)

        assert not (frames_dir / "frame_001.jpg").exists()
        assert not (frames_dir / "frame_002.png").exists()

    def test_noop_when_no_frames_dir(self, tmp_path: Path):
        cleaner = TempFileCleaner()
        cleaner.cleanup_frames(tmp_path)
        assert True


class TestCleanupSrt:
    def test_removes_srt_dir(self, tmp_path: Path):
        srt_dir = tmp_path / "srt"
        srt_dir.mkdir()
        (srt_dir / "clip_0.srt").write_text("1\n00:00:00,000 --> 00:00:05,000\nHello")

        cleaner = TempFileCleaner()
        cleaner.cleanup_srt(tmp_path)

        assert not srt_dir.exists()

    def test_removes_root_srt_files(self, tmp_path: Path):
        (tmp_path / "subtitle.srt").write_text("1\n00:00:00,000 --> 00:00:05,000\nHi")

        cleaner = TempFileCleaner()
        cleaner.cleanup_srt(tmp_path)

        assert not (tmp_path / "subtitle.srt").exists()


class TestCleanupAllTemp:
    def test_keeps_clips_and_thumbnails(self, tmp_path: Path):
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "clip_0.mp4").write_bytes(b"\x00" * 50)

        thumbs_dir = tmp_path / "thumbnails"
        thumbs_dir.mkdir()
        (thumbs_dir / "thumb_0.jpg").write_bytes(b"\xff\xd8\xff")

        (tmp_path / "state.json").write_text('{"state": "COMPLETED"}')
        (tmp_path / "meta.json").write_text('{"filename": "test.mp4"}')

        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()
        (chunks_dir / "chunk.wav").write_bytes(b"\x00")

        cleaner = TempFileCleaner()
        cleaner.cleanup_all_temp(tmp_path)

        assert clips_dir.exists()
        assert thumbs_dir.exists()
        assert (tmp_path / "state.json").exists()
        assert (tmp_path / "meta.json").exists()
        assert not chunks_dir.exists()

    def test_removes_temp_files(self, tmp_path: Path):
        (tmp_path / "transcript.json").write_text("{}")
        (tmp_path / "candidates.json").write_text("[]")
        (tmp_path / "video.mp4").write_bytes(b"\x00" * 50)

        cleaner = TempFileCleaner()
        cleaner.cleanup_all_temp(tmp_path)

        assert (tmp_path / "video.mp4").exists()
        assert not (tmp_path / "transcript.json").exists()
        assert not (tmp_path / "candidates.json").exists()


class TestCheckDiskSpace:
    def test_returns_bool(self):
        cleaner = TempFileCleaner()
        result = cleaner.check_disk_space(1024)
        assert isinstance(result, bool)

    def test_small_request_returns_true(self):
        cleaner = TempFileCleaner()
        assert cleaner.check_disk_space(1) is True
