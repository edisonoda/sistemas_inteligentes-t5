import os
import sys

# Garante que o diretorio do simulador (vs) esteja no caminho de busca do Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vs.environment import Env
from exp import Explorer
from soc import Rescuer

def main(vict_folder, env_folder, config_ag_folder):
    env = Env(vict_folder, env_folder)

    cfg_exp = []
    cfg_soc = []
    exp = []
    soc = []
    
    for i in range(3):
        cfg_exp.append(os.path.join(config_ag_folder, f"exp_{i+1}.txt"))
        cfg_soc.append(os.path.join(config_ag_folder, f"soc_{i+1}.txt"))
        
        soc.append(Rescuer(env, cfg_soc[i]))
        exp.append(Explorer(env, cfg_exp[i], soc[0]))
        
    for i in range(3):
        soc[i].set_rescuers(soc)
        
    env.run()

if __name__ == '__main__':
    print("------------------")
    print("--- INICIO SMA ---")
    print("------------------")
    main_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(main_dir))
    
    grid_str = "94x94"
    vict_str = "408v"
    
    # Aponta para os datasets locais de T05_final
    vict_folder = os.path.join(main_dir, "datasets", "vict", vict_str)
    env_folder = os.path.join(main_dir, "datasets", "env", f"{grid_str}_{vict_str}")
    config_ag_folder = os.path.join(main_dir, "cfg")

    main(vict_folder, env_folder, config_ag_folder)
