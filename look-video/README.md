---
title: LookV
emoji: 📹
colorFrom: cyan
colorTo: blue
sdk: docker
app_port: 8787
pinned: false
---

# LookV

短名产品：小红书链接 → 飞书结构文档。网页 / PWA App / 微信小程序共用同一套后端。

## 公开地址

- 长期网页（GitHub Pages，电脑关机也在）：仓库 Settings → Pages → Deploy from `docs/`
- 带提取接口的短域名（Render 免费）：**https://lookv.onrender.com**
  1. 打开 https://render.com 用 GitHub 登录
  2. New → Blueprint，选这个仓库，应用根目录的 `render.yaml`
  3. 服务名填 `lookv`，不要填 LLM / Cookie / 飞书密钥
  4. 等 Deploy Live。闲置会休眠，第一次打开大约 30 秒

公开站默认不写飞书。试用反馈会发到作者邮箱，并在有后端时写入 `look-video/data/feedback.jsonl`（Render 免费盘会随休眠清空，以邮箱为准）。

## 本机

```bash
cd look-video
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8787
```

## App

手机 Chrome / Safari 打开网站 → 添加到主屏幕。这就是 LookV App（PWA）。

## 微信小程序

用微信开发者工具导入 `lookv-mp/`。游客 AppID 可预览。上线前：

1. 把 `lookv-mp/config.js` 里的 `apiBase` 改成你的 Render 地址
2. 在小程序后台把该域名加进 request 合法域名
3. 换成你的正式 AppID
