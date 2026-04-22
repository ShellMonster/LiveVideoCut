import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
DEFAULT_BGM = str(ASSETS_DIR / "default_bgm.mp3")
USER_BGM_DIR = Path("/app/uploads/bgm_library")
USER_LIBRARY_PATH = USER_BGM_DIR / "library.json"


class BGMSelector:
    def __init__(self, library_path: str | Path) -> None:
        self._library_path = Path(library_path)
        self._bgm_dir = self._library_path.parent
        self._tracks: list[dict] = []
        self._category_defaults: dict[str, list[str]] = {}
        self._user_dir: Path | None = None
        self._load()

    @classmethod
    def with_user_library(cls, library_path: str | Path) -> "BGMSelector":
        selector = cls(library_path)
        selector._user_dir = USER_BGM_DIR
        if USER_LIBRARY_PATH.exists():
            try:
                user_data = json.loads(USER_LIBRARY_PATH.read_text())
                user_tracks = user_data if isinstance(user_data, list) else user_data.get("tracks", [])
                selector._tracks = user_tracks + selector._tracks
            except Exception:
                logger.exception("Failed to load user BGM library")
        return selector

    def _load(self) -> None:
        if not self._library_path.exists():
            logger.warning("BGM library not found: %s", self._library_path)
            return
        try:
            data = json.loads(self._library_path.read_text())
            self._tracks = data.get("tracks", [])
            self._category_defaults = data.get("category_defaults", {})
        except Exception:
            logger.exception("Failed to load BGM library: %s", self._library_path)

    def _resolve_track_path(self, track: dict) -> str | None:
        filename = track.get("file", "")
        if self._user_dir:
            user_path = self._user_dir / filename
            if user_path.exists():
                return str(user_path)
        builtin_path = self._bgm_dir / filename
        if builtin_path.exists():
            return str(builtin_path)
        return None

    def select_for_segment(self, segment: dict, used_ids: set[str] | None = None) -> str:
        if not self._tracks:
            return DEFAULT_BGM

        product_type = segment.get("product_type", "")
        if not product_type:
            product_name = str(segment.get("product_name", ""))
            product_type = self._infer_type_from_name(product_name)

        preferred_moods = self._category_defaults.get(
            product_type,
            self._category_defaults.get("default", []),
        )

        candidates = []
        for track in self._tracks:
            track_cats = track.get("categories", [])
            track_moods = track.get("mood", [])
            cat_match = product_type in track_cats if product_type else False
            mood_match = bool(set(track_moods) & set(preferred_moods)) if preferred_moods else False
            if cat_match or mood_match:
                candidates.append(track)

        if not candidates:
            candidates = list(self._tracks)

        if used_ids is not None:
            unused = [t for t in candidates if t["id"] not in used_ids]
            if unused:
                candidates = unused

        selected = candidates[0]
        if used_ids is not None:
            used_ids.add(selected["id"])

        resolved = self._resolve_track_path(selected)
        if resolved:
            return resolved

        logger.warning("BGM file missing for track %s, falling back to default", selected.get("id"))
        return DEFAULT_BGM

    @staticmethod
    def _infer_type_from_name(name: str) -> str:
        keywords = [
            "上衣", "毛衣", "衬衫", "T恤", "卫衣", "开衫", "吊带", "背心",
            "裙子", "裙装", "半裙", "连衣裙", "长裙", "短裙",
            "裤子", "裤装", "牛仔裤", "阔腿裤", "短裤",
            "外套", "大衣", "夹克", "风衣", "羽绒服", "棉服",
            "套装", "西装", "连衣裙",
            "美妆", "口红", "粉底", "眼影",
            "配饰", "项链", "耳环", "手链",
        ]
        for kw in keywords:
            if kw in name:
                return kw
        return ""

    @property
    def library_info(self) -> list[dict]:
        return [
            {
                "id": t["id"],
                "title": t.get("title", ""),
                "mood": t.get("mood", []),
                "genre": t.get("genre", ""),
                "tempo": t.get("tempo", ""),
                "energy": t.get("energy", ""),
                "categories": t.get("categories", []),
                "duration_s": t.get("duration_s", 0),
            }
            for t in self._tracks
        ]

    def get_track_path(self, track_id: str) -> str | None:
        for track in self._tracks:
            if track["id"] == track_id:
                return self._resolve_track_path(track)
        return None


DEFAULT_SELECTOR = BGMSelector(ASSETS_DIR / "bgm" / "bgm_library.json")
