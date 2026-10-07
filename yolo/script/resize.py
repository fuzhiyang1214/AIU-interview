# resize.py
# 图片批量预处理：把手机原图缩小到统一尺寸，并顺手「摆正」EXIF 方向。
#
# 为什么要做这一步：
#   1. 手机原图单张 3~4 MB，几百张会把仓库撑到几百 MB；
#      而 YOLO 训练时本来就会缩到 640，先缩到长边 1280 信息量丝毫不损。
#   2. 手机竖拍的照片像素是横的、靠 EXIF 标记旋转显示。这一步把旋转
#      「烧进」像素并清掉 EXIF，之后标注就不会再出现方向错乱、宽高对不上的问题。
#
# 用法：
#   python resize.py                       # 默认处理 ../your_data2，长边 1280
#   python resize.py --src ../your_data2 --long 1280
#   python resize.py --dry-run             # 只看会处理哪些，不写文件
#
# 注意：--src 的相对路径是按「本脚本所在目录」解析的（与 json2txt.py / DataProess.py
#       保持一致），所以在哪个目录下执行本脚本都一样。

import argparse
from pathlib import Path

from PIL import Image, ImageOps

SCRIPT_DIR = Path(__file__).parent
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def resize_one(path: Path, long_side: int, quality: int, dry_run: bool) -> tuple[int, int] | None:
    """缩小单张图片（原地覆盖），返回 (原长边, 新长边)；已够小则返回 None。"""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)  # 按 EXIF 摆正，并丢弃方向标记
        w, h = im.size
        cur_long = max(w, h)
        if cur_long <= long_side:
            return None

        scale = long_side / cur_long
        new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
        if dry_run:
            return cur_long, max(new_size)

        im = im.convert("RGB") if path.suffix.lower() in {".jpg", ".jpeg"} else im
        im = im.resize(new_size, Image.LANCZOS)

        save_kwargs = {"quality": quality, "optimize": True} if path.suffix.lower() in {".jpg", ".jpeg"} else {}
        im.save(path, **save_kwargs)  # 覆盖原文件（手机里还有原始照片）
        return cur_long, max(new_size)


def main() -> None:
    ap = argparse.ArgumentParser(description="批量缩小图片并摆正 EXIF 方向")
    ap.add_argument("--src", default="../your_data2",
                    help="图片目录（相对路径按本脚本所在目录解析），默认 ../your_data2")
    ap.add_argument("--long", type=int, default=1280, help="目标长边像素，默认 1280")
    ap.add_argument("--quality", type=int, default=90, help="JPEG 质量，默认 90")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.is_absolute():          # 相对路径统一按脚本所在目录解析
        src = SCRIPT_DIR / src
    src = src.resolve()
    if not src.is_dir():
        print(f"[缩图] 目录不存在：{src}")
        return

    files = [p for p in sorted(src.iterdir()) if p.suffix.lower() in IMG_EXT]
    if not files:
        print(f"[缩图] {src} 里没有图片")
        return

    # 顺手提示手机常见格式问题
    heic = [p for p in src.iterdir() if p.suffix.lower() in {".heic", ".heif"}]
    if heic:
        print(f"[缩图] ⚠️ 发现 {len(heic)} 个 HEIC/HEIF 文件（Pillow 不支持读取）")
        print("        iPhone 请在「设置 → 相机 → 格式」选「兼容性最佳」，或先转成 JPG")

    before_total = sum(p.stat().st_size for p in files)
    changed = 0
    for p in files:
        r = resize_one(p, args.long, args.quality, args.dry_run)
        if r:
            changed += 1
            print(f"[缩图] {p.name}: 长边 {r[0]} → {r[1]}")

    after_total = sum(p.stat().st_size for p in files)
    print(f"\n[缩图] 共 {len(files)} 张，处理 {changed} 张"
          f"（长边 > {args.long} 的）")
    print(f"[缩图] 目录体积 {before_total/1e6:.1f} MB → {after_total/1e6:.1f} MB")
    if args.dry_run:
        print("[缩图] 这是 dry-run，未写入任何文件")


if __name__ == "__main__":
    main()
