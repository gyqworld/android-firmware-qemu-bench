# Android Firmware QEMU Bench

[English](README.en.md) · [内容与权利边界](docs/BOUNDARIES.md) · [外部输入清单](docs/INPUTS.md)

**Windows x64 上运行“使用者自行提供的原车机 Android 用户空间”的兼容性实验。**

> **这是适配工具的源码仓库，不是车机固件、Android 系统发行版、高德发行包或车机全功能模拟器。**
> 仓库没有附带任何车机固件镜像、从固件提取的文件、厂商二进制、APK、地图、应用素材、用户数据盘或真实运行日志。仅下载本仓库还不能启动原系统；必须自行提供匹配版本的外部输入。

## 哪些属于谁

| 组成 | 来源与边界 | 是否在仓库中 |
|---|---|---|
| 启动编排、只读 sparse/NBD、RAM 覆盖、诊断通道、实时像素查看器 | 本项目适配代码；不是 Android framework 的重新实现 | 源码 |
| `gralloc.bench.so` 的实现 | 本项目 `native/gralloc-bench.c` 编译，提供 ashmem 分配与软件 framebuffer 像素传输 | 仅 `.c` 源码，无 `.so` |
| gralloc/HAL 接口声明 | Android 9 AOSP 公开头文件，保留 Apache-2.0 声明 | 具名头文件 |
| `/init`、Bionic、ART/zygote、system_server、SurfaceFlinger、HIDL、Settings 等 | **原车机 Android 固件已有内容**；原系统进程实际运行，不是本项目创作 | 无；由使用者的 system/vendor 镜像读取 |
| 原厂 EGL/Mali、Exynos HWC、车辆应用、预编译 SELinux policy | **原固件已有内容**；部分运行时接口被临时覆盖，原件不回写 | 无 |
| QEMU、兼容内核、BusyBox/musl、SwiftShader、LLVM、Node.js、Python/Pillow | 第三方组件，不是本项目原创；对应上游许可证单独生效 | 无二进制；提供带摘要的下载脚本 |
| 高德 APK、界面、商标、协议、地图和导航算法 | 高德及相应权利人的内容，**不是本项目原创，也不随仓库分发** | 无；可选自行提供 |

更细的运行时替换和许可证范围见 [BOUNDARIES.md](docs/BOUNDARIES.md)。**MIT 不赋予固件或高德的再分发权。**

## 实现方式

```text
Windows / QEMU ARM64 virt（TCG）
  → 单独下载的通用 Android 兼容内核 + 项目 bootstrap
  → 使用者原固件的 init / ART / framework / 系统服务
  → 原 SurfaceFlinger + 原 HIDL HWC2OnFbAdapter
  → 第三方 SwiftShader + 本项目 gralloc0/framebuffer 适配
  → 实际合成帧 → loopback 实时网页；点击 → 原 Android input
```

原 Exynos `boot.img`、DTB、VLM/QNX 没有被完整模拟。网页不重画 Android/高德界面，不是静态截图展示。

## 快速开始

1. 准备 Windows x64。使用 [INPUTS.md](docs/INPUTS.md) 中的镜像布局；将路径写入 **`config.local.json`**，或直接把必需镜像放到 `local/firmware/`。这些路径默认被 Git 忽略。
2. 双击 **`Setup-Dependencies.cmd`**。优先复用已有 Python/Node/LLVM，以及配置中指定的 QEMU/内核/initramfs；缺失时下载到 `runtime/`，验证固定摘要。不会下载车机固件、高德 APK 或地图。
3. 执行 `python doctor.py`，或双击 **`Run-Amap.cmd`**。

首次准备可以明确复用已有文件：

```powershell
./Setup-Dependencies.cmd --qemu "C:\Tools\qemu-system-aarch64.exe" --initramfs "C:\Inputs\initramfs-virt" --kernel "C:\Inputs\Image-4.14" --firmware-dir "C:\Inputs\firmware"
```

下载前查看清单、已有缓存离线重跑：

```powershell
python scripts/setup_dependencies.py --plan
python scripts/setup_dependencies.py --offline
```

首次自行提供 APK（可选，高德 9.5 ARM64 是已测试实例）：

```powershell
./Run-Amap.cmd --apk "C:\Inputs\amap.apk"
```

已安装后无需再次提供 `--apk`。`LIVE_VIEWER_URL` 是本次实时界面地址，端口每次变化。默认运行 30 分钟后结束。启动和首次应用资源加载较慢，**30 Hz 显示模式不等于实测 30 FPS**。

## 已观察结果与限制

在一种匹配的原固件 Android 9 / ARM64 环境中，观察到原 `sys.boot_completed=1`、原 SurfaceFlinger 的 SwiftShader 渲染、高德 9.5 原进程和实时主界面；点击回传到原 Android。首次条款由用户确认后才继续。

这不是所有固件/应用的兼容保证。当前默认 `-nic none`，未接真实 GPS/车辆信号；**在线底图、搜索、路线、定位没有验收**，高德可能提示「暂无可用地图数据」。桌面/SystemUI 与特定车辆应用可在 RAM 挂载视图中隐藏以避免缺少车辆服务的崩溃循环。

## 停止与本地数据

```powershell
python control.py 'sync'
python rollback.py
```

只停止本项目记录且身份匹配的 QEMU；原镜像只读并保存本地 SHA-256 基线。`data/userdata.ext4` 是新建可写数据盘，保留安装、缓存、条款和设置；**停止不等于清除这份数据**。VM 内 RAM 覆盖随停止丢弃。

## 测试与发布检查

```powershell
python -m unittest discover -s tests -v
python scripts/audit_public.py
python scripts/package_source.py --output reports/source-release.zip
```

CI 不接触固件、不启动车机进程、不上传 runtime/build/data。测试成功不能当作某个用户固件已开机。发布包由审计过的源码清单生成，而非压缩整个工作目录。

本项目与 Volkswagen、LG、Samsung、高德、AGL 等无隶属或背书关系。商标、界面、固件与应用仍归各自权利人。
