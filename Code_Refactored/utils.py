import serial
import serial.tools.list_ports
import sys
import time

class Logger:
    """
    简单的日志工具，用于统一输出格式
    """
    @staticmethod
    def info(msg):
        print(f"[INFO] {msg}")

    @staticmethod
    def error(msg):
        print(f"[ERROR] {msg}")

    @staticmethod
    def debug(msg):
        # 可以在这里控制是否显示调试信息
        print(f"[DEBUG] {msg}")

    @staticmethod
    def success(msg):
        print(f"[SUCCESS] {msg}")

    @staticmethod
    def warning(msg):
        print(f"[WARNING] {msg}")


def get_available_ports():
    """
    获取当前可用的串口列表
    :return: list of serial.tools.list_ports.ListPortInfo
    """
    return serial.tools.list_ports.comports()


def select_serial_port(prompt="请选择串口", allow_refresh=True):
    """
    让用户通过数字选择一个串口
    :param prompt: 提示信息
    :param allow_refresh: 是否允许刷新列表
    :return: 选中的串口名称 (str) 或 None (如果取消)
    """
    while True:
        ports = get_available_ports()
        if not ports:
            Logger.warning("未检测到可用的串口设备。")
            if not allow_refresh:
                return None
            choice = input("按 Enter 刷新，输入 'q' 退出: ").strip().lower()
            if choice == 'q':
                return None
            continue

        print(f"\n--- {prompt} ---")
        for idx, port in enumerate(ports):
            print(f"[{idx + 1}] {port.device} ({port.description})")
        
        if allow_refresh:
            print("[r] 刷新列表")
        print("[q] 退出")

        choice = input("请输入序号选择: ").strip().lower()

        if choice == 'q':
            return None
        if choice == 'r' and allow_refresh:
            continue

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(ports):
                selected_port = ports[idx].device
                Logger.info(f"已选择端口: {selected_port}")
                return selected_port
            else:
                Logger.error("无效的序号，请重新输入。")
        else:
            Logger.error("请输入有效的数字序号。")


def select_multiple_ports(prompt="请选择串口 (多选)", allow_refresh=True):
    """
    让用户选择多个串口 (使用逗号分隔，如 1,2)
    :param prompt: 提示信息
    :param allow_refresh: 是否允许刷新
    :return: 选中的串口名称列表 (list of str)
    """
    while True:
        ports = get_available_ports()
        if not ports:
            Logger.warning("未检测到可用的串口设备。")
            if not allow_refresh:
                return []
            choice = input("按 Enter 刷新，输入 'q' 退出: ").strip().lower()
            if choice == 'q':
                return []
            continue

        print(f"\n--- {prompt} ---")
        for idx, port in enumerate(ports):
            print(f"[{idx + 1}] {port.device} ({port.description})")
        
        print(f"[a] 全选 (All)")
        if allow_refresh:
            print("[r] 刷新列表")
        print("[q] 退出")
        print("提示: 输入多个序号用逗号或空格分隔 (例如: 1,2)")

        choice = input("请输入: ").strip().lower()

        if choice == 'q':
            return []
        if choice == 'r' and allow_refresh:
            continue
        if choice == 'a':
            selected_ports = [p.device for p in ports]
            Logger.info(f"已选择所有端口: {selected_ports}")
            return selected_ports

        # 处理多选输入
        try:
            # 替换中文逗号，分割并去除空白
            parts = choice.replace('，', ',').replace(' ', ',').split(',')
            selected_indices = []
            for part in parts:
                if not part: continue
                idx = int(part) - 1
                if 0 <= idx < len(ports):
                    selected_indices.append(idx)
                else:
                    Logger.warning(f"序号 {part} 无效，已忽略")
            
            if not selected_indices:
                Logger.warning("未选择任何有效端口，请重试")
                continue
            
            # 去重并获取端口名
            selected_ports = [ports[i].device for i in sorted(set(selected_indices))]
            Logger.info(f"已选择端口: {selected_ports}")
            return selected_ports
            
        except ValueError:
            Logger.error("输入格式错误，请输入数字序号。")


def create_serial_connection(port_name, baudrate=9600, timeout=1, 
                             bytesize=serial.EIGHTBITS, 
                             stopbits=serial.STOPBITS_ONE, 
                             parity=serial.PARITY_NONE):
    """
    创建并打开串口连接的工厂函数
    """
    try:
        ser = serial.Serial(
            port=port_name,
            baudrate=baudrate,
            bytesize=bytesize,
            stopbits=stopbits,
            parity=parity,
            timeout=timeout
        )
        # Logger.success(f"串口 {port_name} 打开成功 (Baud: {baudrate})")
        return ser
    except serial.SerialException as e:
        Logger.error(f"无法打开串口 {port_name}: {e}")
        return None

def choose_serial_format():
    """交互选择串口格式，返回 (bytesize, stopbits, parity, label)"""
    data_map = {'7': serial.SEVENBITS, '8': serial.EIGHTBITS}
    stop_map = {'1': serial.STOPBITS_ONE, '2': serial.STOPBITS_TWO}
    parity_map = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}

    def ask(prompt, mapping, default_key):
        while True:
            val = input(prompt).strip().upper()
            if not val:
                val = default_key
            if val in mapping:
                return mapping[val], val
            print("[错误] 输入无效，请重试")

    data_bits, data_key = ask("请选择数据位 (7/8，默认8): ", data_map, '8')
    stop_bits, stop_key = ask("请选择停止位 (1/2，默认1): ", stop_map, '1')
    parity_val, parity_key = ask("请选择校验位 (N/E/O，默认N): ", parity_map, 'N')
    label = f"{data_key}{parity_key}{stop_key}"
    return data_bits, stop_bits, parity_val, label
