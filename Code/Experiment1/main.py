import serial
import serial.tools.list_ports
import threading
import time
import sys

class SerialAssistant:
    def __init__(self):
        self.ser = None                 # 用来存储串口对象的变量 即 serial.Serial 的实例
                                        # 初始状态下没有打开任何串口 `open_port` 之后会赋值为相应的串口对象
        self.receiving = False          # 控制接收线程的标志位 False 表示不允许接收数据 (用于退出) ; True 表示允许接收数据
        self.recv_thread = None         # 用来存放线程对象 在结束时候可以调用 join 方法等待线程安全结束   
        self.lock = threading.Lock()
        
        # Statistics for rate testing
        self.bytes_received = 0
        self.test_mode = False          # If True, suppress print and just count

    def get_available_ports(self):
        """List available COM ports"""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def open_port(self, port_name, baudrate=9600, timeout=1):
        """Open serial port with default parameters as per Experiment 1 Req 3"""
        try:
            self.ser = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE,      # parity 奇偶性 , 这里指校验位 , None 表示不使用校验位
                timeout=timeout
            )
            print(f"[System] Serial port {port_name} opened successfully.")
            print(f"         Baud: {baudrate}, Data: 8, Stop: 1, Parity: None")
            
            # Start receive thread automatically
            self.receiving = True
            # 创建线程执行 _receive_worker 方法 , 并设置为守护线程 主线程退出时自动杀死当前线程
            self.recv_thread = threading.Thread(target=self._receive_worker, daemon=True)
            self.recv_thread.start()
            return True
        except serial.SerialException as e:
            print(f"[Error] Failed to open port: {e}")
            return False

    def close_port(self):
        """Close serial port"""
        self.receiving = False                  # 设置false会使接收线程退出循环 从而停止
        if self.recv_thread and self.recv_thread.is_alive():
            self.recv_thread.join(timeout=1)    # 等待接收线程安全退出 最多等 1 秒
        
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[System] Serial port closed.")

    def send_data(self, data):
        """Send data properly encoded"""
        if not self.ser or not self.ser.is_open:
            print("[Error] Port not open.")
            return False

        try:
            if isinstance(data, str):
                '''
                测试data是不是字节流
                    1. 如果是来自用户输入 那就是字符串 需要编码为字节流才能发送
                    2. 如果是来自程序内部的速率测试数据 那就是字节流 直接发送即可
                '''
                data = data.encode('utf-8')
            
            self.ser.write(data)
            # Experiment 1 Req 3: Specific feedback on send success
            if not self.test_mode:
                print(f"[Sent] {len(data)} bytes sent successfully.")
            return True
        except Exception as e:
            print(f"[Error] Send failed: {e}")
            return False

    def _receive_worker(self):
        """
        Background thread for receiving data.
        Experiment 1 Req 4: Real-time detection (using in_waiting).
        """
        while self.receiving and self.ser and self.ser.is_open:
            try:
                # Check buffer size
                if self.ser.in_waiting > 0:         # 判断缓冲区里面有没有数据 有的话再读取
                    # Read all available
                    data = self.ser.read(self.ser.in_waiting)
                    # print(f"\n[DEBUG] Received {len(data)} bytes from buffer")
                    self.bytes_received += len(data)
                    
                    if not self.test_mode:
                        try:
                            decoded = data.decode('utf-8')
                            # print(f"\n[Received] {decoded}")
                            sys.stdout.flush()
                        except UnicodeDecodeError:
                            # print(f"\n[Received Raw] {data}")
                            sys.stdout.flush()
                            
                time.sleep(0.01) # Small sleep to reduce CPU usage
            except Exception as e:
                if self.receiving:
                    print(f"[Error] Receive error: {e}")
                break

def run_basic_mode(assistant):
    print("\n--- Basic Chat Mode (Type 'exit' to quit) ---")
    print("Enter text to send loopback:")

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
        print("\n--- Max Send Rate Test ---")
        print("Sending continuous data stream for 5 seconds...")
        
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
        print("\nSending complete. Calculating results...")
        
        # Since it's loopback, we check receiving speed too
        # Wait a moment for buffer to clear
        time.sleep(1) 
        
        print("-" * 30)
        print(f"Duration: {duration:.2f} s")
        print(f"Total Sent: {sent_bytes} bytes")
        print(f"Total Received: {assistant.bytes_received} bytes")
        print(f"Speed: {sent_bytes / duration / 1024:.2f} KB/s")
        print("Note: If 'Received' < 'Sent', data loss occurred due to buffer overflow.")
    finally:
        assistant.test_mode = False

def run_long_message_test(assistant):
    """Experiment 1 Req 4: Long message test"""
    try:
        print("\n--- Long Message (Fragmentation) Test ---")
        length = 10000 # 10KB message
        print(f"Generating {length} bytes of text data...")
        
        # Create a long identifiable string
        long_msg = "START" + "1234567890" * (length // 10) + "END"
        
        assistant.test_mode = True # Use clean output mode
        assistant.bytes_received = 0
        
        print("Sending...")
        start_time = time.time()
        assistant.send_data(long_msg)
        
        print("Waiting for reception to complete...")
        # Wait until we receive approximately the right amount or timeout
        timeout = 10 
        last_bytes = 0
        while assistant.bytes_received < len(long_msg) and timeout > 0:
            # 由于自收发很快 通常不需要等待10s 这里设置一个较短的轮询间隔
            # 10 秒超时实际上是一个安全保险，针对网络延迟或其他异常情况。
            time.sleep(0.5)
            timeout -= 0.5
            # 只在有新数据时打印
            if assistant.bytes_received > last_bytes:
                progress = (assistant.bytes_received / len(long_msg)) * 100
                print(f"  Progress: {assistant.bytes_received}/{len(long_msg)} ({progress:.1f}%)")
                last_bytes = assistant.bytes_received
            
        print(f"Done. Bytes Received: {assistant.bytes_received}")
        
        if assistant.bytes_received == len(long_msg):
            print("[Success] Full message received intact.")
        else:
            print(f"[Warning] Data mismatch. Lost {len(long_msg) - assistant.bytes_received} bytes.")
    finally:
        assistant.test_mode = False

if __name__ == "__main__":
    assist = SerialAssistant()
    
    # 1. Port Selection
    avail_ports = assist.get_available_ports()
    if not avail_ports:
        # Fallback if no ports found (for testing without hardware)
        print("No COM ports found. Please connect your USB-Serial adapter.")
        manual_port = input("Enter port name manually (e.g. COM3): ")
        if not manual_port: sys.exit()
        current_port = manual_port
    else:
        print("Available Ports:", avail_ports)
        current_port = input(f"Select Port [Default {avail_ports[0]}]: ") or avail_ports[0]

    if not assist.open_port(current_port):
        sys.exit()

    try:
        while True:
            print("\n" + "="*30)
            print(f"Experiment 1: Loopback Test ({current_port})")
            print("1. Basic Send/Receive (Section 3)")
            print("2. Rate Performance Test (Section 4 - Extension)")
            print("3. Long Message Test (Section 4 - Extension)")
            print("0. Exit")
            
            choice = input("Select option: ")
            
            if choice == '1':
                run_basic_mode(assist)
            elif choice == '2':
                run_rate_test(assist)
            elif choice == '3':
                run_long_message_test(assist)
            elif choice == '0':
                break
            else:
                print("Invalid option")
                
    except KeyboardInterrupt:
        print("\nForce Exit")
    finally:
        assist.close_port()
