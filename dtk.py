import serial
import sys
import sqlite3
import os
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

humidity_data = []
temperature_data = []
ec_data = []
timestamps = []


def read_com_port():
    ser = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=1)
    try:
        while True:
            if ser.in_waiting > 0:
                pre_data = ser.readline().decode('utf-8').strip()
                data = parse_data_from(pre_data)
                add_inf_db(data)
                get_last_15_from_db(current_dev_id)  # Обновляем для текущего dev_id
    except KeyboardInterrupt:
        print("Программа завершена")
    finally:
        ser.close()


def parse_data_from(data):
    pre_parts = data.split(': ')
    if len(pre_parts) > 1:
        parts = pre_parts[1].split(' ')
        if len(parts) >= 4:
            return parts
    return []


def create_data_base():
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dev_id INTEGER,
            humidity REAL,
            temperature REAL,
            ec REAL,
            timestamp TEXT
        )
    ''')
    connection.commit()
    connection.close()


def add_inf_db(data):
    if len(data) < 4:
        print("Недостаточно данных для записи в базу:", data)
        return

    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO sensor_data(dev_id, humidity, temperature, ec, timestamp) VALUES (?, ?, ?, ?, ?)",
            (int(data[0]), float(data[1]), float(data[2]), float(data[3]), timestamp)
        )
        connection.commit()
    except ValueError as e:
        print("Ошибка в данных:", e, data)
    finally:
        connection.close()


def get_last_15_from_db(dev_id):
    global humidity_data, temperature_data, ec_data, timestamps
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    cursor.execute("""
        SELECT humidity, temperature, ec, timestamp
        FROM sensor_data
        WHERE dev_id = ?
        ORDER BY id DESC
        LIMIT 15
    """, (dev_id,))
    rows = cursor.fetchall()
    connection.close()
    humidity_data.clear()
    temperature_data.clear()
    ec_data.clear()
    timestamps.clear()
    for row in reversed(rows):
        humidity_data.append(row[0])
        temperature_data.append(row[1])
        ec_data.append(row[2])
        timestamps.append(row[3])


def get_all_device_ids():
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    cursor.execute("SELECT DISTINCT dev_id FROM sensor_data")
    device_ids = [row[0] for row in cursor.fetchall()]
    connection.close()
    return device_ids


def get_all_data_from_db():
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    cursor.execute("""
        SELECT dev_id, humidity, temperature, ec, timestamp
        FROM sensor_data
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    connection.close()
    return rows


def animate(i, axes):
    get_last_15_from_db(current_dev_id)
    if len(humidity_data) > 0:
        for ax in axes.flatten():
            ax.clear()
        axes[0, 0].plot(timestamps, humidity_data, label="Humidity", marker='o')
        axes[0, 0].set_title("Humidity")
        axes[0, 0].set_ylabel("Humidity (%)")
        axes[0, 0].grid(True)
        axes[0, 0].legend()
        axes[0, 0].set_xticks(range(len(timestamps)))
        axes[0, 0].set_xticklabels(timestamps, rotation=45, fontsize=4)

        axes[0, 1].plot(timestamps, temperature_data, label="Temperature", marker='x')
        axes[0, 1].set_title("Temperature")
        axes[0, 1].set_ylabel("Temperature (°C)")
        axes[0, 1].grid(True)
        axes[0, 1].legend()
        axes[0, 1].set_xticks(range(len(timestamps)))
        axes[0, 1].set_xticklabels(timestamps, rotation=45, fontsize=4)

        axes[1, 0].plot(timestamps, ec_data, label="EC", marker='s')
        axes[1, 0].set_title("EC")
        axes[1, 0].set_ylabel("EC (µS/cm)")
        axes[1, 0].grid(True)
        axes[1, 0].legend()
        axes[1, 0].set_xticks(range(len(timestamps)))
        axes[1, 0].set_xticklabels(timestamps, rotation=45, fontsize=4)

        axes[1, 1].axis('off')
        plt.tight_layout()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Sensor Data Viewer")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.graphs_tab = ttk.Frame(self.notebook)
        self.database_tab = ttk.Frame(self.notebook)
        self.device_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.graphs_tab, text="Graphs")
        self.notebook.add(self.database_tab, text="Database")
        self.notebook.add(self.device_tab, text="Device Data")

        self.setup_graphs_tab()
        self.setup_database_tab()
        self.setup_device_tab()

    def setup_graphs_tab(self):
        frame = tk.Frame(self.graphs_tab)
        frame.pack(fill=tk.BOTH, expand=True)

        self.figure, self.axes = plt.subplots(2, 2, figsize=(10, 6))
        self.canvas = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        device_ids = get_all_device_ids()
        self.device_combo = ttk.Combobox(frame, values=device_ids)
        self.device_combo.pack()
        self.device_combo.bind("<<ComboboxSelected>>", self.update_graphs)

        self.ani = FuncAnimation(self.figure, animate, fargs=(self.axes,), interval=1000)

    def setup_database_tab(self):
        frame = tk.Frame(self.database_tab)
        frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(frame, columns=("Device ID", "Humidity", "Temperature", "EC", "Timestamp"), show="headings")
        self.tree.heading("Device ID", text="Device ID")
        self.tree.heading("Humidity", text="Humidity")
        self.tree.heading("Temperature", text="Temperature")
        self.tree.heading("EC", text="EC")
        self.tree.heading("Timestamp", text="Timestamp")
        self.tree.pack(fill=tk.BOTH, expand=True)

        button_frame = tk.Frame(frame)
        button_frame.pack(fill=tk.X)

        clear_button = tk.Button(button_frame, text="Clear Database", command=self.clear_database)
        clear_button.pack(side=tk.LEFT)

        refresh_button = tk.Button(button_frame, text="Refresh", command=self.load_database)
        refresh_button.pack(side=tk.LEFT)

        self.load_database()

    def load_database(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        rows = get_all_data_from_db()
        for row in rows:
            self.tree.insert("", tk.END, values=row)

    def clear_database(self):
        connection = sqlite3.connect("sensor_data")
        cursor = connection.cursor()
        cursor.execute("DELETE FROM sensor_data")
        connection.commit()
        connection.close()
        self.load_database()

    def update_graphs(self, event=None):
        global current_dev_id
        current_dev_id = int(self.device_combo.get())
        self.canvas.draw()

    def setup_device_tab(self):
        # Setup similar to database tab, with data filtered by device ID
        pass


if __name__ == "__main__":
    create_data_base()
    current_dev_id = 18
    root = tk.Tk()
    app = App(root)
    threading.Thread(target=read_com_port, daemon=True).start()
    root.mainloop()
