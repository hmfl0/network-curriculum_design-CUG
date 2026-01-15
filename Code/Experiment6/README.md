# Experiment 6: 简单网络管理实验 (Ping / Traceroute)

本目录包含实验六的代码实现。实验六在网络层增加了 TTL (Time To Live) 处理机制，并实现了基于 ICMP (互联网控制消息协议) 思想的 Ping 和 Traceroute 工具。

## 功能特性

1.  **TTL 转发与丢弃**: 路由器在转发数据包时会自动将 TTL 减 1，当 TTL 归零时丢弃并返回超时消息。
2.  **Ping**: 检测目标节点的可达性，计算往返时延 (RTT) 和丢包率。
3.  **Traceroute**: 利用 TTL 递增原理，探测到达目标节点路径上的所有中间跳数。

## 使用方法

### 环境准备
确保所有参与实验的节点都运行此版本的代码，因为实验四/五的代码不支持 TTL 协议字段，混合运行会导致解析错误。

```shell
pip install pyserial
```

### 启动节点
在每台 PC 上运行：
```shell
python Code/Experiment6/network_app.py
```

### 操作指南

1.  **初始化**: 输入本机 ID 并选择串口（等待 10-15 秒路由收敛）。
2.  **Ping 测试**:
    ```shell
    > ping B
    Ping B with 32 bytes of data:
    来自 B 的回复: time=12.0ms
    ...
    ```
3.  **路由追踪**:
    ```shell
    > tracert C
    Tracing route to C over a maximum of 15 hops:
    1    10ms     B
    2    22ms     C
    Trace complete.
    ```
