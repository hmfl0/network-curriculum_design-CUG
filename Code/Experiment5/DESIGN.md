# Experiment 5: 可靠传输设计文档

## 整体架构

```
┌─────────────────────────────────────────────────────────┐
│              应用层 (User Commands)                      │
├─────────────────────────────────────────────────────────┤
│  send <ID> <MSG>  | table | corrupt | loss | help      │
├─────────────────────────────────────────────────────────┤
│              运输层 (Transport Layer)                     │
├──────────────────┬──────────────────────────────────────┤
│ 发送端 (TX)      │ 接收端 (RX)                          │
│ - SYN初始化      │ - CRC32校验                          │
│ - 停等协议       │ - 序列号验证                         │
│ - 超时重传       │ - 去重/失序处理                      │
│ - ACK等待        │ - SYN-ACK/ACK确认                    │
├──────────────────┼──────────────────────────────────────┤
│              网络层 (Network Layer)                      │
├──────────────────┬──────────────────────────────────────┤
│ 邻居发现 (HELLO) │ 路由更新 (DV)  │ 转发 (DATA)       │
├─────────────────────────────────────────────────────────┤
│              链路层 (Serial Port)                        │
└─────────────────────────────────────────────────────────┘
```

## 关键数据结构

### 1. 接收端状态
```python
self.expected_seqs = {}  # Dict[SrcID, NextExpectedSeq]
# 追踪每个发送方期望的下一个序列号
```

### 2. 发送端状态
```python
self.seq_num = 0                  # 当前发送序列号
self.ack_event = Event()          # 等待ACK的信号
self.received_ack_seq = -1        # 收到的ACK序列号
self.simulate_error = False       # 校验码错误模拟
self.simulate_loss = False        # 丢包模拟
```

### 3. 运输帧格式
```
<字段>          <类型>      <含义>
SrcPort        整数        源端口（通常为0）
DstPort        整数        目标端口（通常为0）
Seq            整数        序列号
Checksum       整数        CRC32校验码
Type           字符串      SYN | SYN-ACK | DAT | ACK
Body           字符串      数据内容
```

## 协议流程

### A. 发送流程（停等协议）

```
发送端                           网络                          接收端
  |                              |                              |
  |-- 生成Seq (随机) -----------→|                              |
  |                              |                              |
  |-- 计算CRC32校验码            |                              |
  |                              |                              |
  |-- 模拟错误？ (corrupt on)     |                              |
  |   ├─ 是 → 篡改校验码          |                              |
  |   └─ 否 → 保持正确            |                              |
  |                              |                              |
  |-- 模拟丢包？ (loss on)        |                              |
  |   ├─ 是 → 假装发送，实际不发   |                              |
  |   └─ 否 → 正常发送            |                              |
  |                              |                              |
  |-- 发送SYN包 ───────────────→ |                              |
  |                              |-- 解析运输帧                 |
  |                              |-- CRC32校验                  |
  |                              |   ├─ 失败 → 丢弃，不回复      |
  |                              |   └─ 成功 → 继续             |
  |                              |-- 检查Seq = expected?       |
  |                              |   ├─ 是 → 交付应用层        |
  |                              |   ├─ 否(重复) → 仍发ACK     |
  |                              |   └─ 否(失序) → 不发ACK     |
  |                              |                              |
  |                      ← ────SYN-ACK─────────────            |
  |-- 等待ACK (3秒超时)          |                              |
  |   ├─ 收到 → 成功              |                              |
  |   ├─ 超时 → 重传              |                              |
  |   └─ 重试3次                  |                              |
```

### B. 关键决策点

**发送端：校验码错误处理**
- 模拟开启时，第一次发送包的校验码被篡改
- 接收端检测失败，不回复ACK
- 发送端超时后自动重传
- 重传时校验码正确，接收端确认成功

**接收端：序列号处理**
```
收到包的Seq
  ├─ == expected → 交付，更新expected = Seq + 1
  ├─ < expected  → 重复，仍回ACK（帮助发送端确认）
  └─ > expected  → 失序，不回ACK（等待发送方重传之前的包）
```

## 核心算法

### 1. CRC32校验
```python
def _calculate_checksum(self, src, dst, seq, t_type, body):
    # 伪首部 + 数据内容
    content = f"{src}|{dst}|{seq}|{t_type}|{body}"
    return zlib.crc32(content.encode('utf-8')) & 0xffffffff
```
- 校验完整帧内容，包括源、目标、序列号、类型
- 检测数据篡改和传输错误

### 2. 停等协议
```python
for attempt in range(MAX_RETRIES):
    send_packet()
    if wait_for_ack(timeout=3.0):
        break  # 成功
    # 否则继续重传
```
- 简单高效的重传机制
- 易于实现和验证，但效率低

### 3. 序列号同步
```python
# 发送端
seq = random.randint(0, 65535)  # 初始序列号

# 接收端
expected_seqs[sender_id] = seq + 1  # 期望下一个
```
- 类似TCP的ISN机制
- 防止旧连接的包被误接受

## 错误处理场景

### 场景1：校验码错误
```
TX: 发送SYN (Seq=1000, 校验码=WRONG)
RX: 收到 → CRC检验 → 失败 → 丢弃 → 不回ACK
TX: 等待3秒无ACK → 超时 → 重传
TX: 发送SYN (Seq=1000, 校验码=CORRECT)
RX: 收到 → CRC检验 → 成功 → 回复SYN-ACK
TX: 收到SYN-ACK → 成功
```

### 场景2：丢包
```
TX: 发送SYN (Seq=2000)
→  [模拟丢包，实际没有发送]
TX: 等待3秒无ACK → 超时 → 重传
TX: 发送SYN (Seq=2000)  [第2次]
RX: 收到 → 回复SYN-ACK
TX: 收到SYN-ACK → 成功
```

### 场景3：重复包
```
TX: 发送SYN (Seq=3000)
RX: 收到 → 回复SYN-ACK → 交付应用层
TX: 等待ACK (正常收到)

[网络延迟，TX重传同一个包]
TX: 重传SYN (Seq=3000)
RX: 收到 (Seq=3000 < expected=3001) → 识别为重复
    仍发送ACK (Seq=3000) → 帮助TX确认
TX: 收到ACK → 成功
```

### 场景4：失序包
```
TX: 发送 Seq=4000
RX: 期望 Seq=4000 → 成功交付 → expected=4001

TX: 发送 Seq=4002  [跳过了4001]
RX: 收到 (Seq=4002 > expected=4001) → 失序
    不回ACK (等待Seq=4001)
TX: 等待ACK超时 → 重传 Seq=4002
RX: 仍期望4001 → 仍不回ACK
... [继续直到Seq=4001到达]
```

## 时间参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `TIMEOUT_RETRANSMIT` | 3秒 | 等待ACK的超时时间 |
| `MAX_RETRIES` | 3次 | 最大重传次数 |
| `HELLO_INTERVAL` | 3秒 | 邻居发现间隔 |
| `DV_INTERVAL` | 5秒 | 路由更新间隔 |
| `NEIGHBOR_TIMEOUT` | 10秒 | 邻居超时判定 |

## 线程模型

```
Main Thread (UI)
├─ input_loop()          [阻塞等待用户输入]
├─ send()               [阻塞，等待ACK（停等）]
└─ print()

Background Threads:
├─ _listen_port() × N    [每个串口一个，接收数据]
├─ _task_hello()        [定期发送HELLO]
├─ _task_broadcast_dv() [定期广播路由表]
└─ _task_check_timeout() [定期检测邻居超时]

同步机制:
├─ ack_event            [等待ACK的Event]
├─ neighbors_lock       [邻居表保护锁]
├─ rt_lock              [路由表保护锁]
└─ port_locks × N       [每个串口的发送互斥锁]
```

## 完整流程示例

### 场景：A向C发送消息（B中继）

```
时间轴：
T=0s:
  A启动 → 发送HELLO
  B启动 → 发送HELLO
  C启动 → 发送HELLO

T=1s-5s:
  相互发现，构建邻居表
  A: 邻居={B}, 路由表={A:0, B:1}
  B: 邻居={A,C}, 路由表={B:0, A:1, C:1}
  C: 邻居={B}, 路由表={C:0, B:1}

T=5s-15s:
  交换DV，更新路由表
  A: 路由表={A:0, B:1, C:2(via B)}
  B: 路由表={A:1, B:0, C:1}
  C: 路由表={A:2(via B), B:1, C:0}

T=20s:
  用户命令: send C "Hello"

T=20.0s:
  A生成 Seq=12345
  A计算 CRC32(A|C|12345|SYN|Hello)=0xABCD1234
  A构造 SYN包: 0|0|12345|0xABCD1234|SYN|Hello
  A查路由表: 去往C的下一跳是B (COM3)
  A→B 发送SYN包

T=20.05s:
  B收到来自A的DATA|A|C|...
  B识别为中继数据 (src=A, dst=C)
  B查路由表: C的下一跳是C本身 (COM5)
  B→C 转发DATA包

T=20.1s:
  C收到DATA|A|C|...
  C识别为本地数据 (dst=C)
  C解析运输帧
  C验证CRC32 ✓
  C识别Seq=12345=expected ✓
  C回复SYN-ACK

T=20.15s:
  B收到来自C的DATA|C|A|...
  B识别为中继ACK
  B→A 转发ACK包

T=20.2s:
  A收到ACK
  A验证Seq=12345 ✓
  A设置 ack_event
  A主线程从wait()返回
  输出: "=== 发送成功 ==="

总耗时: 0.2秒
```

## 性能特性

### 优点
- ✅ 实现简洁，易于理解和调试
- ✅ 完全可靠（在理论上）
- ✅ 易于检测故障（超时明显）
- ✅ 便于验证（停等特性清晰）

### 缺点
- ❌ 效率低（停等期间无法发送）
- ❌ 吞吐量低（受RTT和超时限制）
- ❌ 对高延迟网络不友好（超时时间固定）

### 复杂度
- 时间复杂度: 发送一次消息 O(retries × timeout)
- 空间复杂度: O(邻居数 + 已知目标数 + 在途连接数)

## 扩展建议

1. **滑动窗口**: 一次发送多个包，提高吞吐量
2. **自适应超时**: 根据历史RTT调整超时
3. **快速重传**: 收到3个重复ACK立即重传
4. **序列号轮转**: 处理序列号32位溢出
5. **连接状态机**: 三步握手、断开等
6. **流量控制**: 接收窗口通知、背压机制

## 测试清单

- [ ] 正常通信（1跳）
- [ ] 正常通信（多跳）
- [ ] 校验错误恢复（corrupt on）
- [ ] 丢包恢复（loss on）
- [ ] 连续发送（3-5条消息）
- [ ] 大消息传输（1000字节以上）
- [ ] 路由变动（断开链路）
- [ ] 邻居超时（断电10秒+）
- [ ] 压力测试（频繁发送）
- [ ] 多跳可靠性（3个以上节点）
