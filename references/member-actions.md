## 会员操作

来源：ETM 微信约课页 `https://vip4.etmcn.com/WeiXin/selfLesson.aspx`  
提取时间：2026-06-26  
用途：用于会员相关能力的内部参考，不直接把这些技术细节讲给普通用户。

### 什么时候使用

- 用户问“帮我看最近有什么课”“我约了哪些课”“帮我约这节课”“帮我取消这节课”“还能不能排队”等会员问题时使用。
- 这类问题先检查是否已经保存会员信息；没有的话，先让用户提供微信约课页完整链接。

### 绑定会员信息

让用户按这个顺序操作：

1. 打开微信
2. 搜索“麦粒英语可乐部”
3. 点击“课程预约”
4. 选择“在浏览器打开”
5. 复制完整网址并发给 Agent

保存时至少要提取这些字段：

- `openID`
- `lic`
- `memberGuid`
- `MPUserGuid`（如果链接里有就保存，没有就用全零 GUID）
- `pagetype`（如果有）

优先使用脚本：

- `scripts/miley_club.py bind-member "<完整链接>"`

### 统一工作方式

- 不要手写请求，会员相关操作优先走 `scripts/miley_club.py`。
- 先看“我的合同”，确认用户当前可约的课程系列，再进行查课和约课。
- 先查课，再根据返回结果内部选择 `CourseGuid` 等字段执行约课或取消。
- 对用户回复只讲结果，例如“已帮你约上”“这节课已满，可以排队”“你这周还有 4 节可预约课程”，不要讲接口、参数、GUID。

### 我的合同

- 页面入口：`/WeiXin/MyContract.aspx`
- 优先命令：`python3 scripts/miley_club.py show-contracts`
- 当前要点：
  - 合同页会列出用户当前合同中的课程系列
  - 只有合同里包含的课程系列，用户才能预约对应课程
  - 脚本会把不匹配的课程标记为 `套餐不匹配`

当前已验证过的映射：

- `Pre-Intermediate-课程系列` -> `Pre-Intermediate` 课程
- `Pre-Intermediate&Intermediate-系列课程` -> `Pre-Intermediate & Intermediate` 课程
- `通选班课` -> `Club Class` / 通选课程等
- 如果用户没有 `Elementary` 系列，则不能预约 `Elementary` / `E` 级课程

### 关键动作映射

- 查看课程设置：`GetCourseSetting`
- 查看某天课程：`GetCourse`
- 检查是否开放自助约课：`GetAppointmentCourseState`
- 预约课程：`SelectCourse`
- 取消预约：`CancelSelectCourse`
- 排队等位：`createWaitCourse`
- 取消排队：`CancelWaitCourse`
- 请假资格校验：`JudgeLeaveLimitCount`
- 提交请假：`AddLeave`
- 获取本月请假次数：`GetLeaveCount`

### 约课前的额外校验

微信页面在正式调用 `SelectCourse` 前，还会先调用：

- 路径：`/Ashx/GetMemberCourse.ashx`
- `action`: `getcourserolebycardtype`

这个校验会根据 `memberGuid`、课程日期、课程时段判断当前会员卡是否允许约这节课。脚本里应保留这一步。

### 课程状态判断

从课程列表里优先识别这些状态：

- `已预约`
- `审核中`
- `未通过`
- `已请假`
- `请假审核中`
- `可预约`
- `已约满`
- `可排队`
- `已排队`
- `已超时`

对用户表达时尽量口语化，例如：

- “这节课你已经约上了”
- “这节课现在可以直接报名”
- “这节课已经满了，但还能排队”
- “这节课时间已经过了”
