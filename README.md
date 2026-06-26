# 麦粒英语可乐部 Skill

这是一个面向中文用户的本地 Skill。

安装后，Agent 可以回答“麦粒”“麦粒英语俱乐部”“麦粒英语可乐部”“Miley English Club”相关问题，也可以在用户提供微信课程预约页完整链接后，帮助用户查看课程、查看已预约课程、预约课程、取消预约、排队等位，并根据“我的合同”自动判断课程是否与当前套餐匹配。

## 这是什么

这个仓库本身就是 Skill 根目录，不需要再额外包一层子目录。

当前 Skill 主要包含两类能力：

- 介绍类：回答俱乐部是什么、有什么课程、适合谁、怎么进一步了解
- 会员类：保存会员信息、读取课程、读取合同、判断套餐是否匹配、执行约课或取消预约

## 能做什么

| 能力 | 你可以这样问 |
| --- | --- |
| 俱乐部介绍 | “麦粒是什么？”“麦粒英语俱乐部是做什么的？” |
| 课程类型说明 | “麦粒有哪些课？”“Skill Class 是什么？” |
| 社交媒体与环境图 | “有小红书吗？”“我想看看环境” |
| 绑定会员信息 | “我把约课链接发给你，你帮我记住” |
| 查看当前合同 / 套餐 | “我现在买了什么套餐？” |
| 查看最近课程 | “最近有什么课？” |
| 查看已预约课程 | “我这周约了哪些课？” |
| 预约课程 | “帮我约周日 Kinsey 的课” |
| 取消预约 | “帮我取消周六那节课” |
| 排队等位 | “这节课满了，帮我排队” |

## 关键特点

- 默认中文回复，偏结果导向，不向普通用户暴露太多技术细节
- 支持多个触发别名：
  - `麦粒`
  - `麦粒英语俱乐部`
  - `麦粒英语可乐部`
  - `Miley English Club`
- 会员能力基于微信约课页真实链路
- 约课前会先检查“我的合同”，避免把不属于当前套餐的课程误判成可约
- 本地保存会员状态，后续无需重复发送链接

## 套餐与约课规则

Skill 会先读取“我的合同”页面，再判断课程是否与当前套餐匹配。

当前已支持识别这些系列：

- `Pre-Intermediate-课程系列`
- `Pre-Intermediate&Intermediate-系列课程`
- `通选班课`

当前已支持识别这些课程类型：

- `Elementary` / `E` 级
- `Pre-Intermediate`
- `Pre-Intermediate & Intermediate`
- `Club Class` / 通选课程

例如：

- 如果用户只买了 `Pre-Intermediate`，则不能预约 `Elementary`
- 如果课程会话里判断为套餐不匹配，Skill 会直接拦下，不继续提交预约请求

## 使用方式

### 1. 介绍类问题

直接问即可，例如：

- “麦粒英语可乐部是什么？”
- “麦粒有什么特点？”
- “怎么联系他们？”

### 2. 会员类问题

第一次使用时，需要让用户提供微信课程预约页完整链接：

1. 打开微信
2. 搜索“麦粒英语可乐部”
3. 点击“课程预约”
4. 选择“在浏览器打开”
5. 复制完整网址并发给 Agent

之后 Agent 会把会员信息保存到本地，后续可直接复用。

## 本地命令

会员相关能力优先使用脚本 [scripts/miley_club.py](./scripts/miley_club.py)：

```bash
# 绑定会员
python3 scripts/miley_club.py bind-member "<完整链接>" --make-default

# 查看已保存会员
python3 scripts/miley_club.py list-members

# 查看当前合同 / 套餐
python3 scripts/miley_club.py show-contracts

# 查看全部课程
python3 scripts/miley_club.py list-courses --status all

# 只看可预约课程
python3 scripts/miley_club.py list-courses --status available

# 只看已预约课程
python3 scripts/miley_club.py list-courses --status registered

# 预约课程
python3 scripts/miley_club.py book-course <CourseGuid>

# 取消预约
python3 scripts/miley_club.py cancel-course <CourseGuid>

# 排队
python3 scripts/miley_club.py join-waitlist <CourseGuid>

# 取消排队
python3 scripts/miley_club.py cancel-waitlist <CourseGuid>
```

## 目录结构

```text
miley-english-club-skill/
├── SKILL.md                         # 核心 Skill 指令与元数据
├── README.md                        # 项目说明
├── .gitignore                       # 本地状态与缓存忽略规则
├── agents/
│   ├── openai.yaml                  # UI 元数据
│   └── codex-skill-metadata.schema.json
├── references/
│   ├── club-info.md                 # 俱乐部介绍
│   ├── class-info.md                # 课程介绍
│   └── member-actions.md            # 会员操作参考
├── scripts/
│   └── miley_club.py                # 本地会员脚本
├── tests/
│   └── test_miley_club.py           # 单元测试
└── assets/
    └── images/                      # 环境图、二维码等资源
```

## 安装

### 最简单的方式

把这个仓库作为 Skill 安装到你的 Skill 目录中，只要目录下有 `SKILL.md`，Agent 就能识别。

通用目录通常是：

```text
.agents/skills/miley-english-club/
```

也可以直接放到当前工作区或工具约定的 Skill 目录中使用。

### 手动克隆

```bash
git clone https://github.com/Himoryzhang/miley-english-club-skill.git
```

## 测试

### Skill 结构校验

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

### 单元测试

```bash
python3 -B -m unittest discover -s tests -v
```

### 真人联调建议

建议按这个顺序测试：

1. 绑定会员链接
2. 查看当前合同
3. 查看最近课程
4. 预约一节确定属于当前套餐的课
5. 尝试预约一节不属于当前套餐的课，确认会被拦下
6. 取消预约

## 信息来源

介绍类内容主要来自俱乐部官网整理的 reference：

- [references/club-info.md](./references/club-info.md)
- [references/class-info.md](./references/class-info.md)

当前仓库中使用的官网链接为：

- [麦粒英语可乐部官方介绍](https://mp.weixin.qq.com/s/u_RWjbyFULLx6U79YR0OtQ)

## 隐私与本地状态

微信课程预约页链接中包含用户敏感会员信息，应视为私密信息。

本项目默认会把本地会员状态保存到本地目录，不应提交到 Git。当前仓库已经通过 `.gitignore` 忽略：

- `.local-state/`

如果你在本地测试，请不要公开分享这些链接或状态文件。

## 当前状态

当前版本能力以 [SKILL.md](./SKILL.md) frontmatter 中的 `metadata.version` 为准。

当前已完成：

- 俱乐部介绍
- 课程介绍
- 社交媒体信息
- 图片资源支持
- 会员绑定
- 查课 / 查已预约
- 合同套餐识别
- 套餐匹配校验
- 约课 / 取消预约
- 排队 / 取消排队

后续可以继续增强的方向：

- 更细的课程筛选与排序
- 更友好的课程摘要输出
- 更完整的请假流程支持
- 更强的多会员管理能力
