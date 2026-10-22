### 2026-10-22 更新：修「默认两个 5G SSID 导致 MT7921 整个 radio 起不来」

16 机型全部重编（32 个镜像 + `sha256sums.txt` 一并替换）。

x-wrt 的 `base-config-setting/wifi-init.sh` 在首启时会给**每个 5g radio** 再加一个
`${SSID}_5G` 的 AP，判据只有「`phy0` 是不是 mt76」。MT7915 的 wiphy 允许 16 个 AP，
但 **MT7921 / 7922 / 7925 只允许 1 个**（`mt792x_core.c` 的 `if_limits[]`）⇒ 第二个
AP 在 netdev `up` 时被 cfg80211 拒掉（组合表里 `#{AP} <= 1` 已用满 → `-EBUSY`），
hostapd 随即把该 radio 的所有 BSS deinit 并退出（`Unable to setup interface.`），
**整个 5G radio 一个 SSID 都起不来**（2.4G 是另一个 radio/进程，不受影响）。

本批改用上游 `com.x-wrt` 的修法（`dd88782` + `d13ee65`）：
`wifi_is_single_bss()` 先用 `iw phy $phy info` 里的 `#{ AP } <= 1` 判断（通用），
再退到驱动名 `*mt792*` / debugfs 的 `mt76/deep-sleep`；phy 也从 radio 自己解析，
不再写死 `phy0`。

⚠️ 老配置里如果还留着 `*_5G` 的 wifi-iface，升级时请用 `sysupgrade -n`，
或手工清掉：

```sh
uci show wireless | grep _5G      # 找到那条的 section 名
uci delete wireless.<section>
uci commit wireless && wifi reload
```

---

