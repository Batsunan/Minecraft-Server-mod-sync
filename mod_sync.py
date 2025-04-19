import os
import datetime
import traceback
import paramiko
import threading
import customtkinter as ctk
from PIL import Image
from pathlib import Path
import glob
import time
from PIL import ImageTk

# === CONFIG ===

SFTP_HOST = None  # Will be set by user
SFTP_PORT = None  # Will be set by user
SFTP_USERNAME = None  # Will be set by user
SFTP_PASSWORD = None  # Will be set by user
REMOTE_MODS_PATH = '/mods'
LOCAL_MODS_PATH = os.path.join(os.getenv('APPDATA'), ".minecraft", "mods")
ASSET_PATH = Path(__file__).parent / "assets"
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)  # Create logs directory if it doesn't exist
LOG_PATH = LOG_DIR / "Latest.txt"

# === DEBUG LOGGING ===
def get_log_filename():
    """Generate a timestamped log filename"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return LOG_DIR / f"session_{timestamp}.txt"

def debug(msg):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {msg}"
    print(line)
    log_path = get_log_filename()
    with open(log_path, "a") as f:
        f.write(line + "\n")
    manage_logs()

def manage_logs():
    """Keep only the 20 most recent log files"""
    log_files = sorted(LOG_DIR.glob("session_*.txt"), key=os.path.getmtime)
    if len(log_files) > 20:
        for old_log in log_files[:-20]:
            old_log.unlink()

# === SFTP UTILS ===
def get_sftp():
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USERNAME, password=SFTP_PASSWORD)
    return paramiko.SFTPClient.from_transport(transport)

# === MAIN APPLICATION ===
class MinecraftSyncApp:
    def __init__(self, master):
        self.master = master
        # Show loading screen first
        self.loading_screen = ctk.CTkFrame(master)
        self.loading_screen.pack(fill='both', expand=True)
        
        loading_label = ctk.CTkLabel(
            self.loading_screen, 
            text="Loading Minecraft Sync...", 
            font=("Arial", 16)
        )
        loading_label.pack(pady=20)
        
        # Progress bar for loading
        self.loading_progress = ctk.CTkProgressBar(self.loading_screen)
        self.loading_progress.pack(pady=10, padx=20, fill='x')
        self.loading_progress.set(0)
        
        # Loading status text
        self.loading_status = ctk.CTkLabel(self.loading_screen, text="Initializing...")
        self.loading_status.pack(pady=5)
        
        # Start loading in background
        threading.Thread(target=self.initialize_app, daemon=True).start()
        
    def initialize_app(self):
        # Simulate loading steps
        steps = [
            ("Connecting to server...", 0.2),
            ("Loading mod list...", 0.4),
            ("Checking local files...", 0.6),
            ("Preparing interface...", 0.8),
            ("Ready!", 1.0)
        ]
        
        for text, progress in steps:
            time.sleep(0.5)  # Simulate work being done
            self.master.after(0, self.update_loading, text, progress)
            
        time.sleep(0.5)
        self.master.after(0, self.setup_gui)
        
    def update_loading(self, text, progress):
        self.loading_status.configure(text=text)
        self.loading_progress.set(progress)
        self.sync_mods()
    def setup_gui(self):
        # Remove loading screen
        
        self.loading_screen.pack_forget()
        self.loading_screen.destroy()
        
        self.master.title(f"Mine Server Sync - Connected to {SFTP_HOST}:{SFTP_PORT}")
        self.master.geometry("800x600")
        
        # === Top Bar with Connection Info and Logout Button ===
        top_bar = ctk.CTkFrame(self.master)
        top_bar.pack(fill='x', padx=10, pady=5)
        
        # Connection info label
        conn_info = ctk.CTkLabel(top_bar, text=f"Connected to: {SFTP_HOST}:{SFTP_PORT} \nBuild Version: 1.0.0",
                                 text_color="aqua", font=("Yippes", 12, "bold"))
                                 
        conn_info.pack(side='left', padx=5)
    

    
        
        # Logout button
        logout_btn = ctk.CTkButton(top_bar, text="Logout", width=80, 
                                  command=self.logout, fg_color="transparent",
                                  border_width=1, text_color=("gray10", "#DCE4EE"))
        logout_btn.pack(side='right', padx=5)
        
        # === Tabs ===
        self.tabs = ctk.CTkTabview(self.master)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tabs.add("Comparison")
        self.tabs.add("Exceed Mods")
        self.tabs.add("Latest Mods")
        self.tabs.add("Useful Mods")

        self.compare_table = ctk.CTkScrollableFrame(self.tabs.tab("Comparison"))
        self.compare_table.pack(fill="both", expand=True)
        self.selected_mods = []

        self.exceed_list = ctk.CTkScrollableFrame(self.tabs.tab("Exceed Mods"))
        self.exceed_list.pack(fill="both", expand=True)

        self.latest_list = ctk.CTkScrollableFrame(self.tabs.tab("Latest Mods"))
        self.latest_list.pack(fill="both", expand=True)
        self.latest_mods = []
        self.latest_selected = []

        self.useful_mods_frame = ctk.CTkScrollableFrame(self.tabs.tab("Useful Mods"))
        self.useful_mods_frame.pack(fill="both", expand=True)

        # === Icons ===
        self.check_icon = ctk.CTkImage(dark_image=Image.open(ASSET_PATH / "check.png"), size=(20, 20))
        self.cross_icon = ctk.CTkImage(dark_image=Image.open(ASSET_PATH / "cross.png"), size=(20, 20))
        self.sync_icon = ctk.CTkImage(dark_image=Image.open(ASSET_PATH / "sync.png"), size=(20, 20))
        self.latest_icon = ctk.CTkImage(dark_image=Image.open(ASSET_PATH / "latest.png"), size=(20, 20))
        self.download_all_icon = ctk.CTkImage(dark_image=Image.open(ASSET_PATH / "download_all.png"), size=(20, 20))
        self.delete_all_icon = ctk.CTkImage(dark_image=Image.open(ASSET_PATH / "delete_all.png"), size=(20, 20))

        # === Progress Bar ===
        self.progress_bar = ctk.CTkProgressBar(self.master)
        self.progress_bar.pack(fill='x', padx=10, pady=(0, 5))

        self.progress_label = ctk.CTkLabel(self.master, text="")
        self.progress_label.pack()

        # === Buttons ===
        self.btn_frame = ctk.CTkFrame(self.master)
        self.btn_frame.pack(fill='x', pady=5, padx=10)

        ctk.CTkButton(self.btn_frame, text="Sync Mods", image=self.sync_icon, compound='left', 
                      command=lambda: [self.sync_mods(), self.populate_exceed(), self.populate_latest()]).pack(side='left', padx=5)
        ctk.CTkButton(self.btn_frame, text="Download Selected", image=self.check_icon, compound='left', 
                      command=self.download_selected).pack(side='left', padx=5)
        ctk.CTkButton(self.btn_frame, text="Download Latest", image=self.latest_icon, compound='left', 
                      command=self.download_latest).pack(side='left', padx=5)
        ctk.CTkButton(self.btn_frame, text="Download All", image=self.download_all_icon, compound='left', 
                      command=self.download_all).pack(side='left', padx=5)
        ctk.CTkButton(self.btn_frame, text="Delete All", image=self.delete_all_icon, compound='left', 
                      command=self.delete_all).pack(side='left', padx=5)

        # Initialize UI
        self.add_useful_mod_buttons()
        self.create_select_all_checkbox(self.tabs.tab("Comparison"), self.selected_mods, self.compare_table)
        self.create_select_all_checkbox(self.tabs.tab("Latest Mods"), self.latest_selected, self.latest_list)
        self.sync_mods()
        self.populate_exceed()
        self.populate_latest()

    def logout(self):
        # Clear all connection details
        global SFTP_HOST, SFTP_PORT, SFTP_USERNAME, SFTP_PASSWORD
        SFTP_HOST = None
        SFTP_PORT = None
        SFTP_USERNAME = None
        SFTP_PASSWORD = None
        
        # Close current window
        self.master.destroy()
        
        # Open new login window
        login_root = ctk.CTk()
        login_app = LoginWindow(login_root)
        login_root.mainloop()

    def list_remote_mods(self):
        try:
            with get_sftp() as sftp:
                files = [f for f in sftp.listdir(REMOTE_MODS_PATH) if f.endswith(".jar")]
                debug(f"Listed {len(files)} remote mods")
                return sorted(files)
        except Exception as e:
            debug(f"[ERROR] list_remote_mods: {traceback.format_exc()}")
            return []

    def list_local_mods(self):
        try:
            if not os.path.exists(LOCAL_MODS_PATH):
                return []
            files = [f for f in os.listdir(LOCAL_MODS_PATH) if f.endswith(".jar")]
            debug(f"Listed {len(files)} local mods")
            return sorted(files)
        except Exception as e:
            debug(f"[ERROR] list_local_mods: {traceback.format_exc()}")
            return []

    def get_remote_mod_timestamps(self):
        try:
            with get_sftp() as sftp:
                mods = [(file.filename, file.st_mtime) for file in sftp.listdir_attr(REMOTE_MODS_PATH) if file.filename.endswith(".jar")]
                debug(f"Found {len(mods)} remote mod timestamps")
                return sorted(mods, key=lambda x: x[1], reverse=True)
        except Exception as e:
            debug(f"[ERROR] get_remote_mod_timestamps: {traceback.format_exc()}")
            return []

    def download_mod(self, mod_name):
        try:
            with get_sftp() as sftp:
                remote_path = f"{REMOTE_MODS_PATH}/{mod_name}"
                local_path = os.path.join(LOCAL_MODS_PATH, mod_name)
                sftp.get(remote_path, local_path)
                debug(f"Downloaded: {mod_name}")
                return True
        except Exception as e:
            debug(f"[ERROR] download_mod {mod_name}: {traceback.format_exc()}")
            return False

    def threaded_download_all(self):
        mods = self.list_remote_mods()
        total = len(mods)
        if total == 0:
            return

        for i, mod in enumerate(mods, start=1):
            self.download_mod(mod)
            percent = i / total
            self.master.after(0, lambda p=percent, i=i: self.update_progress(p, i, total))

        self.master.after(0, lambda: [self.sync_mods(), self.finish_progress("Finished Downloading")])

    def threaded_download_latest(self):
        total = len(self.latest_mods)
        if total == 0:
            return

        for i, (mod, _) in enumerate(self.latest_mods, start=1):
            self.download_mod(mod)
            percent = i / total
            self.master.after(0, lambda p=percent, i=i: self.update_progress(p, i, total))

        self.master.after(0, lambda: [self.sync_mods(), self.finish_progress("Finished Downloading")])

    def update_progress(self, percent, current, total):
        self.progress_bar.set(percent)
        self.progress_bar.configure(progress_color="#1f6aa5")
        self.progress_label.configure(text=f"{current}/{total} Files downloaded")
        self.master.update_idletasks()

    def finish_progress(self, msg):
        self.progress_bar.set(1)
        self.progress_bar.configure(progress_color="green")
        self.progress_label.configure(text=msg)

    def download_all(self):
        threading.Thread(target=self.threaded_download_all, daemon=True).start()

    def download_latest(self):
        threading.Thread(target=self.threaded_download_latest, daemon=True).start()

    def delete_all(self):
        try:
            for file in os.listdir(LOCAL_MODS_PATH):
                if file.endswith(".jar"):
                    os.remove(os.path.join(LOCAL_MODS_PATH, file))
                    debug(f"Deleted local mod: {file}")
            self.sync_mods()
        except Exception as e:
            debug(f"[ERROR] delete_all: {traceback.format_exc()}")

    def add_useful_mod_buttons(self):
        label = ctk.CTkLabel(self.useful_mods_frame, text="Recommended Mod Categories:", font=("Arial", 16, "bold"))
        label.pack(pady=10)

        fps_button = ctk.CTkButton(self.useful_mods_frame, text="COMING SOON")
        fps_button.pack(pady=5)

        quality_button = ctk.CTkButton(self.useful_mods_frame, text="#PAREL BOOMER")
        quality_button.pack(pady=5)

    def toggle_all_select(self, target_list, container):
        all_frames = container.winfo_children()
        if len(target_list) < len(all_frames):
            for frame in all_frames:
                if hasattr(frame, 'mod_name') and frame.mod_name not in target_list:
                    self.on_row_click(frame.mod_name, frame, target_list)
        else:
            for frame in all_frames:
                if hasattr(frame, 'mod_name') and frame.mod_name in target_list:
                    self.on_row_click(frame.mod_name, frame, target_list)

    def create_select_all_checkbox(self, parent, target_list, container):
        checkbox = ctk.CTkCheckBox(parent, text="Select All", command=lambda: self.toggle_all_select(target_list, container))
        checkbox.pack(anchor="w", padx=10, pady=5)

    def on_row_click(self, mod, frame, target):
        if mod in target:
            target.remove(mod)
            frame.configure(fg_color="transparent")
        else:
            target.append(mod)
            frame.configure(fg_color="#2a2a2a")

    def sync_mods(self):
        for widget in self.compare_table.winfo_children():
            widget.destroy()
        self.selected_mods.clear()

        remote_mods = self.list_remote_mods()
        local_mods = self.list_local_mods()

        for mod in remote_mods:
            frame = ctk.CTkFrame(self.compare_table)
            frame.pack(fill='x', pady=1, padx=5)
            frame.mod_name = mod
            exists = mod in local_mods
            icon = self.check_icon if exists else self.cross_icon

            name_label = ctk.CTkLabel(frame, text=mod)
            name_label.pack(side='left', padx=10)

            icon_label = ctk.CTkLabel(frame, image=icon, text='')
            icon_label.pack(side='right', padx=10)

            for widget in [frame, name_label, icon_label]:
                widget.bind("<Button-1>", lambda e, m=mod, f=frame: self.on_row_click(m, f, self.selected_mods))

    def populate_exceed(self):
        for widget in self.exceed_list.winfo_children():
            widget.destroy()

        remote = set(self.list_remote_mods())
        local = set(self.list_local_mods())
        only_client = sorted(local - remote)
        for mod in only_client:
            label = ctk.CTkLabel(self.exceed_list, text=mod)
            label.pack(anchor='w', padx=10, pady=2)

    def populate_latest(self):
        for widget in self.latest_list.winfo_children():
            widget.destroy()

        self.latest_mods = self.get_remote_mod_timestamps()[:10]
        self.latest_selected.clear()

        for mod, ts in self.latest_mods:
            dt = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')

            frame = ctk.CTkFrame(self.latest_list)
            frame.pack(fill='x', padx=5, pady=2)
            frame.mod_name = mod

            label = ctk.CTkLabel(frame, text=f"{mod}", anchor='w')
            label.pack(side='left', padx=10, fill='x', expand=True)

            date_label = ctk.CTkLabel(frame, text=dt, anchor='e', width=120)
            date_label.pack(side='right', padx=10)

            for widget in [frame, label, date_label]:
                widget.bind("<Button-1>", lambda e, m=mod, f=frame: self.on_row_click(m, f, self.latest_selected))

    def threaded_download_selected(self):
        total = len(self.selected_mods)
        if total == 0:
            return

        for i, mod in enumerate(self.selected_mods, start=1):
            self.download_mod(mod)
            percent = i / total
            self.master.after(0, lambda p=percent, i=i: self.update_progress(p, i, total))

        self.master.after(0, lambda: [self.sync_mods(), self.finish_progress("Finished Downloading")])

    def download_selected(self):
        threading.Thread(target=self.threaded_download_selected, daemon=True).start()

# === LOGIN WINDOW ===
class LoginWindow:
    def __init__(self, master):
        self.master = master
        self.master.title("Mine Server Sync - Login")
        self.master.geometry("400x350")  # Increased height for additional fields
        
        # Center the window
        window_width = self.master.winfo_reqwidth()
        window_height = self.master.winfo_reqheight()
        position_right = int(self.master.winfo_screenwidth()/2 - window_width/2)
        position_down = int(self.master.winfo_screenheight()/2 - window_height/2)
        self.master.geometry(f"+{position_right}+{position_down}")
        
        self.setup_login_ui()
        
    def setup_login_ui(self):
        frame = ctk.CTkFrame(self.master)
        frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        label = ctk.CTkLabel(frame, text="Enter SFTP Connection Details", font=("Arial", 16))
        label.pack(pady=12, padx=10)
        
        # Host entry
        self.host_entry = ctk.CTkEntry(frame, placeholder_text="SFTP Host")
        self.host_entry.pack(pady=6, padx=10)
        self.host_entry.insert(0, 'sg03.wisehosting.com')  # Default value
        
        # Port entry
        self.port_entry = ctk.CTkEntry(frame, placeholder_text="SFTP Port")
        self.port_entry.pack(pady=6, padx=10)
        self.port_entry.insert(0, "2022")  # Default value
        
        # Username entry
        self.user_entry = ctk.CTkEntry(frame, placeholder_text="Username")
        self.user_entry.pack(pady=6, padx=10)
        
        # Password entry
        self.pass_entry = ctk.CTkEntry(frame, placeholder_text="Password", show="*")
        self.pass_entry.pack(pady=6, padx=10)
        
        # Login button
        login_btn = ctk.CTkButton(frame, text="Connect", command=self.on_login)
        login_btn.pack(pady=12, padx=10)
        
        # Add loading indicator (initially hidden)
        self.loading_indicator = ctk.CTkLabel(frame, text="", width=20, height=20)
        self.loading_indicator.pack(pady=5)
        
        # Error label
        self.error_label = ctk.CTkLabel(frame, text="", text_color="red")
        self.error_label.pack(pady=5)
        
    def show_loading(self, show=True):
        if show:
            self.loading_indicator.configure(text="Connecting...")
            self.master.update()
            # Simple animation dots
            for i in range(1, 4):
                self.loading_indicator.configure(text=f"Connecting{'.' * i}")
                self.master.update()
                time.sleep(0.3)
        else:
            self.loading_indicator.configure(text="")
            
    def on_login(self):
        global SFTP_HOST, SFTP_PORT, SFTP_USERNAME, SFTP_PASSWORD
        
        # Clear previous errors
        self.error_label.configure(text="")
        
        # Get host and validate
        SFTP_HOST = self.host_entry.get().strip()
        if not SFTP_HOST:
            self.error_label.configure(text="Host is required")
            return
            
        # Get port and validate
        port_str = self.port_entry.get().strip()
        if not port_str:
            self.error_label.configure(text="Port is required")
            return
            
        try:
            SFTP_PORT = int(port_str)
            if not (0 < SFTP_PORT <= 65535):
                raise ValueError("Port out of range")
        except ValueError:
            self.error_label.configure(text="Port must be a number (1-65535)")
            return
            
        # Get credentials
        SFTP_USERNAME = self.user_entry.get().strip()
        SFTP_PASSWORD = self.pass_entry.get()
        
        if not SFTP_USERNAME or not SFTP_PASSWORD:
            self.error_label.configure(text="Username and password are required")
            return
        
        # Disable login button during connection attempt
        for widget in self.master.winfo_children():
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "Connect":
                widget.configure(state="disabled")
        
        # Show loading animation
        self.show_loading(True)
        
        # Test connection in a separate thread to keep UI responsive
        threading.Thread(target=self.test_connection, daemon=True).start()
        
    def test_connection(self):
        try:
            with get_sftp() as sftp:
                # Connection successful
                self.master.after(0, self.on_connection_success)
        except Exception as e:
            self.master.after(0, self.on_connection_failed, str(e))
            
    def on_connection_success(self):
        self.show_loading(False)
        # Re-enable login button
        for widget in self.master.winfo_children():
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "Connect":
                widget.configure(state="normal")
        
        # Proceed to main app
        self.master.destroy()
        root = ctk.CTk()
        app = MinecraftSyncApp(root)
        root.mainloop()
        
    def on_connection_failed(self, error):
        self.show_loading(False)
        # Re-enable login button
        for widget in self.master.winfo_children():
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "Connect":
                widget.configure(state="normal")
        
        self.error_label.configure(text=f"Connection failed: {error}")
# === MAIN ===
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    
    login_root = ctk.CTk()
    login_app = LoginWindow(login_root)
    login_root.mainloop()