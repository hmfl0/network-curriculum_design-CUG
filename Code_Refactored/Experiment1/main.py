import serial
import threading
import time
import sys
import os

# 将上级目录加入 sys.path 以便导入 utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import Logger, select_serial_port, create_serial_connection

class SerialAssistant:
    def __init__(self):
        self.ser = None                 # 用来存储串口对象的变量
        self.receiving = False          # 控制接收线程的标志位
        self.recv_thread = None         # 用来存放线程对象
        self.lock = threading.Lock()
        
        # Statistics for rate testing
        self.bytes_received = 0
        self.test_mode = False          # If True, suppress print and just count

    def open_port(self, port_name, baudrate=9600, timeout=1):
        """Open serial port using utils"""
        self.ser = create_serial_connection(port_name, baudrate, timeout=timeout)
        if self.ser:
            # Start receive thread automatically
            self.receiving = True
            self.recv_thread = threading.Thread(target=self._receive_worker, daemon=True)
            self.recv_thread.start()
            return True
        else:
            return False

    def close_port(self):
        """Close serial port"""
        self.receiving = False                  
        if self.recv_thread and self.recv_thread.is_alive():
            self.recv_thread.join(timeout=1)   
        
        if self.ser and self.ser.is_open:
            self.ser.close()
            Logger.info("串口已关闭。")

    def send_data(self, data):
        """Send data properly encoded"""
        if not self.ser or not self.ser.is_open:
            Logger.error("串口未打开。")
            return False

        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            self.ser.write(data)
            # Experiment 1 Req 3: Specific feedback on send success
            if not self.test_mode:
                Logger.success(f"已发送 {len(data)} 字节。")
            return True
        except Exception as e:
            Logger.error(f"发送失败: {e}")
            return False

    def _receive_worker(self):
        """
        Background thread for receiving data.
        """
        while self.receiving and self.ser and self.ser.is_open:
            try:
                # Check buffer size
                if self.ser.in_waiting > 0:         
                    # Read all available
                    data = self.ser.read(self.ser.in_waiting)
                    # Logger.debug(f"从缓冲区接收到 {len(data)} 字节")
                    self.bytes_received += len(data)
                    
                    if not self.test_mode:
                        try:
                            decoded = data.decode('utf-8')
                            print(f"\r[接收] {decoded}")
                            sys.stdout.flush()
                        except UnicodeDecodeError:
                            print(f"\r[接收(Raw)] {data}")
                            sys.stdout.flush()
                            
                time.sleep(0.01) # Small sleep to reduce CPU usage
            except Exception as e:
                if self.receiving:
                    Logger.error(f"接收出错: {e}")
                break

def run_basic_mode(assistant):
    print("\n--- 基础聊天模式 (输入 'exit' 退出) ---")
    print("输入文本进行回环测试:")

    assistant.test_mode = False # Ensure normal output

    while True:
        msg = input(">> ")
        if msg.lower() == 'exit':
            break
        assistant.send_data(msg)
        time.sleep(0.1) # Wait briefly for loopback response

def run_rate_test(assistant):
    """Experiment 1 Req 4: Max send rate test"""
    try:
        print("\n--- 最大发送速率测试 ---")
        print("正在连续发送数据流 (5秒)...")
        
        assistant.test_mode = True # Suppress printing
        assistant.bytes_received = 0
        
        start_time = time.time()
        payload = b'X' * 1024 # 1KB packets
        sent_bytes = 0
        
        try:
            while time.time() - start_time < 5:
                if assistant.send_data(payload):
                    sent_bytes += len(payload)
        except KeyboardInterrupt:
            pass
            
        duration = time.time() - start_time
        print("\n发送完成，正在计算结果...")
        
        # Since it's loopback, we check receiving speed too
        time.sleep(1) 
        
        print("-" * 30)
        print(f"耗时: {duration:.2f} s")
        print(f"总发送: {sent_bytes} 字节")
        print(f"总接收: {assistant.bytes_received} 字节")
        print(f"速率: {sent_bytes / duration / 1024:.2f} KB/s")
        if assistant.bytes_received < sent_bytes:
             Logger.warning("注意: 接收到的数据少于发送的数据，可能发生了缓冲区溢出丢包。")
    finally:
        assistant.test_mode = False

def run_long_message_test(assistant):
    """Experiment 1 Req 4: Long message test"""
    try:
        print("\n--- 长消息 (分包/粘包) 测试 ---")
        length = 10000 # 10KB message
        print(f"生成 {length} 字节的文本数据...")
        
        # Create a long identifiable string
        long_msg = "START" + "1234567890" * (length // 10) + "END"
        
        assistant.test_mode = True # Use clean output mode
        assistant.bytes_received = 0
        
        print("开始发送...")
        start_time = time.time()
        assistant.send_data(long_msg)
        
        print("等待接收完成...")
        timeout = 10 
        last_bytes = 0
        while assistant.bytes_received < len(long_msg) and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5
            if assistant.bytes_received > last_bytes:
                progress = (assistant.bytes_received / len(long_msg)) * 100
                print(f"  进度: {assistant.bytes_received}/{len(long_msg)} ({progress:.1f}%)")
                last_bytes = assistant.bytes_received
            
        print(f"完成。接收字节数: {assistant.bytes_received}")
        
        if assistant.bytes_received == len(long_msg):
            Logger.success("完整接收到所有数据。")
        else:
            Logger.warning(f"数据不匹配。丢失了 {len(long_msg) - assistant.bytes_received} 字节。")
    finally:
        assistant.test_mode = False

if __name__ == "__main__":
    assist = SerialAssistant()
    
    # 1. Port Selection utilizing utils
    current_port = select_serial_port("实验一：回环测试 - 请选择串口")
    
    if not current_port:
        Logger.info("未选择串口，程序退出。")
        sys.exit()

    if not assist.open_port(current_port):
        sys.exit()

    try:
        while True:
            print("\n" + "="*30)
            print(f"Experiment 1: 串口回环测试 ({current_port})")
            print("1. 基础收发 (Section 3)")
            print("2. 速率性能测试 (Section 4 - Extension)")
            print("3. 长消息测试 (Section 4 - Extension)")
            print("0. 退出")
            
            choice = input("请选择功能: ")
            
            if choice == '1':
                run_basic_mode(assist)
            elif choice == '2':
                run_rate_test(assist)
            elif choice == '3':
                run_long_message_test(assist)
            elif choice == '0':
                break
            else:
                Logger.warning("无效的选项")
                
    except KeyboardInterrupt:
        print("\n强制退出")
    finally:
        assist.close_port()
