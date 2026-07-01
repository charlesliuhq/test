# 世界杯比赛预测系统

一个用**纯 Python 标准库**实现的世界杯比赛预测小工具，可在 **Windows 7** 上运行。

## 特点

- ✅ **无需安装任何第三方依赖**，只用 Python 自带的 `tkinter` 图形界面
- ✅ 兼容 **Windows 7**（推荐 Python 3.6 ~ 3.8，其中 3.8 是官方支持 Win7 的最后一个版本）
- ✅ 预测模型：球队实力评分（类 Elo）+ **泊松分布**进球模型
- ✅ 三大功能：单场比赛预测、球队评分管理、整届赛事蒙特卡洛模拟
- ✅ 无图形环境时自动降级为命令行模式

## 运行方式

在 Windows 上安装 Python 后，双击 `worldcup_predictor.py`，或在命令行执行：

```bash
python worldcup_predictor.py
```

> Windows 7 用户请到 python.org 下载 **Python 3.8.x**（最后一个支持 Win7 的版本），
> 安装时勾选 “Add Python to PATH”。安装包已自带 tkinter，无需额外操作。

## 功能说明

### 1. 单场预测
选择两支球队，系统给出：
- 胜 / 平 / 负 概率
- 双方期望进球数
- 最可能出现的几个比分

### 2. 球队评分
- 查看、添加、修改、删除球队评分
- 保存 / 加载 `teams.json` 存档文件
- 一键恢复默认评分

### 3. 赛事模拟
两种赛制可选（模拟次数可调）：

- **完整赛制（小组赛 + 淘汰赛）**：取评分最高的 32/16/8 支球队随机分组，
  8 组单循环（3/1/0 计分，按积分→净胜球→进球排名），每组前 2 出线，
  再按标准交叉赛制进入单败淘汰赛（平局点球决胜）。输出每队的
  **夺冠 / 进决赛 / 进四强**概率。
- **单败淘汰赛**：取评分最高的 2ⁿ 支球队直接进行单败淘汰，输出**夺冠概率**。

## 用历史数据校准评分

系统可以用**真实历史比分**反推、校准球队评分（Elo 算法）：

- **图形界面**：在「球队评分」页点 **从历史数据校准**，选择比分 CSV 即可。
- **命令行脚本**：
  ```bash
  python calibrate.py historical_matches.csv teams.json
  ```
  以现有评分为先验，逐场按「实际结果 vs 预期」的偏差更新评分，
  进球差越大调整越大；校准结果写回 `teams.json`。

CSV 格式（表头必须包含以下列，`weight` 可选，表示比赛权重）：

```csv
home,away,home_goals,away_goals,weight
阿根廷,法国,3,3,1.5
日本,德国,2,1,1.3
```

> ⚠️ 仓库自带的 `historical_matches.csv` 仅为**示例数据**，用于演示校准流程，
> 并非权威赛果。请替换为你自己的真实比分以获得准确评分。

## 打包成 exe（Windows 双击即用）

打包后可以**不装 Python 直接双击运行**。在 **Windows** 机器上：

```bat
:: 双击 build_exe.bat, 或在命令行运行:
build_exe.bat
```

生成的可执行文件位于 `dist\WorldCupPredictor.exe`。

> ⚠️ **PyInstaller 不能跨平台**：要生成 Windows 的 exe，必须在 Windows 上打包
> （在 Linux/Mac 上打包只能得到对应平台的可执行文件）。
> 要兼容 **Windows 7**，请使用 **Python 3.8.x + PyInstaller 4.x**
> （见 `requirements-build.txt`）；新版 PyInstaller 生成的 exe 可能无法在 Win7 上运行。

相关文件：`build_exe.bat`（一键打包脚本）、`worldcup_predictor.spec`（打包配置）、
`requirements-build.txt`（打包依赖）。

## 预测模型原理

1. 每支球队有一个**实力评分**（数值越高越强）。
2. 两队评分差换算成**净胜球优势**（supremacy）。
3. 在“单场总进球期望”的基础上按优势分配给两队，得到各自的**期望进球** λ。
4. 用**泊松分布** `P(X=k) = e^(-λ)·λ^k / k!` 计算各种比分的概率。
5. 汇总所有比分得到胜/平/负概率；模拟时从泊松分布随机采样进球数。

模型参数（可在源码顶部调整）：

| 参数 | 含义 | 默认值 |
|------|------|--------|
| `BASE_GOALS` | 一场比赛双方进球总数的经验期望 | 2.6 |
| `RATING_SCALE` | 评分差换算进球优势的比例尺 | 220 |
| `MAX_GOALS` | 计算比分矩阵时的单队最大进球 | 8 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `worldcup_predictor.py` | 主程序（图形界面 + 预测模型 + 赛事模拟 + 校准引擎） |
| `calibrate.py` | 命令行评分校准脚本 |
| `historical_matches.csv` | 历史比分**示例**数据（请替换为真实数据） |
| `build_exe.bat` | Windows 一键打包 exe 脚本 |
| `worldcup_predictor.spec` | PyInstaller 打包配置 |
| `requirements-build.txt` | 打包所需依赖（运行程序本身无需依赖） |
| `teams.json` | 球队评分存档（保存/校准后生成） |
| `README.md` | 本说明文档 |
