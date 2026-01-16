import sys
import os
import subprocess
import threading
import time
import re
import queue

# Adjust this to match the actual project structure relative to this file
# This file is in Web-Interface/Backend/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
CODE_ROOT = os.path.join(PROJECT_ROOT, 'Code')

MENU_OPTIONS = {
    '1': {
        'name': 'Experiment 1: Loopback Test',
        'script': os.path.join(CODE_ROOT, 'Experiment1', 'main.py'),
        'cwd': os.path.join(CODE_ROOT, 'Experiment1')
    },
    '2c': {
        'name': 'Experiment 2: Client',
        'script': os.path.join(CODE_ROOT, 'Experiment2', 'client.py'),
        'cwd': os.path.join(CODE_ROOT, 'Experiment2')
    },
    '2s': {
        'name': 'Experiment 2: Server',
        'script': os.path.join(CODE_ROOT, 'Experiment2', 'server.py'),
        'cwd': os.path.join(CODE_ROOT, 'Experiment2')
    },
    '3r': {
        'name': 'Experiment 3: Root Node',
        'script': os.path.join(CODE_ROOT, 'Experiment3', 'root.py'),
        'cwd': os.path.join(CODE_ROOT, 'Experiment3')
    },
    '3l': {
        'name': 'Experiment 3: Leaf Node',
        'script': os.path.join(CODE_ROOT, 'Experiment3', 'leaf.py'),
        'cwd': os.path.join(CODE_ROOT, 'Experiment3')
    },
    '4': {
        'name': 'Experiment 4: Router (DV)',
        'script': os.path.join(CODE_ROOT, 'Experiment4', 'router.py'),
        'cwd': os.path.join(CODE_ROOT, 'Experiment4')
    },
    '5': {
        'name': 'Experiment 5: Reliable Router',
        'script': os.path.join(CODE_ROOT, 'Experiment5', 'reliable_router.py'),
        'cwd': os.path.join(CODE_ROOT, 'Experiment5')
    },
    '6': {
        'name': 'Experiment 6: Network App',
        'script': os.path.join(CODE_ROOT, 'Experiment6', 'network_app.py'),
        'cwd': os.path.join(CODE_ROOT, 'Experiment6')
    }
}

class TerminalSession:
    def __init__(self, log_callback, topo_callback):
        self.log_callback = log_callback
        self.topo_callback = topo_callback
        self.process = None
        self.thread = None
        self.running = False
        self.current_buffer = "" # Only for menu
        
        # Initial greeting
        self.show_menu()
    
    def show_menu(self):
        menu = [
            "\r\n\x1b[1;36m=== Network Experiment Launcher ===\x1b[0m",
            "Select an experiment to run:",
            "  [1]  Experiment 1: Loopback Test",
            "  [2c] Experiment 2: Client",
            "  [2s] Experiment 2: Server",
            "  [3r] Experiment 3: Root Node",
            "  [3l] Experiment 3: Leaf Node",
            "  [4]  Experiment 4: Router (DV)",
            "  [5]  Experiment 5: Reliable Router",
            "  [6]  Experiment 6: Network App",
            "",
            "Type the ID (e.g., '4') and press Enter.",
            "> "
        ]
        self.log_callback("\r\n".join(menu))

    def write(self, data):
        """Handle input from WebSocket"""
        
        # Local Echo Logic (Simulate Terminal)
        # Send back exactly what we got for visual feedback, 
        # but convert \r to \r\n for display
        echo_data = data
        if echo_data == '\r':
            echo_data = '\r\n'
        self.log_callback(echo_data)
        
        # If no process is running, we are in menu mode
        if not self.process or self.process.poll() is not None:
            # Accumulate buffer for menu selection
            if data == '\r':
                cmd = self.current_buffer.strip()
                self.current_buffer = "" # Reset
                
                if cmd in MENU_OPTIONS:
                    self.launch(MENU_OPTIONS[cmd])
                else:
                    if cmd:
                        self.log_callback(f"Unknown option: {cmd}\r\n> ")
                    else:
                        self.log_callback("> ")
            elif data == '\x7f': # Backspace
                if len(self.current_buffer) > 0:
                    self.current_buffer = self.current_buffer[:-1]
                    # Visual backspace: Move back, Space, Move back
                    self.log_callback("\b \b") 
            else:
                self.current_buffer += data
                
            return

        # If process is running, write to stdin
        if self.process:
            try:
                # Add newline because most inputs expect it
                # But typical xterm sends \r, need to ensure python gets \n
                input_data = data
                if input_data == '\r': 
                    input_data = '\n'
                
                self.process.stdin.write(input_data.encode('utf-8'))
                self.process.stdin.flush()
            except IOError:
                pass

    def launch(self, option):
        script_path = option['script']
        cwd = option['cwd']
        name = option['name']

        self.log_callback(f"\r\n\x1b[1;32mStarting {name}...\x1b[0m\r\n")
        
        # Use python -u for unbuffered output
        cmd = [sys.executable, '-u', script_path]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr to stdout
                cwd=cwd,
                bufsize=0 # Unbuffered
            )
            
            self.running = True
            self.thread = threading.Thread(target=self._monitor_output, daemon=True)
            self.thread.start()
            
        except Exception as e:
            self.log_callback(f"\r\nFailed to start process: {str(e)}\r\n> ")
            self.show_menu()

    def _monitor_output(self):
        """Read output from process"""
        while self.process and self.process.poll() is None:
            try:
                # Read char by char or line by line?
                # Line by line is safer for parsing, but char by char is better for interactive feel.
                # Since we used unbuffered, we can try to read small chunks.
                chunk = self.process.stdout.read(1)
                if not chunk:
                    break
                
                text = chunk.decode('utf-8', errors='ignore')
                
                # Send to terminal
                self.log_callback(text)
                
                # Buffer for logical parsing (Looking for Tables)
                self.current_buffer += text
                if '\n' in self.current_buffer:
                    lines = self.current_buffer.split('\n')
                    # Process complete lines
                    for line in lines[:-1]:
                        self._analyze_line(line)
                    # Keep incomplete line
                    self.current_buffer = lines[-1]
                    
                    # Also analyze accumulated buffer for multi-line tables if needed
                    # But _analyze_line can trigger a multi-line parser state machine
                    
            except Exception as e:
                break
        
        self.log_callback("\r\n\x1b[1;31mProcess exited.\x1b[0m\r\n")
        self.process = None
        self.show_menu()

    # --- Topology Parser State Machine ---
    _table_buffer = []
    _in_table = False

    def _analyze_line(self, line):
        # We are looking for something like:
        # ------- 当前路由表 (Distance Vector) -------
        # Destination     Cost       Next Hop        Interface
        # ...
        
        clean_line = line.strip()
        
        # Detect Start
        if "路由表" in clean_line or "Routing Table" in clean_line:
            self._in_table = True
            self._table_buffer = []
            return

        # Detect End (Empty line or separator line after content if we want strictness, 
        # but usually the next prompt or ----------- marks end)
        # For simplicity, if we are in table, we collect until we see a separator line at the end, 
        # OR we just parse on every line addition if we match the format.
        
        if self._in_table:
            self._table_buffer.append(clean_line)
            # If we see a separator line that might be the footer?
            # Or if it's the header separator.
            
            # Let's try to parse the buffer if it looks substantial
            if len(self._table_buffer) > 2:
                self._parse_table_buffer(self._table_buffer)
            
            # Reset if we hit an empty line or end separator
            if clean_line.startswith('---') and len(self._table_buffer) > 1:
                # Could be footer
                pass

    def _parse_table_buffer(self, lines):
        # Experiment 4 Format:
        # Destination     Cost       Next Hop        Interface
        # A               0          A               LOCAL
        
        # We need to find the data rows.
        # Ignore headers and separators.
        
        parsed_entries = {}
        my_id = "?"
        
        for l in lines:
            parts = l.split()
            if len(parts) >= 4:
                # Check if it looks like a data row: Dest(Str) Cost(Int) NextHop(Str) Interface(Str)
                dest, cost_str, next_hop, interface = parts[0], parts[1], parts[2], parts[3]
                
                if next_hop.upper() == "NEXT": continue # Header row
                
                try:
                    cost = int(cost_str)
                    parsed_entries[dest] = {
                        'cost': cost,
                        'next_hop': next_hop,
                        'interface': interface
                    }
                    if cost == 0:
                        my_id = dest
                except ValueError:
                    continue

        if parsed_entries and my_id != "?":
            # Send topology update
            topo_data = {
                'id': my_id,
                'table': parsed_entries
            }
            self.topo_callback(topo_data)
