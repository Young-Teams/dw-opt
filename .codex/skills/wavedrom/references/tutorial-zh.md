# WaveDrom 中文教程

本教程聚焦数字时序波形。WaveDrom 使用 WaveJSON 描述图形；命令行工具读取 JSON5，并输出 SVG。

## 目录

- [1. 最小示例](#1-最小示例)
- [2. wave 字符](#2-wave-字符)
- [3. 时钟与总线](#3-时钟与总线)
- [4. 分组与时间控制](#4-分组与时间控制)
- [5. 标题与时间刻度](#5-标题与时间刻度)
- [6. 节点、箭头与说明](#6-节点箭头与说明)
- [7. 完整事务示例](#7-完整事务示例)
- [8. 渲染与网页嵌入](#8-渲染与网页嵌入)
- [9. 排错清单](#9-排错清单)
- [10. 官方资料](#10-官方资料)

## 1. 最小示例

把以下内容保存为 `basic.json5`：

```json5
{
  signal: [
    { name: 'clk',   wave: 'p.......' },
    { name: 'reset', wave: '10......' },
    { name: 'valid', wave: '0..1..0.' },
  ],
}
```

每个 `signal` 元素是一条波形泳道。`name` 是左侧标签，`wave` 从左到右描述状态。通常每个字符占一个时间格；`.` 延续前一状态。

渲染为 SVG：

```bash
wavedrom --input basic.json5 --indent 2 > basic.svg
```

也可使用 skill 自带脚本。它避免失败时留下半截输出文件：

```bash
.codex/skills/wavedrom/scripts/render-wave.sh basic.json5 basic.svg
```

## 2. wave 字符

常用字符如下：

| 字符 | 含义 | 常见用途 |
| --- | --- | --- |
| `0` | 低电平 | 拉低、无效状态 |
| `1` | 高电平 | 拉高、有效状态 |
| `.` | 延续上一状态 | 保持多个周期 |
| `x` | 未知或无效 | 初始化、总线无效期 |
| `z` | 高阻态 | 三态总线、未驱动引脚 |
| `=` | 总线数据段 | 配合 `data` 显示值 |
| `2`…`9` | 不同颜色的数据段 | 区分连续总线字段 |
| `p` / `n` | 周期性正相/负相时钟 | 连续时钟 |
| `P` / `N` | 带有效边沿标记的时钟 | 强调采样边沿 |
| `h` / `l` | 高/低电平时钟片段 | 时钟门控或拼接 |
| `H` / `L` | 带边沿标记的高/低片段 | 强调局部边沿 |
| `|` | 时间间隙 | 省略中间一段时间 |

`u`、`d` 可表达模拟式上升/下降过渡，但普通 RTL 时序图通常优先使用 `0`、`1` 和时钟字符。

示例：

```json5
{
  signal: [
    { name: 'enable', wave: '0.1...0.' },
    { name: 'tri',    wave: 'z..1..z.' },
    { name: 'state',  wave: 'x.2.3.x.', data: ['IDLE', 'RUN'] },
  ],
}
```

总线的每个新数据段都消费一个 `data` 标签。`.` 只延长当前段，不消费标签。

## 3. 时钟与总线

### 时钟

```json5
{
  signal: [
    { name: 'clk',     wave: 'p.......' },
    { name: 'clk_n',   wave: 'n.......' },
    { name: 'gclk',    wave: '0..ph..0' },
    { name: 'sample',  wave: '0...1.0.' },
  ],
}
```

`p` 和 `n` 会在一个时间格内画出完整时钟周期。混入 `h`、`l`、`0`、`1` 可表现门控或停止的时钟。

### 总线

```json5
{
  signal: [
    { name: 'addr', wave: 'x.=...=x', data: ['0x10', '0x14'] },
    { name: 'data', wave: 'x..=...x', data: ['0xCAFE'] },
  ],
}
```

`data` 既可写数组，也可写空格分隔的字符串；含空格或复杂文本时优先使用数组。

## 4. 分组与时间控制

### 分组

数组的第一个元素是组名，后续元素是泳道或嵌套组：

```json5
{
  signal: [
    { name: 'clk', wave: 'p.......' },
    ['Request channel',
      { name: 'valid', wave: '0.1...0.' },
      { name: 'ready', wave: '0...1...' },
      { name: 'addr',  wave: 'x.=...x.', data: ['0x20'] },
    ],
    {},
    ['Response channel',
      { name: 'done',  wave: '0.....1.' },
    ],
  ],
}
```

空对象 `{}` 插入视觉分隔行。

### period 与 phase

- `period`: 缩放一条泳道的周期宽度，例如 `period: 2`。
- `phase`: 水平平移泳道；`phase: 0.5` 常用于半周期对齐。

```json5
{
  signal: [
    { name: 'clk',  wave: 'p....', period: 2 },
    { name: 'data', wave: 'x.=..', data: ['D0'], phase: 0.5 },
  ],
}
```

先统一时间格，再使用 `phase`。过度依赖不同 `period` 和 `phase` 会使源文件难以维护。

### 间隙与水平缩放

在所有相关泳道的相同位置放置 `|`，表示省略的一段时间：

```json5
{
  signal: [
    { name: 'clk',  wave: 'p...|..' },
    { name: 'busy', wave: '01..|.0' },
  ],
  config: { hscale: 2 },
}
```

`config.hscale` 使用大于 0 的整数扩大水平尺寸。

## 5. 标题与时间刻度

`head` 和 `foot` 分别控制图上方与下方的文字、刻度：

```json5
{
  signal: [
    { name: 'clk',  wave: 'p.......' },
    { name: 'req',  wave: '0.1...0.' },
    { name: 'ack',  wave: '0...1.0.' },
  ],
  head: {
    text: 'Request / Acknowledge timing',
    tick: 0,
    every: 1,
  },
  foot: {
    text: 'One column = one clock cycle',
  },
}
```

- `tick` 把数字放在竖直时间边界上。
- `tock` 把数字放在时间格中间。
- `every` 每隔 N 格显示一个编号。
- `text` 添加标题或图注。

## 6. 节点、箭头与说明

在泳道的 `node` 字符串中放置单字符节点名；`.` 表示该时间格没有节点。随后在顶层 `edge` 中连接节点：

```json5
{
  signal: [
    { name: 'req', wave: '0.1....0', node: '..a.....' },
    { name: 'ack', wave: '0...1..0', node: '....b...' },
  ],
  edge: [
    'a~>b 2-cycle latency',
  ],
}
```

常用连接样式：

| 写法 | 效果 |
| --- | --- |
| `a->b` | 直线箭头 |
| `a~>b` | 曲线箭头 |
| `a<->b` | 双向直线箭头 |
| `a<~>b` | 双向曲线箭头 |
| `a-|>b` | 带直角转折的箭头 |
| `a-b label` | 直线并附文字 |

节点字符应唯一，并与 `wave` 的目标时间格对齐。若半周期节点发生偏移，可为相应泳道添加 `phase`，渲染后再核对。

## 7. 完整事务示例

下面展示一个简化的 valid/ready 写事务。握手在 `valid` 与 `ready` 同时为高的周期发生：

```json5
{
  signal: [
    { name: 'clk',    wave: 'P.......' },
    { name: 'reset_n',wave: '01......' },
    ['Write request',
      { name: 'valid', wave: '0.1...0.', node: '..a.....' },
      { name: 'ready', wave: '0...1...', node: '....b...' },
      { name: 'addr',  wave: 'x.=...x.', data: ['0x1000'] },
      { name: 'wdata', wave: 'x.=...x.', data: ['0xDEADBEEF'] },
    ],
    {},
    { name: 'done', wave: '0.....10', node: '......c.' },
  ],
  edge: [
    'a~>b wait for ready',
    'b~>c response',
  ],
  head: {
    text: 'Single write transaction',
    tick: 0,
  },
  config: { hscale: 2 },
}
```

建图时先在纸面或注释中确定逐周期表，再写 `wave`。例如：复位释放在第 1 格、`valid` 在第 2 格拉高、`ready` 在第 4 格拉高。这样可减少仅凭字符串长度猜测导致的错位。

## 8. 渲染与网页嵌入

### CLI

```bash
wavedrom --input source.json5 --indent 2 > output.svg
```

当前 CLI 的核心参数：

- `-i`, `--input <path>`：输入 WaveJSON/JSON5 文件。
- `-t`, `--indent <number>`：SVG 输出缩进。
- `-h`, `--help`：帮助。

PNG 可通过官方 README 推荐的 `@resvg/resvg-js-cli` 管道转换：

```bash
npx wavedrom -i source.json5 | npx @resvg/resvg-js-cli - output.png
```

### HTML

在网页中加载 WaveDrom 3.x：

```html
<script src="https://cdn.jsdelivr.net/npm/wavedrom@3/wavedrom.min.js"></script>
<body onload="WaveDrom.ProcessAll()">
  <script type="WaveDrom">
    { signal: [
      { name: 'clk', wave: 'p....' },
      { name: 'req', wave: '01..0' }
    ]}
  </script>
</body>
```

离线文档或仓库资产优先保存生成后的 SVG，避免查看时依赖 CDN。

## 9. 排错清单

- **总线标签错位**：检查 `=` 或 `2`-`9` 的新数据段数量是否等于 `data` 标签数。
- **信号事件错一格**：逐字符标注索引，检查各泳道 `wave` 的长度和 `.` 的位置。
- **箭头不出现**：检查 `node` 中是否真的存在对应字符，节点名是否唯一，`edge` 拼写是否一致。
- **相邻泳道时间轴不同**：检查某条泳道是否单独设置了 `period` 或 `phase`。
- **输出为空或损坏**：直接运行 `wavedrom --input file.json5 --indent 2` 查看解析错误，或使用 skill 的渲染脚本避免覆盖已有 SVG。
- **JSON5 解析失败**：检查引号、逗号和括号是否配对；不要把可执行 JavaScript 函数当作 CLI 输入。
- **图过宽**：减少无信息的保持周期，使用 `|` 表示省略区间，或降低 `hscale`。

## 10. 官方资料

- 官网与在线编辑器：https://wavedrom.com/
- 官方交互教程：https://wavedrom.com/tutorial.html
- 逻辑电路教程：https://wavedrom.com/tutorial2.html
- 官方源码、CLI 和网页嵌入说明：https://github.com/wavedrom/wavedrom
