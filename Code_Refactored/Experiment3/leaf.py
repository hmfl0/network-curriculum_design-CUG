"""
实验三：简单拓扑的多机通信实验（链路层） - 叶子节点 (Leaf)
功能：作为树形拓扑的叶子节点，连接到根节点
核心逻辑：
1. 仅通过一个串口连接到根节点
2. 发送数据时封装帧头 (SRC|DST|DATA)
3. 接收数据时检查 DST 是否匹配本机ID
"""

import threading
import time
import sys
import os

# 导入 utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import Logger, select_serial_port, create_serial_connection

# 数据帧分隔符
SEPARATOR = '|'

class LeafNode:
    def __init__(self):
        self.ser = None
        self.running = False
        self.my_id = None
        self.recv_thread = None

    def connect(self, port, baudrate, my_id):
        self.ser = create_serial_connection(port, baudrate, timeout=0.1)
        if self.ser:
            self.my_id = my_id
            self.running = True
            
            # 启动接收线程
            self.recv_thread = threading.Thread(target=self._receive_loop)
            self.recv_thread.daemon = True
            self.recv_thread.start()
            
            Logger.success(f"成功连接至 {port}，本机ID设置为: {self.my_id}")
            return True
        else:
            return False

    def _receive_loop(self):
        Logger.info(f"开始监听来自端口的数据...")
        while self.running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self._process_frame(line)
                time.sleep(0.01)
            except Exception as e:
                Logger.error(f"接收线程异常: {e}")
                break

    def _process_frame(self, raw_data):
        """
        处理接收到的帧
        格式: SRC_ID|DST_ID|PAYLOAD
        """
        parts = raw_data.split(SEPARATOR, 2)
        if len(parts) != 3:
            return

        src_id, dst_id, payload = parts

        if dst_id == self.my_id:
            print(f"\n[收到消息] 来自 {src_id}: {payload}")
            print(f"> ", end="", flush=True) # 恢复提示符
        elif dst_id == "BROADCAST": # 可选：支持广播
             print(f"\n[收到广播] 来自 {src_id}: {payload}")
             print(f"> ", end="", flush=True)
        else:
            # 目标不是自己，忽略
            pass

    def send_message(self, target_id, message):
        if not self.ser or not self.ser.is_open:
            Logger.warning("串口未连接")
            return

        # 封装帧
        # 格式: SRC|DST|MSG
        frame = f"{self.my_id}{SEPARATOR}{target_id}{SEPARATOR}{message}\n"
        try:
            self.ser.write(frame.encode('utf-8'))
            print(f"[发送成功] -> {target_id}: {message}")
        except Exception as e:
            Logger.error(f"发送失败: {e}")

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

def main():
    leaf = LeafNode()
    print("="*60)
    print("实验三：简单拓扑的多机通信实验 - 叶子节点 (Leaf)")
    print("="*60)
    
    # 1. 选择串口
    selected_port = select_serial_port("请选择连接根节点的串口")
    if not selected_port:
        return
    
    # 2. 配置 ID
    while True:
        my_id = input("请输入本机识别ID (例如 ID2): ").strip()
        if my_id:
            break
        print("ID不能为空")
    
    # 3. 连接
    if not leaf.connect(selected_port, 9600, my_id):
        return

    print("\n" + "="*60)
    print("操作说明:")
    print("  格式: 目标ID 消息内容")
    print("  例如: ID3 Hello World")
    print("  输入 'exit' 或 'quit' 退出")
    print("="*60)

    try:
        while True:
            cmd = input("> ").strip()
            if not cmd:
                continue
                
            if cmd.lower() in ('exit', 'quit'):
                break

            # 解析输入 "TARGET_ID MESSAGE"
            parts = cmd.split(None, 1)
            if len(parts) < 2:
                print("格式错误。请使用: 目标ID 消息内容")
                continue
            
            target_id, msg = parts
            leaf.send_message(target_id, msg)
            
    except KeyboardInterrupt:
        pass
    finally:
        leaf.stop()
        print("\n程序已退出")

if __name__ == '__main__':
    main()
