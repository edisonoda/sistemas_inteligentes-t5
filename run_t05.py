import os
import subprocess
import re

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else r"c:\Users\crisn\Desktop\-\si\tarefa_si3"
T05_DIR = os.path.join(WORKSPACE_DIR, "T05_final")
CFG_DIR = os.path.join(T05_DIR, "cfg")

EXP_FILES = ["exp_1.txt", "exp_2.txt", "exp_3.txt"]
SOC_FILES = ["soc_1.txt", "soc_2.txt", "soc_3.txt"]

def update_tlims(exp_tlim, soc_tlim):
    print(f"\nUpdating configurations: Explorer TLIM={exp_tlim}, Rescuer TLIM={soc_tlim}")
    
    # Update Explorers
    for name in EXP_FILES:
        path = os.path.join(CFG_DIR, name)
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if line.startswith("TLIM"):
                new_lines.append(f"TLIM {exp_tlim}\n")
            else:
                new_lines.append(line)
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
    # Update Rescuers
    for name in SOC_FILES:
        path = os.path.join(CFG_DIR, name)
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if line.startswith("TLIM"):
                new_lines.append(f"TLIM {soc_tlim}\n")
            else:
                new_lines.append(line)
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

def run_simulation(scenario_name):
    print(f"\n{'='*60}\n RUNNING SIMULATION: {scenario_name} \n{'='*60}")
    # Run main.py in T05_final
    main_path = os.path.join(T05_DIR, "main.py")
    result = subprocess.run(["python", main_path], input="\n", capture_output=True, text=True, cwd=T05_DIR)
    
    # Print raw output to console
    print(result.stdout)
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
        
    return result.stdout

def parse_results(stdout, scenario_name):
    # We can write a parser using regex
    found_matches = re.findall(r"Total of found victims\s*\(Ve\)\s*=\s*(\d+)", stdout)
    saved_matches = re.findall(r"Total of saved victims\s*\(Vs\)\s*=\s*(\d+)", stdout)
    
    # Search individual explorer counts to calculate overlap:
    agent_found = {}
    current_agent = None
    for line in stdout.splitlines():
        agent_match = re.match(r"\[\s*Agent\s+(\w+)\s*\]", line)
        if agent_match:
            current_agent = agent_match.group(1)
        if current_agent and "Total of found victims" in line:
            num_match = re.search(r"=\s*(\d+)", line)
            if num_match:
                agent_found[current_agent] = int(num_match.group(1))
                
    print(f"\n--- Parse Results for {scenario_name} ---")
    print(f"Individual Found: {agent_found}")
    
    # Calculate overlap if we have EXP_1, EXP_2, EXP_3
    exp_keys = [k for k in agent_found.keys() if k.startswith("EXP")]
    sum_individual = sum(agent_found[k] for k in exp_keys)
    
    # In overall accumulated summary, there's a block like:
    # "Total of found victims     (Ve)  =  16" (this is unique found)
    # Let's search for unique found in the accumulated results
    unique_found = 0
    lines = stdout.splitlines()
    for i, line in enumerate(lines):
        if "FOUND victims by all explorer agents" in line:
            # The next few lines contain "Total of found victims (Ve) = XX"
            for j in range(i+1, min(i+300, len(lines))):
                if "Total of found victims" in lines[j] and "(Ve)" in lines[j]:
                    m = re.search(r"=\s*(\d+)", lines[j])
                    if m:
                        unique_found = int(m.group(1))
                        break
            break

    # Let's do the same for unique saved
    unique_saved = 0
    for i, line in enumerate(lines):
        if "SAVED victims by all rescuer agents" in line or "SAVED victims by all agents" in line or "saved victims" in line:
            # Let's look for "Total of saved victims"
            pass
    # We can also get unique saved from the end print of SAVED victims by all agents:
    for i, line in enumerate(lines):
        if "SAVED" in line and "all" in line:
            for j in range(i+1, min(i+300, len(lines))):
                if "Total of saved victims" in lines[j] and "(Vs)" in lines[j]:
                    m = re.search(r"=\s*(\d+)", lines[j])
                    if m:
                        unique_saved = int(m.group(1))
                        break

    overlap = 0.0
    if unique_found > 0:
        overlap = (sum_individual / unique_found) - 1.0
        
    print(f"Total Found Sum (with repeats): {sum_individual}")
    print(f"Unique Found (Ve): {unique_found}")
    print(f"Unique Saved (Vs): {unique_saved}")
    print(f"Overlap: {overlap:.4f}")
    if unique_found > 0:
        print(f"Vs/Ve ratio: {unique_saved / unique_found:.4f}")
    else:
        print("Vs/Ve ratio: N/A")

def main():
    # Scenario 1: Relaxada
    update_tlims(5000, 3000)
    stdout_relax = run_simulation("RELAXADA (Exploracao=5000, Socorro=3000)")
    parse_results(stdout_relax, "RELAXADA")
    
    # Scenario 2: Restrita
    update_tlims(500, 300)
    stdout_restr = run_simulation("RESTRITA (Exploracao=500, Socorro=300)")
    parse_results(stdout_restr, "RESTRITA")

if __name__ == "__main__":
    main()

