
import sys
import os
import json
import asyncio
import threading
import time
from typing import Callable

# Add the Code directory to sys.path to import Experiment5
# Assuming this file is in Web-Interface/Backend/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
# SWITCHED TO EXPERIMENT 5 FOR COMPATIBILITY WITH ORIGINAL CODE
sys.path.append(os.path.join(PROJECT_ROOT, 'Code', 'Experiment5'))

from reliable_router import ReliableRouterNode

class WebNetworkNode(ReliableRouterNode):
    def __init__(self, log_callback: Callable[[str], None], topo_callback: Callable[[dict], None]):
        # Initialize parent specific variables (seq_num, ack_event, etc.)
        super().__init__()
        self.log_callback = log_callback
        self.topo_callback = topo_callback
        
        # Setup State
        self.setup_phase = 'ID' # ID -> PORTS -> READY
        self.selected_ports = []
        self.configured_event = threading.Event()

    def log(self, *args, **kwargs):
        """Redirects print output to WebSocket"""
        sep = kwargs.get('sep', ' ')
        full_msg = sep.join(map(str, args))
        
        # Send to Web
        if self.log_callback:
            self.log_callback(full_msg)
        
        # Also print to local console
        # Use sys.__stdout__ to avoid recursion if we redirected stdout globally (we haven't yet, but good practice)
        try:
            sys.__stdout__.write(full_msg + '\n')
            sys.__stdout__.flush()
        except:
            pass

    def start(self):
        """Non-blocking start method for Web Interface"""
        self.log("="*40)
        self.log("Web Bridge for Experiment 5 (Reliable Transport)")
        self.log("="*40)
        
        # Step 1: Detect Ports
        import serial.tools.list_ports
        self.available_ports = [p.device for p in serial.tools.list_ports.comports()]
        
        if not self.available_ports:
            self.log("Warning: No Serial Ports Detected!")
            self.log("You can strictly test logic, but no network IO will happen.")
        else:
            self.log(f"Detected Ports: {self.available_ports}")

        # Step 2: Waiting for ID
        self.log("\n[SETUP REQUIRED]")
        self.log("Please enter this Node's ID (e.g., A, B, WEB):")
        self.log("(Type in the command bar below)")
        
        self.setup_phase = 'ID'
        
        # Wait for configuration to complete
        self.configured_event.wait()
        
        # Step 3: Start Node Logic (Copied/Adapted from reliable_router.py start logic)
        self.log(f"Initializing Node {self.my_id} on ports {self.selected_ports}...")
        
        self.routing_table[self.my_id] = {'cost': 0, 'next_hop_port': 'LOCAL', 'next_hop_id': self.my_id}
        self.running = True

        for p in self.selected_ports:
            try:
                # We need to use the parent's logic or reimplement listener
                # Parent logic:
                # ser = serial.Serial(p, 9600, timeout=0.1)
                # self.active_ports[p] = ser ...
                # But parent start() does this inside itself.
                # Since we overrode start(), we must do it manually.
                
                ser = serial.Serial(p, 9600, timeout=0.1)
                self.active_ports[p] = ser
                self.port_locks[p] = threading.Lock()
                threading.Thread(target=self._listen_port, args=(p,), daemon=True).start()
                self.log(f"[{p}] Port Opened & Listening.")
            except Exception as e:
                self.log(f"[{p}] Failed to open: {e}")

        # Start background tasks
        threading.Thread(target=self._task_hello, daemon=True).start()
        threading.Thread(target=self._task_broadcast_dv, daemon=True).start()
        threading.Thread(target=self._task_check_timeout, daemon=True).start()

        self.log("\n>>> System Ready. Waiting for commands...")

    def execute_command(self, cmd_str):
        """Handle inputs from the Web Console"""
        cmd_str = cmd_str.strip()
        if not cmd_str: return
        
        # ==> SETUP PHASE: ID
        if self.setup_phase == 'ID':
            self.my_id = cmd_str
            self.log(f"ID Set to: {self.my_id}")
            self.log("\n[SETUP REQUIRED]")
            self.log(f"Available Ports: {self.available_ports}")
            self.log("Enter ports to use (e.g., 'COM3 COM4' or 'all'):")
            self.setup_phase = 'PORTS'
            return

        # ==> SETUP PHASE: PORTS
        elif self.setup_phase == 'PORTS':
            selection = cmd_str.lower()
            target_ports = []
            if selection == 'all':
                target_ports = self.available_ports
            else:
                parts = [p.strip() for p in selection.replace(',', ' ').split()]
                # Fuzzy match COM ports
                for p in parts:
                    # If user typed '3', make it 'COM3' (Windows specific helper)
                    if p.isdigit() and sys.platform.startswith('win'):
                        p_fixed = f"COM{p}"
                    else:
                        p_fixed = p
                        
                    if any(ap.upper() == p_fixed.upper() for ap in self.available_ports):
                         # find exact case
                         real_port = next(ap for ap in self.available_ports if ap.upper() == p_fixed.upper())
                         target_ports.append(real_port)
                    else:
                        self.log(f"Warning: Port {p} not found in available list.")
            
            if not target_ports and self.available_ports:
                self.log("No valid ports selected. Try again (or type 'all').")
                return
            
            self.selected_ports = target_ports
            self.log(f"Selected Ports: {self.selected_ports}")
            self.setup_phase = 'READY'
            self.configured_event.set() # Unblock start()
            return

        # ==> NORMAL PHASE
        cmd = cmd_str.split()
        op = cmd[0].lower()
        
        self.log(f"> {cmd_str}")
        
        if op == 'send': 
            if len(cmd)<3: self.log("Usage: send <ID> <Msg>")
            else:
                msg = ' '.join(cmd[2:])
                target = cmd[1]
                threading.Thread(target=self._initiate_reliable_send, args=(target, msg)).start()
                
        elif op == 'table':
            # Pretty print routing table
            lines = ["Routing Table:"]
            lines.append(f"{'Dest':<10} {'Cost':<6} {'NextHop':<10} {'Interface':<10}")
            lines.append("-" * 40)
            for dest, info in self.routing_table.items():
                lines.append(f"{dest:<10} {info['cost']:<6} {info['next_hop_id']:<10} {info['next_hop_port']:<10}")
            self.log("\n".join(lines))
            
        elif op == 'corrupt':
            if len(cmd) > 1 and cmd[1] == 'on':
                self.simulate_error = True
                self.log("Success: Next packet will have corrupt checksum.")
            else:
                self.simulate_error = False
                self.log("Corrupt mode OFF.")
                
        elif op == 'ping' or op == 'tracert':
             self.log("Error: 'ping'/'tracert' are Exp6 features. Current mode is Exp5 (Reliable).")
             self.log("Use 'send <ID> <Msg>' instead.")
        elif op == 'help':
            self.log("Commands: send <ID> <Msg> | table | corrupt on/off")
        else:
            self.log(f"Unknown command: {op}")

# We need to redirect stdout to capture inherited methods' prints
import sys
import io

class StdoutRedirector:
    def __init__(self, callback):
        self.callback = callback
        self.old_stdout = sys.stdout

    def write(self, text):
        # Filter out newlines to avoid double spacing if log adds one
        if text.strip():
            self.callback(text.strip())
        self.old_stdout.write(text)

    def flush(self):
        self.old_stdout.flush()


