# /embed/servers 嵌入说明

该页面用于在桌面端或外部容器中嵌入 CS2ZE 服务器列表，仅渲染服务器列表区域，不包含主站的侧边栏/头部。

## URL 参数
- `client`：客户端标识（示例：`tauri`）。
- `nonce`：一次性随机值，用于 postMessage 校验（缺失时不会向宿主发送消息）。
- `theme`：`light` 或 `dark`，用于指定主题。
- `lang`：`zh-CN`、`zh-TW`、`en` 等语言标识。
- `tab`：视图标识（`servers` / `map_sub` / `stats` / `feedback`）。
- `dense`：`1` / `true` / `yes` 时启用紧凑布局。

示例：
```
/embed/servers?client=tauri&nonce=abc123&theme=dark&lang=zh-CN&tab=servers&dense=1
```

## postMessage 协议
嵌入模式下，页面会向 `https://www.cs2ze.org` 发送消息，结构如下：
```json
{
  "type": "CS2ZE_READY | CS2ZE_JOIN | CS2ZE_COPY | CS2ZE_SUBSCRIBE_MAP",
  "v": 1,
  "nonce": "来自 URL 的 nonce",
  "payload": {}
}
```

### 消息类型与 payload
- `CS2ZE_READY`：`{ "features": ["join","copy","subscribe_map"] }`
- `CS2ZE_JOIN`：`{ "ip": "1.2.3.4", "port": 27015, "name": "Server Name" }`
- `CS2ZE_COPY`：`{ "text": "connect ip:port", "kind": "connect" }`
- `CS2ZE_SUBSCRIBE_MAP`：`{ "map": "ze_xxx" }`
