"""
实验二：双机通信实验（C/S模式） - 服务器端
功能：作为服务器接收客户端请求，处理后返回响应
"""

import threading
import time
import sys
import os

# 导入 utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import Logger, select_serial_port, create_serial_connection, choose_serial_format

class SerialServer:
    def __init__(self):
        self.ser = None
        self.running = False
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
        print(f"[DEBUG {ts}] {direction}: len={len(payload)} raw={raw} hex={hex_str}")
    
    def open_port(self, port_name, baudrate=9600, bytesize=8, stopbits=1, parity='N'):
        """打开串口"""
        self.ser = create_serial_connection(port_name, baudrate, 1, bytesize, stopbits, parity)
        if self.ser:
            Logger.success(f"服务器串口 {port_name} 打开成功")
            return True
        else:
            return False
    
    def close_port(self):
        """关闭串口"""
        self.running = False
        if self.recv_thread:
            self.recv_thread.join(timeout=2)
        if self.ser and self.ser.is_open:
            self.ser.close()
            Logger.info("服务器串口已关闭")
    
    def send_data(self, data):
        """发送数据"""
        if self.ser and self.ser.is_open:
            try:
                if isinstance(data, str):
                    data = data.encode('utf-8')
                self.ser.write(data)
                self._log('SEND', data)
                return True
            except Exception as e:
                Logger.error(f"发送失败: {e}")
                return False
        return False
    
    def process_request(self, request):
        """处理客户端请求"""
        request_str = request.decode('utf-8', errors='ignore').strip()
        
        # 根据不同的请求类型返回不同的响应
        if request_str.upper().startswith("HELLO"):
            response = "SERVER: Hello, Client! Connection established."
        elif request_str.upper().startswith("TIME"):
            response = f"SERVER: Current time is {time.strftime('%Y-%m-%d %H:%M:%S')}"
        elif request_str.upper().startswith("ECHO"):
            # Echo 服务，返回客户端发送的内容
            echo_content = request_str[5:].strip()
            response = f"SERVER: ECHO - {echo_content}"
        elif request_str.upper().startswith("CALC"):
            # 简单计算服务
            try:
                expr = request_str[5:].strip()
                result = eval(expr)
                response = f"SERVER: CALC - {expr} = {result}"
            except:
                response = "SERVER: ERROR - Invalid calculation expression"
        elif request_str.upper().startswith("QUIT"):
            response = "SERVER: Goodbye!"
            return response, True  # 返回退出标志
        else:
            response = f"SERVER: Unknown command '{request_str}'. Available: HELLO, TIME, ECHO <msg>, CALC <expr>, QUIT"
        
        return response, False
    
    def receive_worker(self):
        """接收数据的工作线程"""
        Logger.info("服务已启动，等待客户端连接...")
        while self.running:
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.readline()
                    if data:
                        self._log('RECV', data)
                        
                        # 处理请求并返回响应
                        response, should_quit = self.process_request(data)
                        time.sleep(0.1)  # 短暂延迟，确保客户端准备好接收
                        self.send_data(response + "\n")
                        
                        if should_quit:
                            Logger.info("收到退出请求，准备关闭...")
                            # self.running = False # Server usually keeps running or restarts, but here we break conform to logic
                            # But wait, original code broke here.
                            self.running = False
                            break
                else:
                    time.sleep(0.01)
            except Exception as e:
                if self.running:
                    Logger.error(f"接收数据异常: {e}")
                    time.sleep(0.1)
    
    def start_server(self):
        """启动服务器"""
        if not self.ser or not self.ser.is_open:
            Logger.error("请先打开串口")
            return False
        
        self.running = True
        self.recv_thread = threading.Thread(target=self.receive_worker, daemon=True)
        self.recv_thread.start()
        return True

def main():
    server = SerialServer()
    
    print("=" * 60)
    print("实验二：双机通信实验 - 服务器端（C/S模式）")
    print("=" * 60)
    
    # 1. 选择串口
    selected_port = select_serial_port("请选择服务器串口")
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
    if not server.open_port(selected_port, baudrate, bytesize, stopbits, parity):
        return
    
    if server.start_server():
        try:
            while server.running:
                time.sleep(1)
        except KeyboardInterrupt:
            Logger.info("正在停止服务器...")
        finally:
            server.close_port()

if __name__ == "__main__":
    main()
