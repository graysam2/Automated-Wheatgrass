import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import Calendar
import os
import csv
from datetime import datetime

SCHEDULE_FILE = "automation_schedule.csv"
offset = (800-530)/2 - 20 ##sorry for magic numbers, im
class SchedulerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Grass Batch Scheduler")
        self.root.geometry("800x500")
        self.root.resizable(False, False)
        self.root.configure(bg="#2c2c2c")
        

        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook", background="#2c2c2c", borderwidth=0)
        style.configure("TNotebook.Tab", background="#3a3a3a", foreground="white")
        style.map("TNotebook.Tab", background=[("selected", "#555555")])
        style.configure("TCombobox", fieldbackground="#3a3a3a", background="#3a3a3a", foreground="white")
        style.map("TCombobox",
            fieldbackground=[("readonly", "#3a3a3a")],
            background=[("readonly", "#3a3a3a")],
            foreground=[("readonly", "white")]
        )
        style.configure("Treeview", background="#2c2c2c", foreground="white", fieldbackground="#2c2c2c")
        style.configure("Treeview.Heading", background="#3a3a3a", foreground="white")

        self.tab_control = ttk.Notebook(root)
        self.tab_start = tk.Frame(self.tab_control, bg='#2e7d32')
        self.tab_view = tk.Frame(self.tab_control, bg="#2e7d32")
        self.tab_add = tk.Frame(self.tab_control, bg="#2e7d32")
        self.tab_control.add(self.tab_start, text="Start Batch")
        self.tab_control.add(self.tab_view, text="View Schedule")
        self.tab_control.add(self.tab_add, text="Add Task")
        self.tab_control.pack(expand=1, fill="both")

        self.build_start_tab()
        self.build_view_tab()
        self.build_add_tab()

    def build_start_tab(self):
        tk.Label(self.tab_start, text="The batch will", bg="#2e7d32", fg="white", font=("Segoe UI", 10)).place(x=50+offset, y=10)
        self.specifier_var = tk.StringVar(value="Start")
        self.specifier_menu = ttk.Combobox(self.tab_start, textvariable=self.specifier_var, values=["Start", "End"], state="readonly", width=10)
        self.specifier_menu.place(x=50+offset, y=35)
        tk.Label(self.tab_start, text="On", bg="#2e7d32", fg="white", font=("Segoe UI", 10)).place(x=50+offset, y=65)

        today = datetime.today()
        self.calendar = Calendar(
            self.tab_start,
            selectmode='day',
            year=today.year,
            month=today.month,
            day=today.day,
            background='#3a3a3a',
            foreground='white',
            headersbackground='#2e2e2e',
            headersforeground='white',
            normalbackground='#3a3a3a',
            normalforeground='white',
            weekendbackground='#3a3a3a',
            weekendforeground='white',
            selectbackground='#1e5631',
            selectforeground='white'
        )
        self.calendar.place(x=20+offset, y=90, width=250, height=200)

        tk.Label(self.tab_start, text="Upcoming Batches", bg="#2e7d32", fg="white", font=("Segoe UI", 10, "bold")).place(x=320+offset, y=65)
        self.batch_listbox = tk.Listbox(self.tab_start, font=("Segoe UI", 10), bg="#2c2c2c", fg="white", highlightbackground="#2e7d32")
        self.batch_listbox.place(x=300+offset, y=90, height=260, width=250)

        self.schedule_button = tk.Button(self.tab_start, text="Schedule Batch", font=("Segoe UI", 10, "bold"), bg="#3a3a3a", fg="white", command=self.schedule_batch)
        self.schedule_button.place(x=20+offset, y=300, width=250, height=50)

        self.refresh_batch_list()

    def build_view_tab(self):
        self.tree = ttk.Treeview(self.tab_view, columns=("timestamp", "device", "action", "value"), show="headings")
        self.tree.heading("timestamp", text="Timestamp")
        self.tree.heading("device", text="Device")
        self.tree.heading("action", text="Action")
        self.tree.heading("value", text="Value")
        self.tree.column("timestamp", width=200)
        self.tree.column("device", width=100)
        self.tree.column("action", width=100)
        self.tree.column("value", width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.refresh_schedule_table()

    def build_add_tab(self):
        tk.Label(self.tab_add, text="Schedule a Single Task", bg="#2e7d32", fg="white", font=("Segoe UI", 12, "bold")).pack(pady=10)

        form_frame = tk.Frame(self.tab_add, bg="#2e7d32")
        form_frame.pack(pady=10)

        labels = ["Device:", "Action:", "Value:", "Date:", "Time (HH:MM):"]
        for i, label in enumerate(labels):
            tk.Label(form_frame, text=label, bg="#2e7d32", fg="white").grid(row=i, column=0, sticky="e", padx=5, pady=5)

        self.device_var = tk.StringVar()
        self.device_menu = ttk.Combobox(form_frame, textvariable=self.device_var, values=["motor1", "motor2", "valve1", "valve2"], state="readonly")
        self.device_menu.grid(row=0, column=1, padx=5, pady=5)

        self.action_var = tk.StringVar()
        self.action_entry = ttk.Entry(form_frame, textvariable=self.action_var)
        self.action_entry.grid(row=1, column=1, padx=5, pady=5)

        self.value_var = tk.StringVar()
        self.value_entry = ttk.Entry(form_frame, textvariable=self.value_var)
        self.value_entry.grid(row=2, column=1, padx=5, pady=5)

        today = datetime.today()
        self.add_calendar = Calendar(
            form_frame,
            selectmode='day',
            year=today.year,
            month=today.month,
            day=today.day,
            background='#3a3a3a',
            foreground='white',
            headersbackground='#2e2e2e',
            headersforeground='white',
            normalbackground='#3a3a3a',
            normalforeground='white',
            weekendbackground='#3a3a3a',
            weekendforeground='white',
            selectbackground='#1e5631',
            selectforeground='white'
        )
        self.add_calendar.grid(row=3, column=1, padx=5, pady=5)

        self.time_var = tk.StringVar()
        self.time_entry = ttk.Entry(form_frame, textvariable=self.time_var)
        self.time_entry.grid(row=4, column=1, padx=5, pady=5)

        submit_btn = tk.Button(self.tab_add, text="Add Task", font=("Segoe UI", 10, "bold"), bg="#3a3a3a", fg="white", command=self.add_task)
        submit_btn.pack(pady=10)

    def refresh_schedule_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, newline='') as f:
                reader = csv.DictReader(f)
                sorted_tasks = sorted(reader, key=lambda row: row["timestamp"])
                for row in sorted_tasks:
                    self.tree.insert("", tk.END, values=(row["timestamp"], row["device"], row["action"], row["value"]))

    def refresh_batch_list(self):
        self.batch_listbox.delete(0, tk.END)
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, newline='') as f:
                reader = csv.DictReader(f)
                # Filter for batch complete markers only
                batch_dates = sorted(set(
                    row["timestamp"].split()[0]
                    for row in reader
                    if row["device"] == "system" and row["action"] == "batch_complete"
                ))
                for date_str in batch_dates:
                    self.batch_listbox.insert(tk.END, datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d"))

    def schedule_batch(self):
        selected_date = self.calendar.get_date()
        specifier = self.specifier_var.get().lower()

        try:
            dt = datetime.strptime(selected_date, "%d/%m/%Y")
        except Exception as e:
            messagebox.showerror("Invalid Date", str(e))
            return

        os.system(f"python3 Scheduler.py {specifier} {dt.month} {dt.day}")
        self.refresh_batch_list()
        self.refresh_schedule_table()
        messagebox.showinfo("Success", f"Scheduled batch to {specifier} on {dt.strftime('%B %d')}")

    def add_task(self):
        device = self.device_var.get()
        action = self.action_var.get()
        value = self.value_var.get()
        date = self.add_calendar.get_date()
        time_str = self.time_var.get()

        try:
            timestamp = datetime.strptime(f"{date} {time_str}", "%m/%d/%Y %H:%M")
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            messagebox.showerror("Invalid Time Format", "Please use HH:MM format for time.")
            return

        if not (device and action and value):
            messagebox.showerror("Missing Data", "Please fill in all fields.")
            return

        new_task = {"timestamp": timestamp_str, "device": device, "action": action, "value": value}
        file_exists = os.path.exists(SCHEDULE_FILE)

        with open(SCHEDULE_FILE, "a", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "device", "action", "value"])
            if not file_exists or os.path.getsize(SCHEDULE_FILE) == 0:
                writer.writeheader()
            writer.writerow(new_task)

        self.refresh_schedule_table()
        messagebox.showinfo("Task Added", f"Task scheduled for {timestamp_str}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SchedulerGUI(root)
    root.mainloop()