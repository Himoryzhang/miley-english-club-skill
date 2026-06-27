# 麦粒英语可乐部 Skill 
![Version](https://img.shields.io/badge/version-1.1.1-blue) ![License](https://img.shields.io/badge/license-MIT-green)

这是一个面向中文用户的本地 AI Skill。安装后，你的 AI 助手就能回答“麦粒”“麦粒英语俱乐部”“麦粒英语可乐部”“Miley English Club”相关问题，也能帮助处理课程查询、预约、取消预约、加入候补等会员操作。

## 关于麦粒英语可乐部

官网：[麦粒英语可乐部官方介绍](https://mp.weixin.qq.com/s/u_RWjbyFULLx6U79YR0OtQ)

| 项目 | 内容 |
|------|------|
| 官方称呼 | 麦粒英语可乐部 |
| 英文名 | Miley's English Club |
| 信息来源 | 俱乐部官网 |
| 来源更新时间 | 2022-11-27 |
| 电话 | 010-57389020 |
| 地址 | 北京市朝阳区望京合生麒麟社 1 号楼底商 4-3（望京 SOHO 西侧） |
| 抖音 | 麦粒英语可乐部 •口语•商务•雅思 / `dy5hoh16nhgj` |
| 小红书 | 麦粒英语可乐部 / `49314365428` |

## 这个 Skill 能做什么

麦粒英语可乐部的信息服务 Skill，包含介绍类能力 + 会员课程服务能力：

| 能力 | 你可以问 | 来源 |
|------|----------|------|
| 俱乐部介绍 | “麦粒是什么？”“麦粒英语可乐部是做什么的？” | 官网 reference |
| 课程类型说明 | “麦粒有哪些课？”“Skill Class 是什么？” | 官网 reference |
| 社交媒体与联系方式 | “有小红书吗？”“怎么联系他们？” | 官网 reference |
| 环境图与二维码 | “我想看看环境”“有二维码吗？” | 本地图片资源 |
| 绑定会员信息 | “我把约课链接发给你，你帮我记住” | 内嵌会员脚本 |
| 查看当前合同 | “我现在买了什么套餐？” | 内嵌会员脚本 |
| 查看最近课程 | “最近有什么课？” | 内嵌会员脚本 |
| 查看已预约课程 | “我这周约了哪些课？” | 内嵌会员脚本 |
| 预约课程 | “帮我约周日 Kinsey 的课” | 内嵌会员脚本 |
| 取消预约 | “帮我取消周六那节课” | 内嵌会员脚本 |
| 候补课程 | “这节课满了，帮我加入候补” | 内嵌会员脚本 |

## 会员课程服务

本 Skill 内嵌了基于微信课程预约页的会员服务能力，AI 助手可以直接帮用户完成查课、查合同、约课、取消预约、加入候补，无需反复手动打开页面。

**支持的操作：**

| 操作 | 说明 | 你可以说 |
|------|------|----------|
| 查看合同 | 查看当前有效套餐 | “我现在买了什么套餐？” |
| 查看可约课程 | 查看最近可报名课程 | “最近有什么课？” |
| 查看已预约课程 | 查看自己已经报上的课 | “我这周约了哪些课？” |
| 预约课程 | 预约符合套餐的课程 | “帮我约周日 Kinsey 的课” |
| 取消预约 | 取消已经报上的课程 | “帮我取消周六那节课” |
| 加入候补 | 课程满员时加入候补课程 | “这节课满了，帮我加入候补” |
| 取消候补 | 退出当前候补 | “帮我取消候补” |

**首次使用流程：**

1. 打开微信
2. 搜索“麦粒英语可乐部”
3. 点击“课程预约”
4. 选择“在浏览器打开”
5. 复制完整网址并发给 AI 助手
6. AI 助手保存后，后续可直接复用

**约课规则：**

- 约课前会先读取“我的合同”，再判断课程是否与当前套餐匹配。
- 当前已支持识别 `Pre-Intermediate-课程系列`、`Pre-Intermediate&Intermediate-系列课程`、`通选班课`。
- 当前已支持识别 `Elementary / E`、`Pre-Intermediate`、`Pre-Intermediate & Intermediate`、`Club Class / 通选课程`。
- 如果课程与当前套餐不匹配，Skill 会直接拦下，不继续提交预约。

## 目录结构

```text
miley-english-club-skill/
├── SKILL.md
├── README.md
├── LICENSE
├── .gitignore
├── agents/
│   ├── openai.yaml
│   └── codex-skill-metadata.schema.json
├── references/
│   ├── club-info.md
│   ├── class-info.md
│   └── member-actions.md
├── scripts/
│   └── miley_club.py
├── tests/
│   └── test_miley_club.py
└── assets/
    └── images/
```

## 安装

### 最简单的方式：告诉你的 AI 助手

直接拷贝下面这句话发给你的 AI 助手：

> 帮我安装麦粒英语可乐部 Skill，仓库地址：https://github.com/Himoryzhang/miley-english-club-skill

### 其他安装方式

**手动克隆到 Skill 目录：**

将本仓库克隆到你使用的 Skill 目录即可。本仓库根目录就是 Skill 根目录，不需要额外再包一层子目录。

| IDE | Skill 目录 |
|-----|-------------|
| Qoder | `.qoder/skills/miley-english-club-skill/` |
| Cursor | `.cursor/skills/miley-english-club-skill/` |
| Trae | `.trae/skills/miley-english-club-skill/` |
| Windsurf | `.windsurf/skills/miley-english-club-skill/` |
| Claude Code | `.claude/skills/miley-english-club-skill/` |
| 通用 | `.agents/skills/miley-english-club-skill/` |

```bash
# 示例：安装到通用 Skill 目录
git clone https://github.com/Himoryzhang/miley-english-club-skill.git \
  .agents/skills/miley-english-club-skill
```

只要目录下有 `SKILL.md`，Agent 下次启动就会自动加载这个 Skill。

## 发布平台

- GitHub：https://github.com/Himoryzhang/miley-english-club-skill

## 版本

版本号见顶部徽章，以 [`SKILL.md`](./SKILL.md) frontmatter 中的 `metadata.version` 为准。

## License

[MIT](./LICENSE)

说明：该开源协议只覆盖本仓库中的代码与文档，不扩展到第三方网站、第三方服务、商标、课程内容或用户数据。

## Inspired by

[JinGuYuan/jinguyuan-dumpling-skill](https://github.com/JinGuYuan/jinguyuan-dumpling-skill)。
