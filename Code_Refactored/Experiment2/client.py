"""
实验二：双机通信实验（C/S模式） - 客户端
功能：作为客户端向服务器发送请求，并接收响应
"""

import threading
import time
import sys
import os

# 导入 utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import Logger, select_serial_port, create_serial_connection, choose_serial_format

class SerialClient:
    def __init__(self):
        self.ser = None
        self.receiving = False
        self.recv_thread = None
        self.debug = True

    def _log(self, direction, payload):
        """调试输出，带时间戳和方向"""
        if not self.debug:
            return
        ts = time.strftime('%H:%M:%S')
        if not isinstance(payload, bytes):
            payload = str(payload).encode('utf-8', errors='ignore')
        raw = repr(payload)
        hex_str = ' '.join(f"{b:02X}" for b in payload)
        # 使用 utils 的 debug 也可以，但这里格式比较特殊，保留原样但用 print
        print(f"[DEBUG {ts}] {direction}: len={len(payload)} raw={raw} hex={hex_str}")
    
    def open_port(self, port_name, baudrate=9600, bytesize=8, stopbits=1, parity='N'):
        """打开串口"""
        self.ser = create_serial_connection(port_name, baudrate, 1, bytesize, stopbits, parity)
        if self.ser:
            parity_str = str(parity) # might be object
            Logger.success(f"客户端串口 {port_name} 打开成功")
            Logger.info(f"配置: Baud {baudrate}")
            
            # 自动启动接收线程
            self.receiving = True
            self.recv_thread = threading.Thread(target=self._receive_worker, daemon=True)
            self.recv_thread.start()
            return True
        else:
            return False
    
    def close_port(self):
        """关闭串口"""
        self.receiving = False
        if self.recv_thread:
            self.recv_thread.join(timeout=2)
        if self.ser and self.ser.is_open:
            self.ser.close()
            Logger.info("客户端串口已关闭")
    
    def send_request(self, request):
        """发送请求到服务器"""
        if self.ser and self.ser.is_open:
            try:
                if isinstance(request, str):
                    request = request.encode('utf-8')
                # 确保请求以换行符结尾，便于服务器读取
                if not request.endswith(b'\n'):
                    request += b'\n'
                self.ser.write(request)
                self._log('SEND', request)
                return True
            except Exception as e:
                Logger.error(f"发送失败: {e}")
                return False
        return False
    
    def _receive_worker(self):
        """接收数据的工作线程"""
        while self.receiving:
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.readline()
                    if data:
                        self._log('RECV', data)
                        # 简单的回显给用户看
                        try:
                            print(f"[收到] {data.decode('utf-8').strip()}")
                        except:
                            pass
                else:
                    time.sleep(0.01)
            except Exception as e:
                if self.receiving:
                    Logger.error(f"接收数据异常: {e}")
                    time.sleep(0.1)

def main():
    client = SerialClient()
    
    print("=" * 60)
    print("实验二：双机通信实验 - 客户端（C/S模式）")
    print("=" * 60)
    
    # 1. 选择串口
    selected_port = select_serial_port("请选择客户端串口")
    if not selected_port:
        return

    # 2. 设置波特率
    while True:
        try:
            bps_input = input("请输入波特率 (默认9600): ").strip()
            baudrate = int(bps_input) if bps_input else 9600
            break
        except ValueError:
            Logger.error("请输入有效的波特率")

    # 3. 选择串口格式
    bytesize, stopbits, parity, fmt_label = choose_serial_format()
    Logger.info(f"选用格式: {fmt_label}，波特率 {baudrate}")
    
    # 4. 打开串口
    if not client.open_port(selected_port, baudrate, bytesize, stopbits, parity):
        return
    
    print("\n" + "=" * 60)
    print("客户端命令说明:")
    print("  HELLO          - 向服务器发送问候")
    print("  TIME           - 请求服务器当前时间")
    print("  ECHO <msg>     - 回显消息")
    print("  CALC <expr>    - 计算表达式，例如: CALC 2+3*4")
    print("  QUIT           - 断开连接并退出")
    print("  help           - 显示帮助信息")
    print("=" * 60 + "\n")
    
    # 发送初始连接请求
    Logger.info("正在连接服务器...")
    time.sleep(0.5)  # 等待服务器就绪
    client.send_request("HELLO")
    
    # 主循环 - 发送请求
    try:
        while True:
            request = input("\n请输入命令: ").strip()
            
            if not request:
                continue
            
            if request.lower() == 'help':
                print("\n可用命令:")
                print("  HELLO          - 向服务器发送问候")
                print("  TIME           - 请求服务器当前时间")
                print("  ECHO <msg>     - 回显消息")
                print("  CALC <expr>    - 计算表达式")
                print("  QUIT           - 断开连接并退出")
                continue
            
            # 发送请求
            client.send_request(request)
            
            # 如果是退出命令，等待响应后退出
            if request.upper() == "QUIT":
                time.sleep(0.5)  # 等待接收服务器的响应
                break
            
            time.sleep(0.1)  # 短暂延迟
            
    except KeyboardInterrupt:
        print("\n检测到中断信号")
    finally:
        client.close_port()
        print("已退出")


if __name__ == "__main__":
    main()
