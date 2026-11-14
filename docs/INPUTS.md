# 私有输入 / User-supplied inputs

## 必需镜像

请自行取得匹配的一套 Android 9 / ARM64 原固件，并在本地提供：

| 文件 | 用途 | 是否下载/分发 |
|---|---|---|
| `system.img` | system-as-root ext4/sparse，含根 `/init` 与 `/system`；原 Android framework/ART/服务/资源 | 不下载，不分发 |
| `vendor.img` | ext4/sparse，含 `/lib64/hw`、`/etc/init`、原预编译 SELinux policy 和所需厂商库 | 不下载，不分发 |
| `userdata.img` | 原交付的工厂数据镜像，只读挂载；不是公开数据集 | 不下载，不分发 |

本项目按原实验包的布局编写，假设 vendor policy 位于 `/etc/selinux/precompiled_sepolicy`、fstab 为 `/etc/fstab.exynosauto9`、system 镜像的根有 `/init`。不同 Android 版本、分区布局或 API/ABI 需要重新适配，不能只改文件名。

**不需要复制进仓库：** boot.img、dtb.img、vbmeta.img、VLM、QNX、完整固件目录。bench 使用单独下载的通用兼容内核，不重现完整安全启动链。

## 本地编译会读取的原固件库

从你提供的 `system.img:/system/lib64/` 读取 `libc.so`、`liblog.so`、`libhardware.so`、`libcutils.so`、`libsync.so`、`libdl.so`，仅用于匹配原 Bionic ABI 的本地链接。这些提取件留在被忽略的 `build/link/`，**不属于源码项目，不能随 GitHub Release 上传**。

这不是“本项目自带 Android SDK/厂商运行库”；也不意味这些库都是同一种许可证。使用者应按实际版本核对权利和许可。

## APK（可选）

已有测试实例：高德车机版 `9.5.0.600013`、`com.autonavi.amapauto`、ARM64。APK 自行提供，不提供下载/镜像链接或改包。`--apk` 在本地安装盘视图中提交给原 Android 包管理器；APK 原件保持只读。

地图、离线数据、账号、许可和应用条款不随工具提供。首次条款必须人工确认。没有地图数据时，真实高德可显示主界面但底图为空，这不是导航验收。

## 配置示例

```json
{
  "firmware_dir": "C:/Inputs/private-firmware",
  "qemu": "C:/Tools/qemu-system-aarch64.exe",
  "initramfs": "C:/Inputs/initramfs-virt",
  "kernel": "C:/Inputs/Image-4.14",
  "node": "node",
  "clang": "clang",
  "linker": "ld.lld"
}
```

保存为被忽略的 `config.local.json`。不要将真实绝对路径放进公开 README、Issues 或日志附件。没有配置时路径参照 `config.example.json`。

## English

Supply matching private `system.img`, `vendor.img`, and factory `userdata.img`. The system image must contain a root `/init` and `/system`; the vendor image must match the tested Android 9 ARM64 layout and policy. No bootloader/VLM/QNX image is required or provided. Six original system shared libraries are privately extracted for linking and stay in ignored `build/link/`. Optional APKs, maps, accounts and terms remain outside the repository. A generic public kernel is used instead of the original hardware boot image.
