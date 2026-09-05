from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from prompt import ORGANIZE_SYSTEM

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
FEISHU_FOLDER = os.environ.get("LOOK_VIDEO_FOLDER", "FuigfwVjjldKMbdJAxrcMHStn3D")

app = FastAPI(title="LookV", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExtractIn(BaseModel):
    url: str = ""
    cookie: str = ""
    note: dict | None = None


class OrganizeIn(BaseModel):
    extract: dict
    api_key: str = ""
    api_base: str = ""
    model: str = ""


class RunIn(BaseModel):
    url: str = ""
    cookie: str = ""
    note: dict | None = None
    api_key: str = ""
    api_base: str = ""
    model: str = ""
    push_feishu: bool = False


class FeishuIn(BaseModel):
    title: str
    markdown: str
    folder_token: str = Field(default="")


def _headers(cookie: str = "") -> dict:
    h = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.xiaohongshu.com/",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if cookie:
        h["Cookie"] = cookie
    return h


def _parse_initial_state(html: str) -> dict | None:
    m = re.search(
        r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>",
        html,
        re.S,
    )
    if not m:
        return None
    raw = m.group(1).replace("undefined", "null")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _note_from_state(state: dict, url: str) -> dict | None:
    mapping = (state.get("note") or {}).get("noteDetailMap") or {}
    if not mapping:
        return None
    first = next(iter(mapping.values()))
    note = (first or {}).get("note") or first or {}
    user = note.get("user") or {}
    interact = note.get("interactInfo") or {}
    tags = [t.get("name") if isinstance(t, dict) else str(t) for t in (note.get("tagList") or [])]
    images = []
    for img in note.get("imageList") or []:
        url_img = (
            img.get("urlDefault")
            or img.get("url")
            or (img.get("infoList") or [{}])[-1].get("url")
        )
        if url_img:
            images.append(url_img)
    video = note.get("video") or {}
    media = video.get("mediaV2") or video.get("media") or {}
    if isinstance(media, str):
        try:
            media = json.loads(media)
        except json.JSONDecodeError:
            media = {}
    subs = ((media.get("subtitles") if isinstance(media, dict) else None) or {}) if media else {}
    return {
        "url": url,
        "noteId": note.get("noteId") or note.get("id") or "",
        "type": note.get("type") or "normal",
        "title": (note.get("title") or "").strip(),
        "desc": (note.get("desc") or "").strip(),
        "author": user.get("nickname") or user.get("nickName") or "",
        "tags": [t for t in tags if t],
        "likes": interact.get("likedCount") or interact.get("likeCount") or "",
        "collects": interact.get("collectedCount") or "",
        "comments": interact.get("commentCount") or "",
        "images": images,
        "subtitles": subs,
        "duration": (video.get("capa") or {}).get("duration") or video.get("duration") or "",
    }


def extract_note(url: str, cookie: str = "") -> dict:
    if not url.strip():
        raise HTTPException(400, "请粘贴小红书链接")
    with httpx.Client(follow_redirects=True, timeout=25.0, headers=_headers(cookie)) as client:
        r = client.get(url.strip())
    html = r.text
    if "登录" in html and "noteDetailMap" not in html and len(html) < 8000:
        raise HTTPException(
            401,
            "小红书需要登录。请在设置里填 Cookie，或用书签工具在已打开的笔记页一键导入。",
        )
    state = _parse_initial_state(html)
    note = _note_from_state(state, str(r.url)) if state else None
    if not note or (not note.get("title") and not note.get("desc")):
        title = re.search(r"<title>([^<]+)</title>", html)
        raise HTTPException(
            422,
            "没有读到笔记正文（常见原因：链接缺 xsec_token，或页面被跳到发现页）。"
            + (f" 当前标题：{(title.group(1) if title else '').strip()}" if title else ""),
        )
    return note


def heuristic_organize(ext: dict) -> str:
    title = ext.get("title") or "未命名笔记"
    author = ext.get("author") or "未知"
    ntype = "视频" if ext.get("type") == "video" else "图文"
    url = ext.get("url") or ""
    desc = (ext.get("desc") or "").strip()
    paras = [p.strip() for p in re.split(r"\n+", desc) if p.strip() and not p.strip().startswith("#")]
    if not paras:
        paras = ["原文描述几乎只有标签。若是外刊图文，需要图片 OCR 后再整理。"]
    body_parts = []
    for i, p in enumerate(paras):
        heading = "开篇" if i == 0 else f"第{i + 1}节"
        body_parts.append(f"### {heading}\n\n{p}\n")
    summary = paras[0][:180]
    cores = paras[-3:] if len(paras) > 1 else paras
    core_md = "\n".join(f"{i + 1}. {c[:160]}" for i, c in enumerate(cores))
    return f"""# {title}

作者：{author}　类型：{ntype}　来源：[{url}]({url})

## 逻辑总结

{summary}

这篇笔记的结构按原文顺序展开。若要更接近访谈精修，请在设置中填入大模型 API Key。

## 正文

{''.join(body_parts)}
### 收束

以上为中文去重后的原文要点，未添加原文没有的情节。

## 中心内容

{core_md}
"""


def llm_organize(ext: dict, api_key: str, api_base: str, model: str) -> str:
    key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        return heuristic_organize(ext)
    base = (api_base or os.environ.get("LLM_API_BASE") or "https://api.deepseek.com").rstrip("/")
    mdl = model or os.environ.get("LLM_MODEL") or "deepseek-chat"
    payload = {
        "model": mdl,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": ORGANIZE_SYSTEM},
            {
                "role": "user",
                "content": "请整理下面这条笔记：\n" + json.dumps(ext, ensure_ascii=False)[:24000],
            },
        ],
    }
    url = base + "/v1/chat/completions"
    with httpx.Client(timeout=90.0) as client:
        r = client.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(502, f"模型接口失败：{r.status_code} {r.text[:400]}")
    data = r.json()
    text = data["choices"][0]["message"]["content"].strip()
    text = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", text).strip()
    return text


def markdown_title(md: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.M)
    return (m.group(1).strip() if m else fallback)[:80]


def lark_available() -> bool:
    return bool(shutil.which("lark-cli"))


def push_feishu(title: str, markdown: str, folder_token: str = "") -> dict:
    if not lark_available():
        raise HTTPException(501, "服务器上没有 lark-cli。本机运行 Look Video 才能一键同步飞书。")
    folder = folder_token or FEISHU_FOLDER
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "doc.md"
        path.write_text(markdown, encoding="utf-8")
        # lark-cli only accepts relative @ paths from cwd
        cmd = [
            "lark-cli",
            "docs",
            "+create",
            "--as",
            "user",
            "--doc-format",
            "markdown",
            "--parent-token",
            folder,
            "--title",
            title,
            "--content",
            f"@./doc.md",
        ]
        proc = subprocess.run(cmd, cwd=td, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise HTTPException(502, (proc.stderr or proc.stdout or "飞书创建失败")[:800])
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"raw": proc.stdout}
    if not out.get("ok"):
        raise HTTPException(502, json.dumps(out, ensure_ascii=False)[:800])
    doc = (out.get("data") or {}).get("document") or {}
    return {"url": doc.get("url"), "document_id": doc.get("document_id"), "title": title}


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "product": "LookV",
        "lark_cli": lark_available(),
        "public": not lark_available(),
        "llm_env": bool(
            os.environ.get("LLM_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        ),
    }


class FeedbackIn(BaseModel):
    score: str = ""
    text: str = ""
    contact: str = ""


@app.post("/api/feedback")
def api_feedback(body: FeedbackIn):
    if not (body.text or "").strip():
        raise HTTPException(400, "请写一句反馈")
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    row = {
        "at": datetime.now(timezone.utc).isoformat(),
        "score": (body.score or "")[:20],
        "text": body.text.strip()[:2000],
        "contact": (body.contact or "").strip()[:80],
    }
    with (data_dir / "feedback.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True}


@app.post("/api/extract")
def api_extract(body: ExtractIn):
    if body.note:
        note = dict(body.note)
        note.setdefault("url", body.url)
        return {"ok": True, "extract": note}
    return {"ok": True, "extract": extract_note(body.url, body.cookie)}


@app.post("/api/organize")
def api_organize(body: OrganizeIn):
    md = llm_organize(body.extract, body.api_key, body.api_base, body.model)
    return {"ok": True, "markdown": md, "title": markdown_title(md, body.extract.get("title") or "笔记")}


@app.post("/api/run")
def api_run(body: RunIn):
    if body.note:
        ext = dict(body.note)
        ext.setdefault("url", body.url)
    else:
        ext = extract_note(body.url, body.cookie)
    md = llm_organize(ext, body.api_key, body.api_base, body.model)
    title = markdown_title(md, ext.get("title") or "笔记")
    result = {"ok": True, "extract": ext, "markdown": md, "title": title, "feishu": None}
    if body.push_feishu and lark_available() and os.environ.get("ALLOW_PUBLIC_FEISHU") == "1":
        result["feishu"] = push_feishu(title, md)
    return result


@app.post("/api/feishu")
def api_feishu(body: FeishuIn):
    if os.environ.get("ALLOW_PUBLIC_FEISHU") != "1":
        raise HTTPException(403, "公开试用已关闭写入飞书，请复制 Markdown 自己粘贴。")
    return {"ok": True, **push_feishu(body.title, body.markdown, body.folder_token)}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/sw.js")
def sw():
    return FileResponse(STATIC / "sw.js", media_type="application/javascript")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
