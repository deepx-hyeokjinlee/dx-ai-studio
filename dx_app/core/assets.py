"""DX-APP Asset access — files, images, videos, outputs."""

import os
from pathlib import Path
from config import DX_APP_ROOT, SAMPLE_DIR, OUTPUTS_DIR, ASSETS_DIR


def get_file_content(rel):
    try:
        p=(DX_APP_ROOT/rel).resolve()
        if not str(p).startswith(str(DX_APP_ROOT.resolve())):return None
        if p.suffix not in{".hpp",".cpp",".py",".h",".json",".md"}:return None
        return p.read_text(errors="replace")
    except:return None

def get_images():
    d=SAMPLE_DIR/"img"
    if not d.is_dir():return[]
    _img_ext={".jpg",".jpeg",".png",".bmp"}
    out=[]
    for entry in sorted(d.iterdir()):
        if entry.is_file() and entry.suffix.lower() in _img_ext:
            out.append(str(entry.relative_to(DX_APP_ROOT)))
        elif entry.is_dir():
            has_img=any(
                f.is_file() and f.suffix.lower() in _img_ext
                for f in entry.iterdir()
            )
            if has_img:
                out.append(str(entry.relative_to(DX_APP_ROOT)))
    return out

def get_videos():
    d=ASSETS_DIR/"videos"
    if not d.is_dir():return[]
    return[str(f.relative_to(DX_APP_ROOT)) for f in sorted(d.iterdir()) if f.suffix.lower() in{".mp4",".mov",".avi",".mkv"}]

def list_outputs():
    _IMG_EXT={".jpg",".jpeg",".png",".bmp",".webp"}
    _VID_EXT={".mp4",".mov",".avi",".mkv",".webm"}
    _ARC_EXT={".tar",".gz",".tgz",".zip",".tar.gz"}
    items=[]
    for f in OUTPUTS_DIR.iterdir():
        if not f.is_file():continue
        ext=f.suffix.lower()
        name=f.name
        if ext in _IMG_EXT:ftype="image"
        elif ext in _VID_EXT:ftype="video"
        elif any(name.endswith(a) for a in _ARC_EXT):ftype="archive"
        else:ftype="other"
        # Try to find matching source image for Before/After
        src_image=None
        if ftype=="image" and name.startswith("result_"):
            # result_yolov8n_123.jpg → try to find matching input in sample/
            import re
            m=re.match(r'result_([^_]+)_',name)
            if m:
                from config import CAT_IMAGE
                model_hint=m.group(1)
                for cat,img in CAT_IMAGE.items():
                    if model_hint.lower() in cat.lower():
                        src_image=img;break
        items.append({"name":name,"size":f.stat().st_size,"mtime":f.stat().st_mtime,
                       "url":f"/outputs/{name}","type":ftype,"src_image":src_image})
    return sorted(items,key=lambda x:x["mtime"],reverse=True)

def delete_output(name):
    """Delete a single file from the outputs directory."""
    if not name or ".." in name or "/" in name:
        return {"error":"Invalid filename"}
    fp=OUTPUTS_DIR/name
    if not fp.is_file():
        return {"error":"File not found"}
    try:
        fp.unlink()
        return {"ok":True,"deleted":name}
    except Exception as e:
        return {"error":str(e)}
