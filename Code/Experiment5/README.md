# Experiment 5: 多机可靠传输实验

本目录包含实验五的代码实现，基于实验四的路由功能，增加了运输层可靠传输机制。

## 文件说明

- `reliable_router.py`: 主程序，集成了路由器和可靠发送/接收端的功能。

## 运行方式

1. **环境准备**
   确保已安装 `pyserial` 库：
   ```shell
   pip install pyserial
   ```

2. **启动程序**
   在每一台参与实验的计算机上运行：
   ```shell
   python Code/Experiment5/reliable_router.py
   ```

3. **操作流程**
   - 启动后输入本机 ID（如 `A`）。
   - 选择串口（输入 `all` 或指定 COM 口，如 `COM3,COM4`）。
   - 等待路由收敛（约 10-15 秒），可使用 `table` 查看路由表。
   - 发送可靠消息：
     ```shell
     send <目标ID> <消息内容>
     # 例如: send B HelloReliable
     ```
   - 程序会自动等待 ACK，若超时会自动重传。

4. **模拟错误测试**
   - 开启校验码篡改模拟：
     ```shell
     corrupt on
     ```
   - 此时发送的一条消息，其校验码会被故意改为错误值。
   - 观察接收端是否报错丢弃，以及发送端是否超时重传。
   - 关闭模拟：
     ```shell
     corrupt off
     ```
