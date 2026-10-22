# feed-files/ —— 对上游 feed 文件的**整份覆盖**

这里的文件不是我们写的，是 x-wrt 上游 `com.x-wrt` 的版本，用于在**我们钉住的
feed 分支还没带上某个修复**时，先把修复铺进去。

## 目录

| 路径 | 对应上游 | 说明 |
|---|---|---|
| `base-config-setting/wifi-init.sh` | `com.x-wrt` `base-config-setting/files/wifi-init.sh`（master） | 含 `dd88782`「do not set SSID_5G for single BSS and fix hardcoded phy0」+ `d13ee65`「improve Cypress/Broadcom detection and fix htmode」 |

取回方式：

```
curl -fsSL -o wifi-init.sh \
  https://raw.githubusercontent.com/x-wrt/com.x-wrt/master/base-config-setting/files/wifi-init.sh
```

本次收录的版本：**275 行 / 7757 字节 / md5 79ba36f5023de4d68c808dcf75b38d42**（2026-10-22 取）。

## 规则

- `tools/integrate.py` 的第 10 步只在**树里的文件还没有该修复**时才覆盖
  （判据：文件里是否出现 `wifi_is_single_bss`）。所以 feeds 一旦更新到含
  `dd88782` 的版本，这一步会自动变成 no-op，不会挡住上游后续改动。
- 覆盖目标是 `feeds/x/base-config-setting/files/wifi-init.sh`，
  `./scripts/feeds update -a` 会把覆盖冲掉 ⇒ 之后重跑 `integrate.py` 即可。
- 新增覆盖文件时，请在这里登记来源 URL 与校验值，别改了内容却不留出处。
