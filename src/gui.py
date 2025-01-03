import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Combobox, Treeview, Scrollbar
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
        
        self.tree = Treeview(self.root, columns=("Action", "Attacker", "Target", "Details", "Target HP"), show="headings")
        self.tree.heading("Action", text="Action")
        self.tree.heading("Attacker", text="Attacker")
        self.tree.heading("Target", text="Target")
        self.tree.heading("Details", text="Details")
        self.tree.heading("Target HP", text="Target HP")
        
        self.tree.column("Action", width=100)
        self.tree.column("Attacker", width=100)
        self.tree.column("Target", width=100)
        self.tree.column("Details", width=300)
        self.tree.column("Target HP", width=100)
        
        self.tree.grid(row=5, column=0, columnspan=3, pady=10)
        
        scrollbar = Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=5, column=3, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

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
                self.tree.delete(*self.tree.get_children())
                self.tree.insert("", tk.END, values=("Job1 JSON Loaded", "", "", "", ""))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load job1.json: {e}")

    def load_db(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                self.tree.delete(*self.tree.get_children())
                self.tree.insert("", tk.END, values=("DB JSON Loaded", "", "", "", ""))
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
            
            self.tree.delete(*self.tree.get_children())
            self.tree.insert("", tk.END, values=("Simulation Completed", "", "", "", ""))
            
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
                self.tree.delete(*self.tree.get_children())
                self.populate_treeview(selected_simulation['action_log'])
            else:
                messagebox.showwarning("Warning", "No simulation selected.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show simulation details: {e}")

    def populate_treeview(self, action_log):
        for action in action_log:
            if action['action'] == "initiate_combat":
                self.tree.insert("", tk.END, values=("Initiate Combat", "", "", action['details'], ""))
            elif action['action'] == "engage":
                self.tree.insert("", tk.END, values=("Engage", action['attacker'], action['target'], action['details'], ""))
            elif action['action'] == "attack":
                self.tree.insert("", tk.END, values=("Attack", action['attacker'], action['target'], f"Attack roll: {action['details']['attack_roll']}, Damage: {action['details']['damage']}", action['enemy_health']))
            elif action['action'] == "ranged_attack":
                self.tree.insert("", tk.END, values=("Ranged Attack", action['attacker'], action['target'], f"Attack roll: {action['details']['attack_roll']}, Damage: {action['details']['damage']}", action['enemy_health']))

if __name__ == "__main__":
    root = tk.Tk()
    app = SimulationGUI(root)
    root.mainloop()