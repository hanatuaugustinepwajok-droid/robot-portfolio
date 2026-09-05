const config = require("../../config.js");

function section(md, name) {
  const re = new RegExp("##\\s*" + name + "[\\s\\S]*?(?=\\n##\\s|$)");
  const m = (md || "").match(re);
  return m ? m[0].trim() : "这一节还没有。";
}

Page({
  data: {
    url: "",
    loading: false,
    status: "",
    err: false,
    tab: "md",
    markdown: "",
    preview: "等待整理…",
    title: ""
  },
  onUrl(e) {
    this.setData({ url: e.detail.value });
  },
  setTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ tab, preview: this.previewOf(tab, this.data.markdown) });
  },
  previewOf(tab, md) {
    if (tab === "sum") return section(md, "逻辑总结");
    if (tab === "core") return section(md, "中心内容");
    return md || "等待整理…";
  },
  demo() {
    this.setData({
      url: "https://www.xiaohongshu.com/explore/6a639a0c0000000011014718"
    });
    this.run(true);
  },
  run(isDemo) {
    const api = config.apiBase;
    if (!api) {
      this.setData({ err: true, status: "请先在 config.js 填 Render 地址" });
      return;
    }
    this.setData({ loading: true, err: false, status: "正在整理…" });
    const body = isDemo
      ? {
          url: this.data.url,
          note: {
            url: this.data.url,
            title: "华裔二代亿万富豪Lucy Guo的创业人生课",
            author: "星野手记",
            type: "video",
            desc: "CMU 计算机，Thiel Fellow。Scale AI 联合创始人，退出运营但留股权。访谈：不是每件事都是风险；人脉是净资产；为学习优化；去问。"
          }
        }
      : { url: this.data.url };
    wx.request({
      url: api.replace(/\/$/, "") + "/api/run",
      method: "POST",
      header: { "content-type": "application/json" },
      data: body,
      success: (res) => {
        const j = res.data || {};
        if (res.statusCode >= 400) {
          const d = j.detail;
          this.setData({
            loading: false,
            err: true,
            status: typeof d === "string" ? d : "整理失败"
          });
          return;
        }
        this.setData({
          loading: false,
          err: false,
          status: "整理完成",
          markdown: j.markdown || "",
          title: j.title || "",
          preview: this.previewOf(this.data.tab, j.markdown || "")
        });
      },
      fail: () =>
        this.setData({
          loading: false,
          err: true,
          status: "连不上服务器。请确认 LookV 已部署且小程序关闭了域名校验。"
        })
    });
  },
  copy() {
    if (!this.data.markdown) return;
    wx.setClipboardData({ data: this.data.markdown });
  }
});
