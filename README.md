# xwrt-hinlink —— HinLink 全系机型 x-wrt 适配层

把 **HinLink（H28K / H29K / HT2 / H66K / H68K / H69K / H88K / H89K）共 16 个机型**
接进 [x-wrt](https://github.com/x-wrt/x-wrt) 的 `rockchip/armv8` target。

- 基线分支：**`26.10_b202610170051`**（内核 6.18，U-Boot 2026.10）
- 选 x-wrt 的原因：**natflow 加速**（x-wrt 自带的转发加速栈）。
  ⚠️ 注意：natflow 在 rockchip 上**没有硬件 offload** —— `995-*hwnat*` 系列补丁
  只存在于 airoha / mediatek / ramips 三个 target，rockchip 的 187 个补丁里
  一条都不命中，RK356x / RK3588 本身也没有 PPE。所以这里用 x-wrt 得到的是
  **软件路径优化 + 与 imm 一致的驱动栈**，不是硬件 NAT。
- 本仓库是**适配层**（overlay），不是 x-wrt 源码树。用法：clone 官方 x-wrt →
  把本仓库内容覆盖进去 → `tools/integrate.py` 做合并。

> 溯源：本仓库的 DTS / 包 / 板级配置来自同作者的 immortalwrt 适配层
> `Beaverfffan/immortalwrt-hinlink`。两者**内容同源**，差异见 §5。

---

## 1. 快速开始

```bash
# 1) 取 x-wrt 基线（浅克隆即可，编译不需要上游历史）
git clone --depth 1 -b 26.10_b202610170051 https://github.com/x-wrt/x-wrt.git
cd x-wrt

# 2) 覆盖适配层（本仓库根目录就是这个 overlay 的根）
git -C /path/to/xwrt-hinlink archive HEAD | tar x -C .

# 3) feeds
./scripts/feeds update -a
./scripts/feeds install -a

# 4) 合并（board.d / armv8.mk / U-Boot 变体登记都是"改官方文件"，必须跑
#    这一步；直接覆盖会把官方其他机型的配置冲掉）
python3 tools/integrate.py --dst "$PWD"

# 5) 编一个机型
cp configs/h69k.config .config
make defconfig
make -j$(nproc)
```

产物：`bin/targets/rockchip/armv8/*-sysupgrade.img.gz`

★ 直接 `make` 的用户**必须**先做第 4 步的 `feeds uninstall`（见 §6.1），
否则 `luci-app-oled` / `fancontrol` 会被 feed 里的同名包顶掉。

---

## 2. 目录结构

```
target/linux/rockchip/
├── files/arch/arm64/boot/dts/rockchip/   ← 19 份 DTS + 公共 dtsi（本仓库主体）
├── image/armv8.mk.hinlink                ← 16 个 Device 定义（被 armv8.mk include）
├── armv8/base-files/etc/board.d/
│   ├── 01_leds                           ← 片段，由 integrate.py 合并进官方文件
│   └── 02_network                        ← 片段，同上
├── armv8/config-6.18                     ← 追加段（FB/fbtft/rfkill 内建）
└── hinlink-config.append                 ← 上面那段 config 的源文件

patches/          ← 内核补丁（fbtft gc9307 / 屏偏移 / delfbcon 光标）
patches-uboot/    ← U-Boot 板级 dts + defconfig（H29K/HT2、H88K/H89K）
package/beaverfffan/
├── fancontrol / luci-app-fancontrol      ← JiaY-shi 血统，温度控制**默认开**
├── luci-app-hinlink-modem-hardreset      ← 自研「5G复位」面板（rpcd shell 插件）
├── luci-app-oled                         ← iStoreOS 版 SSD1306（不是 unifreq 那版）
└── aic8800                               ← AIC8800 SDIO/PCIe/USB 驱动
tools/            ← integrate.py / gen_configs.py / build_single.sh …
configs/          ← 16 份单机型 .config
```

### DTS 怎么生效

x-wrt 的 `include/image.mk` 里 `Device/Build/dtb` 是**直接用 cpp + dtc 编**
`$(LINUX_DIR)/arch/arm64/boot/dts/rockchip/<DEVICE_DTS>.dts`，
**不依赖内核 Makefile 的 `dtb-y` 列表**。
而 `target/linux/rockchip/files/` 会在内核 prepare 阶段被整体拷进 `$(LINUX_DIR)`，
所以本仓库的 DTS **放进去就等于生效**，不需要改内核 dts 的 Makefile。

---

## 3. 机型与硬件能力

| # | configs/ 文件名 | OpenWrt DEVICE 名 | SoC | 网口（LAN / WAN） | 风扇 | 5G复位脚 | 屏幕 |
|---|---|---|---|---|---|---|---|
| 1 | `h28k` | `hinlink_h28k_rk3528` | RK3528 | `eth0` / `eth1` | — | — | — |
| 2 | `h29k-v1.3-1.14` | `hinlink_h29k-v1.3-1.14_rk3528` | RK3528 | `eth0` / — | — | ✓ GPIO4_B4/B5 | ST7789V 1.14″ |
| 3 | `h29k-v5-1.14` | `hinlink_h29k-v5-1.14_rk3528` | RK3528 | `eth0` / — | — | ✓ | ST7789V 1.14″ |
| 4 | `h29k-v5-1.49` | `hinlink_h29k-v5-1.49_rk3528` | RK3528 | `eth0` / — | — | ✓ | GC9307 1.49″ 触屏 |
| 5 | `ht2` | `hinlink_opc-ht2_rk3528` | RK3528 | `eth0` / — | — | — | — |
| 6 | `h66k` | `hinlink_opc-h66k` | RK3568 | `eth1` / `eth0` | — | — | — |
| 7 | `h68k-a-b` | `hinlink_opc-h68k-a-b` | RK3568 | `eth1` / `eth0` | — | — | — |
| 8 | `h68k-a-b-usb` | `hinlink_opc-h68k-a-b-usb` | RK3568 | `eth1` / `eth0` | — | — | — |
| 9 | `h68k-c-d-f` | `hinlink_opc-h68k-c-d-f` | RK3568 | `eth1 eth2 eth3` / `eth0` | — | — | — |
| 10 | `h68k-c-d-f-usb` | `hinlink_opc-h68k-c-d-f-usb` | RK3568 | `eth1 eth2 eth3` / `eth0` | — | — | — |
| 11 | `h68k-new` | `hinlink_opc-h68k-new` | RK3568 | `eth0 eth2 eth3` / `eth1` | — | — | — |
| 12 | `h69k` | `hinlink_opc-h69k` | RK3568 | `eth1 eth2` / `eth0` | ✓ PWM | ✓ GPIO0_C0 | OLED I²C |
| 13 | `h69k-mini` | `hinlink_opc-h69k-mini` | RK3568 | `eth0 eth2 eth3` / `eth1` | ✓ PWM | ✓ | OLED I²C |
| 14 | `h88k-v2` | `hinlink_h88k_v2` | RK3588 | `eth1` / `eth0` | ✓ | ✓ GPIO4_C6 | — |
| 15 | `h88k-v3` | `hinlink_h88k_v3` | RK3588 | `eth1 eth2` / `eth0` | ✓ | ✓ | — |
| 16 | `h89k` | `hinlink_opc-h89k_rk3588` | RK3588 | `eth0 eth1` / `eth2` | ✓ | ✓ | ST7789V 1.14″ |

两条**互相独立**的判据（别取交集 —— 会漏掉「有复位脚但没风扇」的 H29K 全系）：

```
有风扇       -> fancontrol + luci-app-fancontrol      （5 个）
有 5G 复位脚 -> luci-app-hinlink-modem-hardreset      （8 个）
```

⚠️ 判据必须落到**真实节点**（`compatible = "rfkill-gpio"` / 真实 `pwm-fan`），
不能裸 grep 关键词：`ht2` 的 dts 注释里提到 rfkill、`h89k` 的注释里提到 pwm-fan，
都会误判；h88k-v2/v3、h89k 的节点在公共 `rk3588-hinlink.dtsi` 里。

⚠️ **H29K / H88K 的屏目前没有可用的用户态程序驱动**（fbtft 只提供 `/dev/fbN`）。

---

## 4. 出厂默认

- **LAN = `192.168.15.1`**，DHCP 开，无密码。
  ★ 沿用 x-wrt 自己的默认，**不再**改成 `192.168.100.1`（用户 2026-10-17 决定）。
  想改：官方 `base-files/etc/board.d/…` 或首次开机后 `uci set network.lan.ipaddr`，
  本仓库**没有**任何脚本会去覆盖它（不再有 `03_hinlink-lan-ip`）。
- WAN/LAN 按 §3 表由 `02_network` 的 `rockchip_setup_interfaces()` 设定。
- MAC：全部机型从 **eMMC `mmcblk0` 的 CID** 派生 `wan_mac`，`lan_mac = wan_mac + 1`。
  ⚠️ `config_generate` 会给多端口 LAN 的**每个**口写同一份 `macaddr`
  ⇒ 多口机型（h68k-c-d-f / h69k-mini / h88k-v3 / h89k）各 LAN 口 MAC **相同**。
  要逐口独立 MAC 得把这些机型从 `rockchip_setup_macs` 的共享分支移出。

---

## 5. 与 immortalwrt 适配层的差异（照抄会踩的坑）

| 项 | immortalwrt | x-wrt 26.10 | 处理 |
|---|---|---|---|
| 板级 `board.d` | 我们自己维护整段 hinlink 分支 | **上游已有** h28k/h66k/h68k 三条 | `integrate.py` 先摘掉上游分支再插（否则 h68k 的 WAN 会按新机 `eth1` 配） |
| `armv8.mk` | 无 hinlink 设备 | 已有 4 个（h28k/h6xk/h66k/h68k） | 摘掉，换我们的 16 个 |
| U-Boot 变体 | 我们补 8 个 | 已有 3 个（h28k/h66k/h68k）+ 106/107 补丁 | 只补 5 个（h29k/ht2/h88k-v2/h88k-v3/h89k），并把已有 3 个的 `BUILD_DEVICES` 改成我们的 device 名 |
| U-Boot 补丁号 | 108 / 109 | **108-01…108-07 已被 mkimaging 占用** | 改号成 **120 / 121** |
| `kmod-rtw89-8852bu` | 有 | **没有**（x-wrt 的 rtw89 只做 PCI 侧） | 从 DEVICE_PACKAGES 去掉 |
| `kmod-rtl8188eu` | 有 | **没有**（只剩 `rtl8188eu-firmware`） | 去掉 |
| `brcmfmac-{firmware,nvram}-43456-sdio` | 有 | **没有**（43456 整族缺） | 去掉（板载是 AP6256 = BCM43455） |
| 默认 LAN | 192.168.100.1 | 192.168.15.1 | 用 x-wrt 的 |
| 内核补丁号 9528/9530/9999 | 空闲 | 空闲 | 原样使用 |

另一个**上游自带**的问题（不是本仓库引入）：x-wrt 的
`package/base-files` 里 `config PACKAGE_input-support` 自带
`select PACKAGE_procd if PACKAGE_procd-selinux<PACKAGE_input-support`，
`make defconfig` 会打印

```
tmp/.config-package.in:53:error: recursive dependency detected!
        symbol PACKAGE_input-support is selected by PACKAGE_input-support
```

这是自指，**所有机型**都有，不影响编译（rc=0）。

---

## 6. 关键机理（改之前先读）

### 6.1 feed 同名包会**静默**顶掉本地包

`./scripts/feeds install -a` 在 `package/feeds/<feed>/` 下建软链，OpenWrt 扫
`package/` 时按**字母序**，`package/feeds/*` 晚于 `package/beaverfffan/*` ⇒
同名 Package 定义被 feed 那份覆盖。编译不报错、manifest 里也照样有这个包，
**只是内容是 feed 的**：

- `fancontrol` → 上游 `enabled '0'`（我们要 `'1'`，温控默认开）
- `luci-app-oled` → unifreq 版 `netsource=eth0`（我们要 `wwan0`）
- `luci-app-fancontrol` → 上游版

修法（二选一）：

```bash
# 手动
./scripts/feeds uninstall fancontrol luci-app-fancontrol luci-app-oled
# 或直接删软链
rm -rf package/feeds/*/fancontrol package/feeds/*/luci-app-fancontrol \
       package/feeds/*/luci-app-oled
```

`tools/build_single.sh` 的 `[0]` 步会自动做，并清掉 `tmp/.packageinfo` 与
对应 `build_dir` / `staging_dir` 产物（不清会继续复用 feed 版的编译结果）。
**新增自维护包必查**：`find feeds -maxdepth 4 -type d -name <包目录名>`。

### 6.2 H69K 的 OLED 挂 **i2c5**

- 引脚 `i2c5m0`：**GPIO3_B3 = SCL / GPIO3_B4 = SDA**。
- 内核 `rk356x-base.dtsi` 的 `i2c@fe5e0000` **自带 `pinctrl-0 = <&i2c5m0_xfer>`**
  ⇒ 板级**只给 `status = "okay"`**，不要重复写 pinctrl。
- 时序照 iStoreOS：rising 160 / falling 30 / 400 kHz。
- 16 台机器的 DTS 原先**全都没有 `&i2c5`** ⇒ 实机 device-tree 里是
  `disabled` ⇒ 没有 `/dev/i2c-5` ⇒ `oled` 打不开设备、procd 日志刷
  `Instance oled::instance1 s in a crash loop`、**屏全黑**。已在 h69k-3eth 补齐。
- ⚠️ **改完 DTS 必须清内核构建目录**：`target/linux/rockchip/files/` 只在
  prepare stamp 失效时才重拷，残留会让人以为"改了等于没改"。
  最稳的是 `rm -rf build_dir/target-*/linux-rockchip_armv8`。

### 6.3 5G 模组复位：`rfkill-gpio` + `/sys/class/rfkill/rfkillN/state`

三组极性各不相同：

| 机型族 | 供电脚 | 复位脚 | 极性 |
|---|---|---|---|
| H29K 全系 | GPIO4_B5 | GPIO4_B4 | **低有效** |
| H69K / mini | —（单路） | GPIO0_C0 | **低有效** |
| H88K v2/v3 + H89K | GPIO4_A3 | GPIO4_C6 | **高有效** |

四条硬机理：

1. **`regulator-fixed` 的极性只看 `enable-active-high`**：`gpio`/`gpios` 上挂的
   `GPIO_ACTIVE_LOW` flag 被内核**主动忽略**。有 EAH ⇒ 高使能，没有 ⇒ 低使能。
   （坑：H69K 曾同时写 EAH + ACTIVE_LOW ⇒ 模组从未上电。）
   只有 `rfkill-gpio` / `gpio-hog` 的 flag 才有效。
2. **`regulator-fixed`（always-on）没有任何用户态接口**，拒 `disable`；
   `gpioset` / libgpiod 也一样 `EBUSY`。**软复位唯一入口是
   `/sys/class/rfkill/rfkillN/state`**（`DEVICE_ATTR_RW`）：`echo 0 → 等 → echo 1`。
3. **6.18 的 `rfkill-gpio` 没有 `power-gpios`**（只 request `reset`/`shutdown`），
   DT 读的是 **`label` / `radio-type`**（不是 `name` / `type`）。它的 probe 在
   `device_initcall` 就把 reset 拉到工作态，而 regulator 的 enable 在更晚的
   `late_initcall_sync` ⇒ **复位先于上电**；有时序需求要用
   **两级 `regulator-fixed` + `vin-supply` 依赖链**。
4. `CONFIG_RFKILL_GPIO=y` 必须是**内建**：`=y` ⇒ `device_initcall`，所有 initcall
   都在用户态之前跑完 ⇒ preinit/rcS/SSH 一定晚于它，不存在"加载太晚"。
   只有 `=m` 才要等 kmods。所以 `hinlink-config.append` 里写死了 `=y`。

### 6.4 U-Boot：`BUILD_DEVICES` 必须写**当前有效**的 device 名

OpenWrt 的 `uboot-rockchip` 包靠 `BUILD_DEVICES` **反向关联**设备，且变体名必须
同时在 `UBOOT_TARGETS` 里（`$(foreach type,$(UBOOT_TARGETS),$(call BuildPackage,…))`
—— 光定义 `define U-Boot/xxx` 不登记，包根本不会生成）。

- x-wrt 上游写的是它自己的 device 名（`hinlink_h28k` / `hinlink_h66k` /
  `hinlink_h68k`），与我们的 16 个型号名对不上 ⇒ `make defconfig` 不会选中
  `CONFIG_PACKAGE_u-boot-hinlink-*-rk35xx`，**从零编译**会在 image 阶段报
  `No such file: …/hinlink-h68k-rk3568-u-boot-rockchip.bin`。
  （有 u-boot 缓存的树上反而看不出来。）
- 改完 `uboot-rockchip/Makefile` 后必须 `rm -f tmp/.packageinfo tmp/.targetinfo`
  再 `make defconfig`。

### 6.5 LED 名必须跟 DTS 的 `color`/`function` 走

内核 `gpio-leds` 用 `color`/`function` 拼出 `"<color>:<function>"`（如 `blue:wan`），
直接用 `label = "..."` 才用 label。厂商 2022/2023 固件用的是旧式
`"<boardname>:blue:net"` —— 我们已换成 mainline 写法，`01_leds` 里的名字
（`blue:wan` / `amber:disk` / `green:status` …）**改 DTS 时必须同步改**，
否则 `/etc/init.d/led` 找不到设备，灯不亮。

### 6.6 放在 target `base-files` 里的 init 脚本**不会**被自动 enable

`rootfs.mk` 里那句自动 enable 跑在 base-files 拷贝**之前** ⇒ 必须在
`base-files/etc/rc.d/` 里同时放 `Sxx<name>` 软链（会被原样拷进 rootfs）。
要早于网络 ⇒ `START=19`（`network` 是 20）。

### 6.7 ★ x-wrt 编译期必须处理的三个开关（都实测踩过）

这三个不处理，`make` 会以完全看不出根因的方式失败：

1. **`CONFIG_RFKILL_FULL=y`（6.18 拆分了 rfkill）**
   `net/rfkill/Kconfig` 现在是：
   ```
   config RFKILL          bool, default y      ← 核心位，一直 y
   menuconfig RFKILL_FULL tristate "RF switch subsystem support"
   config RFKILL_GPIO     depends on RFKILL_FULL   ← 必须先开 FULL
   ```
   只写 `CONFIG_RFKILL=y` 时 `RFKILL_FULL` 默认 **n** ⇒ **`RFKILL_GPIO`
   这个符号根本不可见**，oldconfig 把它静默丢掉（`.config` 里连一行都不留），
   5G 复位面板就找不到 `/sys/class/rfkill/rfkillN`——而且**不报任何错**。
   已写进 `hinlink-config.append`。

2. **`CONFIG_WERROR` 是 `y`，第三方 out-of-tree 驱动会被当错误**
   6.18 的 `CONFIG_WERROR` 默认 `default COMPILE_TEST`（=n），但合并出来的
   内核 `.config` 里却是 `CONFIG_WERROR=y`；`aic8800` 直接炸在
   `-Werror=missing-prototypes` / `-Werror=expansion-to-defined`。
   在 target config 里写 `# CONFIG_WERROR is not set` **对这个树无效**
   （手写 `scripts/config -d WERROR` 却能生效，说明是合并管线的问题，
   见 `hinlink-config.append` 里的说明）。真正管用的做法是给驱动自己加：
   ```make
   KCFLAGS="-Wno-error" \      # 加在每次 $(KERNEL_MAKE) 调用上
   ```
   已加进 `aic8800/Makefile` 的 4 处 `$(KERNEL_MAKE)` 调用。
   ⇒ 以后接任何 out-of-tree 驱动模块，先按这个套路加。

3. **`aic8800` 的 BT 编译开关必须默认 n**
   打开 `CONFIG_AIC8800_SDIO_BT_SUPPORT` 后驱动会引用 Bluetooth HCI 符号
   （`hci_register_dev` / `hci_recv_frame` / `hci_unregister_dev`），
   而为了避开 kconfig 成环我们已经去掉了 `kmod-bluetooth` 的条件依赖
   ⇒ `modpost: "hci_register_dev" [aic8800_fdrv.ko] undefined!`。
   要蓝牙就同时开该符号 + `CONFIG_PACKAGE_kmod-bluetooth=y`。

另外**两个上游补丁必须删掉**（`integrate.py` 已自动删）：
`patches-6.18/101-...-Add-HINLINK-H28K.patch` 用 `patch` **新建**
`rk3528-hinlink-h28k.dts`，与 `files/` 里的同名文件撞车 ⇒ 内核 prepare 直接
`The next patch would create the file … which already exists! Hunk #1 FAILED`；
`121-...-led-aliases-for-HINLINK.patch` 改的是同一批 dts 的 `led-*` alias，
我们**已经写进自己的 dts**，留着只会二次冲突。

### 6.8 网口编号的两个坑

- **kmodloader 按 `/etc/modules.d/<名>` 的文件名字典序加载**（内部 `glob()`），
  **不是**按总线枚举顺序 ⇒ 跨总线的同类网卡谁先拿到 `eth0` 由模块名排序决定。
  实例：`r8152`（USB 2.5G）排在 `r8169` 前面 ⇒ USB 网卡会抢 `eth0`。
  要固定映射只能按槽位路径在用户态改名。
- **PCIe 槽位标识是 PCIe region 基址，不是 DT 节点地址**（RK3568 实测）：
  `pcie2x1`(DT fe260000) = **`3c0000000.pcie`**（常插 WiFi，`mt7915e` 也在这里）、
  `pcie3x1`(fe270000) = **`3c0400000.pcie`**、`pcie3x2`(fe280000) = **`3c0800000.pcie`**。
  取法：`readlink -f /sys/class/net/<if>/device` 逐段找 `.pcie` 结尾的名字
  （`grep fe2xxxxx` 匹配不到）。

---

## 7. 工具

| 脚本 | 作用 |
|---|---|
| `tools/integrate.py` | 把本仓库合并进 x-wrt 树（board.d 分支级合并、armv8.mk 设备替换、U-Boot 变体登记）。**幂等**，重复跑结果一致 |
| `tools/gen_configs.py` | 由一份全机型 `.config` 生成 16 份单机型 config，并校验"该选的包还在、不该选的不在" |
| `tools/build_single.sh` | 逐机型编译（单机型模式），带 feed 同名包清理、断点续跑 |
| `tools/gen_release_cfg.py` | 发行版 config（分区 128/1024 + passwall/openclash/ttyd/upnp） |
| `tools/check_phandle.py` / `dts_syntax_check.py` / `verify_dtb.py` | DTS 自检 |
| `tools/check_port_count.py` / `verify_boardd.py` | 校验 `02_network` 与 DTS 的网口数是否对得上 |

### 为什么必须单机型模式

多机型模式 `PER_DEVICE_ROOTFS=n` 会让所有机型**共用一份 rootfs**，`.config` 里
`=y` 的包会跑到每一个机型上（5G 复位面板会落到全部 16 台）。
单机型模式下每机型独立 rootfs，产物与 `configs/<机型>.config` 一一对应。

---

## 8. 已知限制

- **H29K / H88K / H89K 的屏没有用户态程序驱动** —— fbtft 只提供 `/dev/fbN`，
  `luci-app-oled` 只服务 I²C SSD1306（H69K / H69K-mini）。
- **h88k-v3 的屏走 `spidev` + 用户态**（DTS 里没有 fbtft 面板参数），
  想改 fbtft 方案要自己补 `panel` 节点（`CONFIG_FB_TFT_ST7789V=y` 已内建）。
- **natflow 在 rockchip 无硬件 offload**（见文首说明）。
- 多口机型 LAN 各口 MAC 相同（见 §4）。
