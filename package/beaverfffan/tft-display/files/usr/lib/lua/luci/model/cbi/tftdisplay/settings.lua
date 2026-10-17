local m, s, o
local fs = require "nixio.fs"
local sys = require "luci.sys" -- 确保正确加载 sys 模块

-- 添加 By Fish 的超链接
local description = [[
配置显示模式、屏幕设置和硬件接口。<br>
]]

m = Map("tftdisplay", "屏幕信息设置", description)

-- 主设置部分
s = m:section(TypedSection, "global", "设置")
s.anonymous = true
s.addremove = false

-- 屏幕启用选项
-- o = s:option(Flag, "screen_enabled", "启用屏幕", "切换屏幕开启或关闭。")
-- o.default = "1"
-- o.rmempty = false -- 确保选项值为 0 时也写入配置文件

o = s:option(ListValue, "display_resolution", "屏幕尺寸", "选择 LVGL 屏幕尺寸。")
o:value("1.14", "1.14屏幕")
o:value("1.9", "1.9屏幕")
o.default = "1.14"

o = s:option(ListValue, "display_template", "屏幕模板", "选择 模板样式。")
o:value("1", "默认")
o.default = "1"

o = s:option(ListValue, "display_Backlight", "屏幕背光", "选择 屏幕背光  （仅V1.3版本支持）模式。")
o:value("2", "日夜模式")
o:value("1", "开启背光")
o:value("0", "关闭背光")
o.default = "2"




-- 添加指示灯启用选项
-- o = s:option(Flag, "indicator_enabled", "启用 4G/5G 指示灯", "启用或禁用 4G/5G 指示灯功能。")
-- o.default = "0" -- 默认关闭
-- o.rmempty = false

-- 动态加载网口
-- o = s:option(ListValue, "network_interface", "网络接口", "选择网络接口。")
-- local net_interfaces = fs.dir("/sys/class/net")
-- if net_interfaces then
--     for interface in net_interfaces do
--         if interface ~= "lo" then -- 忽略本地环回接口
--             o:value(interface, interface)
--         end
--     end
-- end
-- o.default = "br-lan"


-- 添加保存后的服务重启逻辑
function m.on_after_commit(self)
    sys.call("/etc/init.d/tftdisplay restart") -- 确保 sys 模块正确加载
end

return m
