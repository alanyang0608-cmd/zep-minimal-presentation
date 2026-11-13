# 内容契约 / Content contract

`scripts/build.py`中的校验器是实际执行标准。输入UTF-8 JSON；未知字段会报错。字段均为纯文本，不支持Markdown或HTML。标题可用`\n`作语义换行。可先运行`--check`，错误会指出字段位置。

## 顶层

| 字段 | 含义 |
| --- | --- |
| `title` | 必填，演示总标题，最多100字符 |
| `theme` | blue-note / paper-grid / midnight / mono-signal / acid-notes；生成时必须指定，或显式传入`--theme`。没有默认值，先让用户选择 |
| `language` | zh-CN或en；设置文档语言，默认为zh-CN |
| `footer` | 可选，短署名/组织/主题，最多160字符；不填写则不显示 |
| `subtitle` | 可选，材料说明；封面副标题另写在封面页中 |
| `slides` | 1–100页；每页是下面一种类型 |

## 所有页面共有

- `id`：必填，稳定、唯一，最多64字符。用于目录目标，改页序不必改它。
- `type`：必填，从下表选；`title`必填，普通页不超过48字符，封面/观点/章节/提问/结束页不超过72字符。
- `kicker`：可选短栏目标签，最多45字符。`body`：可选短说明，最多170字符。
- `notes`：可选讲者提示，最多4000字符。它会进入HTML，**不是保密区域**；公开稿也要检查。
- `sources`：可选`[{"label":"来源说明","url":"https://…"}]`，仅允许HTTPS且无用户名密码；展示为提示中的外链，不在运行时自动请求。
- `tone`：auto / light / dark / accent。新建标准稿省略或用auto，由模板固定决定背景；不得仅因agent的审美判断加入dark/accent。继续已确认稿件保留原设置；用户明确要求某页背景变化时可使用其他值，并记录所改页。示例使用auto展示按页型选择的背景。见[背景规则](color-consistency.md)。
- `emphasis`：可选标题短语数组，最多3项，每项≤32字符；必须完整出现在某一个标题行中。仅做主题内的语义强调，不接受自定义颜色或HTML。例如`"emphasis":["一个问题"]`。
- `motion`：static / words / list / metrics / timeline / draw。默认由页型决定；作品/截图通常static。

## 十五种页型

| type | 额外字段 | 数量与内容约束 | 默认动效 |
| --- | --- | --- | --- |
| cover | subtitle | 一句主张与简短副标题 | words |
| contents | items | 2–7项，每项title与target，target必须存在 | list |
| statement | subtitle | 一句观点/问题，可语义换行 | words |
| columns | items | 2–4项，每项title、可选body | list |
| metrics | items | 2–4项，每项title、value（字符串）、unit、可选body；不按大小画柱 | metrics |
| ratio | value、total、basis、dots、caption、unit | 数值非负、total>0、value≤total；basis必填。dots为0或1–100整数 | metrics |
| timeline | items | 2–5项，每项label（日期/阶段）、title、可选body；顺序来自内容 | timeline |
| process | items | 2–5项，每项title与可选body，箭头表示真实推进关系 | timeline |
| comparison | items | 恰好2项，每项title、可选body；不预设哪边更好 | list |
| chart | values、labels、basis、unit、caption | 2–8个非负有限数，标签同长度；等间隔序列，basis必填 | draw |
| gallery | items | 1–3项；单项为大图与说明；title；image或art二选一；可选body | static |
| end | subtitle | 结论、问题或下一步行动 | static |
| section | items（可选）、active、subtitle | 章节标题；若有目录则2–7项，title/target；active必须对应菜单中的target | 有目录list，无目录words |
| rows | items | 2–4个条目，标题在左、解释逐行在右 | list |
| dialogue | items | 主标题是一句提问/指令，下面2–3项解释 | words |

`items`字段预算：title32、body95、value14、unit12、label20字符。预算只是输入防护；横向四栏的英文长词、中文密集句仍可能需要拆页。不得为了过校验而删除必要限定条件；移到合适页面或讲者提示，并保留主画面的必要说明。

## 比例与图表

比例由`value / total`计算。`dots: 20`代表20个等份点；例如8/10会生成16个实心点。1/3无法用20个完整点精确表示，校验器会拒绝；改成兼容总数或`dots: 0`比例条。比例文字保留最多一位小数，底层长度使用原数；basis应明确口径、是否估计与数据时间。

chart用于**等间隔数值序列**，不自动解析日期。若输入不规则的日历时间，先准确制图再作为gallery本地图片使用，或明确扩展带日期坐标的页型。图形不做平滑拟合、不插值造数、不随机滚动数值。负数或双轴图超出当前能力，需扩展或导入正确的图像。

## 图片与内置示意

gallery可以使用：

```json
{"title":"案例标题","image":"media/figure.png","alt":"图像内容描述","credit":"作者或组织 · 使用依据","body":"这张图证明什么"}
```

图片须在JSON所在目录或子目录中，PNG/JPEG/WebP，单张不超过10MiB。生成器嵌入图片，无运行时外链；不接受远程图像地址、越出目录的路径、SVG或任意HTML。alt与credit必填，但校验器不能替你判断真实授权。截图仍需人工检查个人信息和文档元信息。

无外部素材时，可用本包绘制的`art: "layers" | "route" | "window"`，并明确它是示意。不能拿示意充当真实产品截图或实证结果。

## 内容计划检查

先回答三件事，再填写JSON：这页讲什么；用什么证据；观众应按什么顺序看。复杂任务可另存简短page-plan，不要求额外固定格式。无依据时保留问题或标注待补资料，不生成看似真实的客户、引用或成绩。

## 演讲编排提示

`--check`在结构校验外会打印非阻塞的ADVICE：较长稿件没有独立观点、连续四页都是columns、statement又附带body。它不修改内容、不规定必须加入多少观点或黑页；有意采用相同版式或只展示作品时可保留。判断依据是材料与演讲目标。

单句观点一般只填title、kicker、notes，可使用emphasis；不要为满足样例把subtitle也补满。真实产品/作品单图使用gallery的一项image，保留alt与credit，其他图片校验规则不变。通用生成器不包含设备专属操作图，需来自用户材料或另行准确绘制。
