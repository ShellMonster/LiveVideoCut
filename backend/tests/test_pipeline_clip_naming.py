from app.tasks.pipeline import build_clip_basename


def test_build_clip_basename_ignores_unsafe_product_name():
    basename = build_clip_basename(
        0,
        "蓝白 A字版型连衣裙，带有白色荷叶边、红色领结和配套围裙及头饰 裙子",
    )

    assert basename == "clip_000"


def test_build_clip_basename_is_stable_ascii():
    basename = build_clip_basename(12, "多色可选/裤子:黑色?米色*浅蓝")

    assert basename == "clip_012"
