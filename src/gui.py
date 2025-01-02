import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Combobox
import json
from simulation import Simulation
from loader import load_inventory, load_simulation_config, create_characters

class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulation Configuration")
        
        self.job1_path = tk.StringVar()
        self.db_path = tk.StringVar()
        self.num_simulations = tk.IntVar(value=100)
        self.simulation_results = []
        
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self.root, text="Job1 JSON File:").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(self.root, textvariable=self.job1_path, width=50).grid(row=0, column=1)
        tk.Button(self.root, text="Browse", command=self.browse_job1).grid(row=0, column=2)
        
        tk.Label(self.root, text="DB JSON File:").grid(row=1, column=0, sticky=tk.W)
        tk.Entry(self.root, textvariable=self.db_path, width=50).grid(row=1, column=1)
        tk.Button(self.root, text="Browse", command=self.browse_db).grid(row=1, column=2)
        
        tk.Label(self.root, text="Number of Simulations:").grid(row=2, column=0, sticky=tk.W)
        tk.Entry(self.root, textvariable=self.num_simulations, width=10).grid(row=2, column=1, sticky=tk.W)
        
        tk.Button(self.root, text="Run Simulation", command=self.run_simulation).grid(row=3, column=0, columnspan=3)
        
        tk.Label(self.root, text="Select Simulation:").grid(row=4, column=0, sticky=tk.W)
        self.simulation_selector = Combobox(self.root, state="readonly")
        self.simulation_selector.grid(row=4, column=1)
        tk.Button(self.root, text="Show Details", command=self.show_simulation_details).grid(row=4, column=2)
        
        self.text_area = tk.Text(self.root, wrap=tk.WORD, width=80, height=50)
        self.text_area.grid(row=5, column=0, columnspan=3, pady=10)

    def browse_job1(self):
        file_path = filedialog.askopenfilename(initialdir='./sim', filetypes=[("JSON files", "*.json")])
        if file_path:
            self.job1_path.set(file_path)
            self.load_job1(file_path)

    def browse_db(self):
        file_path = filedialog.askopenfilename(initialdir='./db', filetypes=[("JSON files", "*.json")])
        if file_path:
            self.db_path.set(file_path)
            self.load_db(file_path)

    def load_job1(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                self.text_area.delete(1.0, tk.END)
                self.text_area.insert(tk.END, json.dumps(data, indent=4, ensure_ascii=False))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load job1.json: {e}")

    def load_db(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                self.text_area.delete(1.0, tk.END)
                self.text_area.insert(tk.END, json.dumps(data, indent=4, ensure_ascii=False))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load db.json: {e}")

    def run_simulation(self):
        try:
            inventory_data = load_inventory(self.db_path.get())
            config_data = load_simulation_config(self.job1_path.get())
            factions = create_characters(config_data['factions'], inventory_data)
            num_simulations = self.num_simulations.get()

            sim = Simulation(factions)
            self.simulation_results = sim.run_simulation(num_simulations)
            metrics = sim.gather_metrics(self.simulation_results)
            
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(tk.END, json.dumps(metrics, indent=4, ensure_ascii=False))
            
            # Update the simulation selector
            self.simulation_selector['values'] = [f"Simulation {i+1}" for i in range(num_simulations)]
            self.simulation_selector.current(0)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run simulation: {e}")

    def show_simulation_details(self):
        try:
            selected_index = self.simulation_selector.current()
            if selected_index >= 0:
                selected_simulation = self.simulation_results[selected_index]
                formatted_log = self.format_action_log(selected_simulation['action_log'])
                self.text_area.delete(1.0, tk.END)
                self.text_area.insert(tk.END, formatted_log)
            else:
                messagebox.showwarning("Warning", "No simulation selected.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show simulation details: {e}")

    def format_action_log(self, action_log):
        formatted_log = ""
        for action in action_log:
            if action['action'] == "initiate_combat":
                formatted_log += f"Combat initiated between factions.\n"
            elif action['action'] == "engage":
                formatted_log += f"{action['attacker']} engages {action['target']}.\n"
            elif action['action'] == "attack":
                formatted_log += f"{action['attacker']} attacks {action['target']}.\n"
                formatted_log += f"  Attack roll: {action['details']['attack_roll']}\n"
                formatted_log += f"  Damage: {action['details']['damage']}\n"
                formatted_log += f"  {action['target']} health: {action['enemy_health']}\n"
            elif action['action'] == "ranged_attack":
                formatted_log += f"{action['attacker']} shoots at {action['target']}.\n"
                formatted_log += f"  Attack roll: {action['details']['attack_roll']}\n"
                formatted_log += f"  Damage: {action['details']['damage']}\n"
                formatted_log += f"  {action['target']} health: {action['enemy_health']}\n"
            formatted_log += "\n"
        return formatted_log

if __name__ == "__main__":
    root = tk.Tk()
    app = SimulationGUI(root)
    root.mainloop()