# CS2ZE Web to Client Protocol (v1)

This document defines the `postMessage` contract between the embedded `/embed/servers` page and a desktop container client.

## Version

- `v`: `1`

## Common message schema

```json
{
  "type": "CS2ZE_READY | CS2ZE_JOIN | CS2ZE_COPY | CS2ZE_SUBSCRIBE_MAP",
  "v": 1,
  "nonce": "value from URL query nonce",
  "payload": {}
}
```

## Target origin

- `targetOrigin` must be a concrete origin such as `https://example.com`.
- Do not use `*`.

## Message types

### `CS2ZE_READY`

```json
{
  "features": ["join", "copy", "subscribe_map"]
}
```

### `CS2ZE_JOIN`

```json
{
  "ip": "1.2.3.4",
  "port": 27015,
  "name": "Server Name"
}
```

### `CS2ZE_COPY`

```json
{
  "text": "connect 1.2.3.4:27015",
  "kind": "connect"
}
```

### `CS2ZE_SUBSCRIBE_MAP`

```json
{
  "map": "ze_example_map"
}
```

## Fallback behavior in normal browsers

- If `nonce` is missing, no message is posted to the host.
- Join/Copy actions degrade to copying the `connect` command.
- Without `client=tauri`, the page remains browsable but does not trigger native host actions.
