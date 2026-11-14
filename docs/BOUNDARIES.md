# 内容、执行与许可证边界 / Content and licensing boundaries

## 1. 仓库不是完整系统

本项目的功能是把**外部原固件用户空间**放入 QEMU/Linux 运行环境，并适配其启动、软件图形与输入输出。Android 的主要运行能力并非本项目原创：

| 运行时对象 | 来源 | 本项目做了什么 |
|---|---|---|
| `/init`、ueventd、Bionic、ART、zygote、system_server | 使用者提供的原固件 system.img | 挂载、启动、记录状态；不附源镜像或提取程序 |
| framework/JAR/ODEX/VDEX、系统资源、SettingsProvider 等 | 原固件 | 执行原实现；不重新授权或分发 |
| SurfaceFlinger、graphics HIDL 服务、HWC2OnFbAdapter | 原固件中已有 Android 组件 | 继续使用，接到软件 framebuffer；不是自编完整 HWC2 服务 |
| Exynos/Mali 原显示库、vendor fstab、原 init RC、预编译 policy | 原 vendor/system 镜像 | 只读输入；在 RAM 覆盖中选择性替换/隐藏配置/库，不带原文副本或固件差异包 |
| gralloc0、ashmem 像素缓冲、framebuffer post→virtio-serial | `native/gralloc-bench.c` | 本项目新增适配，编译后私下使用；仓库仅源码 |
| 通用 ARM64 内核 | AOSP 预编译下载 | 替代原硬件内核；不声称原 boot.img 已在 QEMU 启动 |
| EGL/GLES 软件渲染 | Google 官方 SDK 包中 SwiftShader | 单独下载校验并保留来源；不声称原创、不随源码包附带 |
| APK 页面、地图、搜索/导航业务、协议与商标 | 高德或其他应用及数据权利人 | 仅作为使用者可选输入运行，不复制其代码/素材，不附 APK/地图 |

文件名、包名、标准接口名和运行路径说明不是上述二进制/资源的授权转移。

## 2. 原系统与实验环境的差异

- 机器是 QEMU `virt`、ARM64 TCG，不是 Exynos Auto V9 硬件模型。
- 运行通用兼容内核；未启动整套原厂 bootloader、VLM/QNX 或车辆网络。
- headless/graphics 使用实验 bootstrap 完成挂载并进入原 init 第二阶段。
- 加载原 vendor policy，但此 guest 设为 permissive；只在本地临时环境中使用。
- 原 UFS 路径/fstab、init 导入和显示库选择在内存覆盖层适配；graphics 可隐藏桌面、SystemUI、车辆专用应用，只保留必要系统应用。
- `data/userdata.ext4` 是**新建数据盘**，不是原车用户数据的公开副本。原 `userdata.img` 作为只读外部输入；graphics 模式使用独立可写盘。
- 800×480 是 bench 的选择，不等于原车屏幕分辨率；软件渲染模式与性能也不同。
- root shell、viewer、NBD 均绑定 loopback；这不是面向生产环境的访问控制设计。
- APK 安装、应用条款与设置仅写到本地数据盘。脚本不替用户接受条款，不包含账号或地图数据。

因此“高德真实界面已显示”只表示原应用真实执行和输出可见，不表示车辆硬件、服务、位置、地图授权或全部导航功能复现。

## 3. 公开内容和禁止混入的目录

公开包只包含 `scripts/public-files.json` 中的审计清单：自编源码、文档、测试、上游依赖**摘要/URL**和 AOSP 公开接口头文件。

`local/`、`runtime/`、`build/`、`data/`、`output/`、`reports/`、`original/`、`modified/`、`changes/`、缓存及本地配置都不属于公开发布物。

特别排除：system/vendor/userdata/boot/dtb/vbmeta 镜像；任何提取 ELF/SO/JAR/APK/DEX/ODEX/VDEX；厂商 RC/policy 原件及其大段内容；签名密钥、令牌、账号、日志、实时帧、地图和第三方 artwork。**发布时也不要附带 data 盘或旧实验目录。**

`.gitignore` 只是第一道措施。`audit_public.py` 进一步审计实际 Git 索引和源码 ZIP 清单，拒绝未知文件、二进制魔数、敏感路径/凭据模式及来源不明的文件。`git add -f` 不会绕过该审计。

## 4. English summary

This is an adaptation layer, not an original Android implementation or a firmware/app distribution. The supplied firmware's init, ART, framework, SurfaceFlinger, HIDL adapter and system resources do the actual Android work. The project supplies boot orchestration, a small gralloc/framebuffer transport and live viewing/input tooling. Original firmware files remain private and read-only; temporary configuration/HAL substitutions occur in RAM.

The MIT license covers original bench code only. Identified AOSP headers retain Apache-2.0. Downloaded open-source tools keep their separate licenses and notices. Firmware-derived components, third-party apps, UI, trademarks and maps are not relicensed or redistributed. SDK download availability and hash verification do not grant broader redistribution rights.
