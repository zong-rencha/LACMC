# LACMC Evaluation

Evaluation deployment for **Continual Heterogeneous Multi-Agent Cooperation via Low-Rank Adaptation in Decentralized Partially Observable Environments**.

当前主分支只提供预构建 Docker 镜像的下载、校验和启动脚本。运行入口是镜像内的 `evaluate3.py`，无需在宿主机准备 `src/` 或 `vendor/`。

## 下载

- 当前部署脚本：本页 **Code → Download ZIP**，或下面的 `git clone`。
- 镜像、模型和十张地图：[v1.3 Release Assets](https://github.com/zong-rencha/LACMC/releases/tag/v1.3)。
- 游戏程序：[Blizzard Linux SC2 4.10](https://github.com/Blizzard/s2client-proto#downloads)，安装前阅读对应 AI and Machine Learning License。

部署需要 x86_64/amd64、可运行 Docker 的环境、支持 CUDA 13.0 的 NVIDIA GPU 和驱动。Linux 需要 NVIDIA Container Toolkit；Windows Docker Desktop 使用 WSL 2 与 Linux 容器。宿主机 Python 3.9+ 只运行标准库下载工具。

AutoDL 普通容器实例不支持在实例内运行 Docker，参见 [平台说明](https://www.autodl.com/docs/env)。

## Linux

Docker 与 NVIDIA 容器支持配置完成后，在终端执行：

```bash
git clone --depth 1 https://github.com/zong-rencha/LACMC.git
cd LACMC
python3 scripts/download_assets.py --image
sudo python3 scripts/load_image.py

# 先阅读 Blizzard 许可；仅在同意后执行
bash scripts/setup_sc2.sh --accept-license

sudo docker run --rm --gpus all --cpus=2 --memory=2g --memory-swap=2g \
  lacmc-qmix:1.3 python -c "import torch; print(torch.__version__); print(torch.cuda.get_device_name(0)); print(torch.ones(4,device='cuda').sum().item())"

sudo bash scripts/run-evaluation.sh
```

GPU 测试最后应输出 `4.0`。再次评估只需在项目目录执行最后一条命令。

## Windows

先安装并启动 Docker Desktop（Linux 容器、WSL 2），准备 Git 和 Python 3.9+。在 PowerShell 执行：

```powershell
git clone --depth 1 https://github.com/zong-rencha/LACMC.git
Set-Location LACMC
python scripts/download_assets.py --image
python scripts/load_image.py
```

从 Blizzard 下载 **Linux** `SC2.4.10.zip`，解压到 `SC2-Linux`，应存在 `SC2-Linux\StarCraftII\Versions\Base75689\SC2_x64`。密码 `iagreetotheeula` 表示接受对应许可。

```powershell
New-Item -ItemType Directory -Path '.\SC2-Linux\StarCraftII\Maps\SMAC_Maps' -Force | Out-Null
Copy-Item -Path '.\maps\SMAC_Maps\*' -Destination '.\SC2-Linux\StarCraftII\Maps\SMAC_Maps' -Recurse -Force
powershell -ExecutionPolicy Bypass -File .\scripts\run-evaluation.ps1
```

## 文件与结果

- `scripts/`：下载、校验、加载镜像、安装游戏和启动评估。
- `artifacts/`：运行下载脚本后产生的发布附件缓存。
- `results/`：下载的 10 个评估检查点和输出。
- `maps/SMAC_Maps/`：下载的实验地图。
- `SC2-Linux/StarCraftII/`：单独安装的游戏。

输出直接显示在终端，数组保存在 `results/success_rate/p.npy`；同名结果会被覆盖。不按次创建新评估目录或额外日志。

发布清单和 SHA256 用于核对附件。镜像由锁定依赖的云端构建产生；当前评估默认每图 32 局，不保证不同硬件或每次运行数值完全一致。

v1.3 已替换为评估专用镜像：只保留 19 个项目评估文件及 10 个必需检查点，去除了训练方法、关系/轨迹训练模块、绘图、其他环境和备用文件。保留的检查点与原文件逐字节一致，十张地图和 Python 依赖版本不变。镜像采用独立最终构建阶段，并审计归档中的每一层，避免旧层残留完整项目源码。必需的评估源码仍可提取；精简不是加密，也无法收回以前下载的完整镜像。

## 已有用户更新

分卷名称改为 `lacmc-qmix-1.3-eval-only.tar.part-NNN`，加载后仍为 `lacmc-qmix:1.3`。请重新执行下载与镜像加载步骤，刷新校验清单、发布清单、模型包和全部新分卷；旧的 `cmac-dtr-1.3.tar.part-*` 不再用于当前发布，不要混用。现有下载脚本会按照新清单校验文件；保留的模型文件内容相同。

本地 GPU 验证已完成十张地图、每图 32 局；十任务固定输入的网络输出与动作对照最大误差为 0.0。云端构建核对这 19 个文件的哈希与本地验证一致。评估分数仍可能随运行和硬件变化。

## 许可

当前部署文件沿用 [MIT License](LICENSE)。第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [SMAC License](licenses/SMAC-LICENSE)；SC2 游戏适用 Blizzard 单独许可。
