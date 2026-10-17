## HinLink H 系列 · x-wrt 26.10 全 16 机型固件

**基线**：`x-wrt 26.10_b202610170051`（内核 6.18.55 / U-Boot 2026.10），
target `rockchip/armv8`，默认 LAN **`192.168.15.1`**（root 无密码）。

适配层源码与本批 config 见仓库 [`Beaverfffan/xwrt-hinlink`](https://github.com/Beaverfffan/xwrt-hinlink)：
`configs/` 是这 16 份配置，`tools/integrate.py` 负责合并，
`README.md` 写了机型表与机理。

### 为什么用 x-wrt

图它的 natflow 转发加速。⚠️ 但要说清：**natflow 在 rockchip 上没有硬件 offload**
（`995-*hwnat*` 系列补丁只存在于 airoha / mediatek / ramips 三个 target，
RK356x / RK3588 本身也没有 PPE）⇒ 这里拿到的是**软件路径优化**，不是硬件 NAT。

### 本批内容

- 16 机型、每机型独立 rootfs（官方模板的 `CONFIG_TARGET_PER_DEVICE_ROOTFS=y`）
- 配置**基于官方模板** `feeds/x/rom/lede/config.rockchip-armv8`，
  选完机型后跑 `feeds/x/rom/lede/fix-config.sh`（官方流程）
- 内核 / rootfs 分区：**128 MB / 1024 MB**（官方模板原是 64 / 256，
  这里为装得下 passwall 类插件放大；只影响镜像 padding，不参与编译）
- 固件版本号：`16dev-2026.10.17`
- 内置无线驱动：MT7921 / MT7922（含独立固件包）/ MT7925 / MT7915 /
  MT7916 / MT7615、ath11k + WCN6855(NFA765)、AIC8800（SDIO/PCIe/USB）、
  rtw88 / rtw89 / rtl8xxxu / r8152
- 内置 `luci-app-oled`（iStoreOS 版，SSD1306 0.91″，`netsource=wwan0`）

### 机型 × 插件（两条**独立**判据，不取交集）

> 机器**有风扇** → 编风扇温控；有 **5G 复位脚** → 编「5G复位」面板。

| 机型 | 网口（LAN / WAN） | 风扇温控 | 5G复位 | 屏幕 |
|---|---|---|---|---|
| `h69k` | eth1 eth2 / eth0 | ✅ | ✅ | OLED (i2c5) |
| `h69k-mini` | eth0 eth2 eth3 / eth1 | ✅ | ✅ | OLED (i2c5) |
| `h88k-v2` | eth1 / eth0 | ✅ | ✅ | — |
| `h88k-v3` | eth1 eth2 / eth0 | ✅ | ✅ | — |
| `h89k` | eth0 eth1 / eth2 | ✅ | ✅ | ST7789V 1.14″ |
| `h29k-v1.3-1.14` | eth0 / — | — | ✅ | ST7789V 1.14″ |
| `h29k-v5-1.14` | eth0 / — | — | ✅ | ST7789V 1.14″ |
| `h29k-v5-1.49` | eth0 / — | — | ✅ | GC9307 1.49″ 触屏 |
| `h28k` | eth0 / eth1 | — | — | — |
| `ht2` | eth0 / — | — | — | — |
| `h66k` | eth1 / eth0 | — | — | — |
| `h68k-a-b` | eth1 / eth0 | — | — | — |
| `h68k-a-b-usb` | eth1 / eth0 | — | — | — |
| `h68k-c-d-f` | eth1 eth2 eth3 / eth0 | — | — | — |
| `h68k-c-d-f-usb` | eth1 eth2 eth3 / eth0 | — | — | — |
| `h68k-new` | eth0 eth2 eth3 / eth1 | — | — | — |

### 怎么刷

- 已有 OpenWrt / x-wrt：把 `*-squashfs-sysupgrade.img.gz` 传上去
  `sysupgrade -n <file>`（`-n` 丢掉旧配置；从其他固件迁移建议丢）。
- 裸机 / 从 eMMC 救砖：用 RKDevTool 烧 `*-ext4-sysupgrade.img.gz` 解压后的
  `*.img`（**注意**：这版没有单独的 `-factory.img`）。

### 已知限制

- **H29K / H88K / H89K 的屏没有用户态程序驱动** —— fbtft 只提供 `/dev/fbN`。
- **h88k-v3 的屏走 `spidev` + 用户态**（DTS 里没有 fbtft 面板参数）。
- **多口机型的各 LAN 口 MAC 相同**（`config_generate` 对 `ports` 里每个口写同一份
  `macaddr`）。要逐口独立 MAC 得把该机型从 `rockchip_setup_macs` 共享分支移出。
- **natflow 无硬件 offload**（见上）。
- 本批**未做实机验证**，只保证编译通过、镜像结构正常。

### 校验

每个 asset 都附在 `sha256sums.txt` 里。
