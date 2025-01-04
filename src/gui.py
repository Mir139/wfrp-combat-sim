import tkinter as tk
from tkinter import filedialog, messagebox, Toplevel, Text
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
        
        self.global_tree = Treeview(self.root, columns=("#", "Job File", "Total Battles", "Survival Prob. (factions)", "Survival Prob. (individuals)", "Average Remaining Health"), show="headings")
        self.global_tree.heading("#", text="#")
        self.global_tree.heading("Job File", text="Job File")
        self.global_tree.heading("Total Battles", text="Total Battles")
        self.global_tree.heading("Survival Prob. (factions)", text="Survival Prob. (factions)")
        self.global_tree.heading("Survival Prob. (individuals)", text="Survival Prob. (individuals)")
        self.global_tree.heading("Average Remaining Health", text="Average Remaining Health")
        
        self.global_tree.column("#", width=10)
        self.global_tree.column("Job File", width=200)
        self.global_tree.column("Total Battles", width=75)
        self.global_tree.column("Survival Prob. (factions)", width=300)
        self.global_tree.column("Survival Prob. (individuals)", width=400)
        self.global_tree.column("Average Remaining Health", width=400)
        
        self.global_tree.grid(row=6, column=0, columnspan=3, pady=10)
        
        scrollbar = Scrollbar(self.root, orient="vertical", command=self.global_tree.yview)
        scrollbar.grid(row=6, column=3, sticky="ns")
        self.global_tree.configure(yscrollcommand=scrollbar.set)
        self.global_tree.bind("<ButtonRelease-1>", self.on_click)
        self.global_tree.bind("<Double-1>", self.on_double_click)

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
                #self.global_tree.insert("", 0, values=(file_path, "Job1 JSON Loaded", "", ""))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load job1.json: {e}")

    def load_db(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                #self.global_tree.insert("", 0, values=(file_path, "DB JSON Loaded", "", ""))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load db.json: {e}")

    def run_simulation(self):
        try:
            inventory_data = load_inventory(self.db_path.get())
            config_data = load_simulation_config(self.job1_path.get())
            factions = create_characters(config_data['factions'], inventory_data)
            num_simulations = self.num_simulations.get()

            sim = Simulation(factions)
            sim_results = sim.run_simulation(num_simulations)
            simulation_wrapper = {
                "results": sim_results,
                "metrics": sim.gather_metrics(sim_results)
            }

            survival_probabilities = self.format_decimals(simulation_wrapper["metrics"]["survival_probabilities"].items(), 2)
            individual_survival_probabilities = self.format_decimals(simulation_wrapper["metrics"]["individual_survival_probabilities"].items(), 2)
            individual_average_remaining_health = self.format_decimals(simulation_wrapper["metrics"]["individual_average_remaining_health"].items(), 2)
                        
            self.simulation_results.append(simulation_wrapper)
            
            truncated_job_file = self.truncate_path(self.job1_path.get(), 32)
            self.global_tree.insert("", 0, values=(len(self.simulation_results)-1, truncated_job_file, simulation_wrapper["metrics"]["total_battles"], json.dumps(survival_probabilities, ensure_ascii=False), json.dumps(individual_survival_probabilities, ensure_ascii=False), json.dumps(individual_average_remaining_health, ensure_ascii=False)))
            
            # Put the selection on the latest inserted job
            last_inserted_job = self.global_tree.get_children()[0]
            self.global_tree.focus(last_inserted_job)
            self.global_tree.selection_set(last_inserted_job)

            # Update the simulation selector
            self.update_simulation_selector(simulation_wrapper["metrics"]["total_battles"])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run simulation: {e}")
    
    def format_decimals(self, numbers, decimals):
        if decimals == 2:
            numbers_formated = {k: f"{v:.2f}" for k, v in numbers}
        return numbers_formated
    
    def update_simulation_selector(self, num_simulations):
        self.simulation_selector['values'] = [f"Simulation {i+1}" for i in range(num_simulations)]
        self.simulation_selector.current(0)
    
    def truncate_path(self, path, max_length):
        if len(path) > max_length:
            return "..." + path[-(max_length-3):]
        return path

    def show_simulation_details(self):
        try:
            item = self.global_tree.selection()[0]
            selected_job = int(self.global_tree.item(item, "values")[0])
            selected_index = self.simulation_selector.current()
            if selected_job >= 0 and selected_index >= 0:
                selected_simulation = self.simulation_results[selected_job]["results"][selected_index]
                self.open_details_window(selected_simulation['action_log'], selected_job, selected_index)
            else:
                messagebox.showwarning("Warning", "No simulation selected.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show simulation details: {e}")

    def open_details_window(self, action_log, job_id, sim_id):
        details_window = Toplevel(self.root)
        details_window.title(f"Simulation Details - Job #{job_id} - Simulation {sim_id+1}")
        
        tree = Treeview(details_window, columns=("Action", "Attacker", "Target", "Roll", "DR", "Damage", "Target HP"), show="headings")
        tree.heading("Action", text="Action")
        tree.heading("Attacker", text="Attacker")
        tree.heading("Target", text="Target")
        tree.heading("Roll", text="Roll")
        tree.heading("DR", text="DR")
        tree.heading("Damage", text="Damage")
        tree.heading("Target HP", text="Target HP")
        
        tree.column("Action", width=100)
        tree.column("Attacker", width=150)
        tree.column("Target", width=150)
        tree.column("Roll", width=50)
        tree.column("DR", width=50)
        tree.column("Damage", width=60)
        tree.column("Target HP", width=100)
        
        tree.grid(row=0, column=0, columnspan=3, pady=10)
        
        scrollbar = Scrollbar(details_window, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=3, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        
        self.populate_treeview(tree, action_log)

    def populate_treeview(self, tree, action_log):
        for action in action_log:
            if action['action'] == "initiate_combat":
                tree.insert("", tk.END, values=("Initiate Combat", "", "", "", "", "", ""))
            elif action['action'] == "engage":
                tree.insert("", tk.END, values=("Engage", action['attacker'], action['target'], "", "", "", ""))
            elif action['action'] == "attack":
                tree.insert("", tk.END, values=("Attack", action['attacker'], action['target'], f"{action['details']['attack_roll']} | {action['details']['enemy_roll']}", f"{action['details']['attack_dr']} | {action['details']['enemy_dr']}", action['details']['damage'], action['enemy_health']))
            elif action['action'] == "ranged_attack":
                tree.insert("", tk.END, values=("Ranged Attack", action['attacker'], action['target'], action['details']['attack_roll'], "", action['details']['damage'], action['enemy_health']))
            elif action['action'] == "death":
                tree.insert("", tk.END, values=("Death", "", action['target'], "", "", "", action['enemy_health']))

    def on_click(self, event):
        item = self.global_tree.focus()
        num_simulations = int(self.global_tree.item(item, "values")[2])
        self.update_simulation_selector(num_simulations)

    def on_double_click(self, event):
        item = self.global_tree.selection()[0]
        job_id = int(self.global_tree.item(item, "values")[0])
        self.open_job_details_window(job_id)

    def open_job_details_window(self, job_id):
        simulation_wrapper = self.simulation_results[job_id]
        details_window = Toplevel(self.root)
        details_window.title(f"Job Details #{job_id}")
        
        text = Text(details_window, wrap=tk.WORD, width=80, height=20)
        text.grid(row=0, column=0, columnspan=3, pady=10)
        
        scrollbar = Scrollbar(details_window, orient="vertical", command=text.yview)
        scrollbar.grid(row=0, column=3, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)
        formatted_log = self.format_job_result(simulation_wrapper)
        text.delete(1.0, tk.END)
        text.insert(tk.END, formatted_log)

    def format_job_result(self, simulation_wrapper):
        survival_probabilities = self.format_decimals(simulation_wrapper["metrics"]["survival_probabilities"].items(), 2)
        individual_survival_probabilities = self.format_decimals(simulation_wrapper["metrics"]["individual_survival_probabilities"].items(), 2)
        individual_average_remaining_health = self.format_decimals(simulation_wrapper["metrics"]["individual_average_remaining_health"].items(), 2)
        formatted_log = ""
        formatted_log += f"Total battles: {simulation_wrapper["metrics"]["total_battles"]}\n"
        formatted_log += f"Survival probabilities:\n"
        for faction in survival_probabilities:
            formatted_log += f"  {faction}: {survival_probabilities[faction]}\n"
        formatted_log += f"\n"
        formatted_log += f"Individual survival probabilities / Average remaining health:\n"
        for member in individual_survival_probabilities:
            formatted_log += f"  {member}: {individual_survival_probabilities[member]} - {individual_average_remaining_health[member]}\n"
        formatted_log += f"\n"

        return formatted_log
    
if __name__ == "__main__":
    root = tk.Tk()
    app = SimulationGUI(root)
    root.mainloop()