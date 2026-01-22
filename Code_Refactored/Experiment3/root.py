"""
实验三：简单拓扑的多机通信实验（链路层） - 根节点 (Root/Switch)
功能：作为树形拓扑的根节点，管理多个串口，负责数据帧的转发
核心逻辑：
1. 维护 转发表 (Routing Table): 记录 设备ID -> 对应串口 的映射
2. 监听所有连接的串口
3. 收到数据后，解析目标ID (Target ID)
4. 查询转发表，将数据转发到对应的串口
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

class PortListener(threading.Thread):
    def __init__(self, port, baudrate, callback, user_id="Unknown"):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.callback = callback
        self.user_id = user_id # 该端口连接的设备ID
        self.ser = None
        self.running = False

    def run(self):
        try:
            self.ser = create_serial_connection(self.port, self.baudrate, timeout=0.1)
            if self.ser:
                self.running = True
                Logger.info(f"[{self.port}] 端口已打开，连接设备: {self.user_id}")
                
                while self.running:
                    if self.ser.in_waiting:
                        try:
                            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                            if line:
                                self.callback(line, self.port)
                        except Exception as e:
                            Logger.error(f"[{self.port}] 读取错误: {e}")
                    time.sleep(0.01) # 避免CPU占用过高
            else:
                self.running = False
        except Exception as e:
            Logger.error(f"[{self.port}] 初始化失败: {e}")
            self.running = False

    def send(self, data):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((data + '\n').encode('utf-8'))
                return True
            except Exception as e:
                Logger.error(f"[{self.port}] 发送失败: {e}")
        return False

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

class RootNode:
    def __init__(self):
        self.listeners = {} # port_name -> PortListener
        self.routing_table = {} # node_id -> port_name
        self.my_id = "ROOT"

    def handle_message(self, raw_data, source_port):
        """
        处理接收到的消息
        协议格式: SRC_ID|DST_ID|PAYLOAD
        """
        parts = raw_data.split(SEPARATOR, 2)
        if len(parts) != 3:
            Logger.debug(f"[收到畸形帧] {raw_data} 来自 {source_port}")
            return

        src_id, dst_id, payload = parts
        
        # 显示接收日志
        print(f"[RECV] {src_id} -> {dst_id} : {payload} (来自 {source_port})")

        # 判断是否发给自己
        if dst_id == self.my_id:
            print(f"  >>> 收到发给自己的消息: {payload}")
            return

        # 查表转发
        if dst_id in self.routing_table:
            target_port = self.routing_table[dst_id]
            
            # 避免回环（虽然逻辑上查表不会查回原端口，除非路由表配置错误）
            if target_port == source_port:
                Logger.warning(f"  [警告] 目标端口与源端口相同，丢弃")
                return

            if target_port in self.listeners:
                print(f"  >>> 转发至端口 {target_port} (目标: {dst_id})")
                success = self.listeners[target_port].send(raw_data)
                if not success:
                    Logger.error(f"  [ERROR] 转发失败")
            else:
                Logger.error(f"  [ERROR] 目标端口 {target_port} 未在监听列表")
        else:
            Logger.warning(f"  [丢弃] 未知目标ID: {dst_id} (转发表中不存在)")

    def add_port(self, port, baudrate, connected_id):
        if port in self.listeners:
            Logger.warning(f"端口 {port} 已经在使用了")
            return
        
        listener = PortListener(port, baudrate, self.handle_message, connected_id)
        listener.start()
        self.listeners[port] = listener
        self.routing_table[connected_id] = port
        Logger.success(f"路由添加成功: 目标 {connected_id} -> 端口 {port}")

    def stop(self):
        for listener in self.listeners.values():
            listener.stop()

def main():
    root = RootNode()
    print("="*60)
    print("实验三：简单拓扑的多机通信实验 - 根节点 (Root)")
    print("="*60)
    
    # 配置波特率
    baudrate = 9600
    
    # 交互式添加连接
    print("\n请配置连接的叶子节点")
    while True:
        # 使用 utils 选择器
        port = select_serial_port("选择端口 (或选择退出)")
        
        if not port:
            break
        
        # 检查是否已经配置过
        if port in root.listeners:
            print(f"端口 {port} 已经配置过了，请选择其他串口")
            continue

        node_id = input(f"该端口 ({port}) 连接的设备ID是? (例如 ID2): ").strip()
        if not node_id:
            print("设备ID不能为空")
            continue

        root.add_port(port, baudrate, node_id)
        
        cont = input("是否继续添加端口? (y/n) [y]: ").strip().lower()
        if cont == 'n':
            break

    if not root.listeners:
        Logger.info("未配置任何端口，程序退出")
        return

    print("\n" + "="*60)
    print(f"系统启动完成。本机ID: {root.my_id}")
    print("转发表:")
    for nid, port in root.routing_table.items():
        print(f"  {nid} <==> {port}")
    print("系统正在监听并转发数据... (按 Ctrl+C 退出)")
    print("="*60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        Logger.info("正在停止所有端口监听...")
        root.stop()
        print("程序已退出")

if __name__ == '__main__':
    main()
