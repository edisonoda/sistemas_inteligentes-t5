import os
import pandas as pd
import math
import random
import heapq
import numpy as np
from vs.abstract_agent import AbstAgent
from vs.constants import VS
from map import Map

class Rescuer(AbstAgent):
    def __init__(self, env, config_file):
        super().__init__(env, config_file)
        self.map = Map()
        self.victims = {}
        self.plan = []
        self.plan_x = 0
        self.plan_y = 0
        self.plan_visited = set()
        self.plan_rtime = self.TLIM
        self.x = 0
        self.y = 0
        self.explorers_remaining = {"EXP_1", "EXP_2", "EXP_3"}
        self.rescuers = []
        self.set_state(VS.IDLE)

    def set_rescuers(self, rescuers_lst):
        self.rescuers = rescuers_lst

    def solve_tsp_sa(self, start_pos, victim_coords, victim_ids, initial_temp=100.0, cooling_rate=0.99, min_temp=0.001):
        # Tempera Simulada para resolver o problema do caixeiro viajante (TSP)
        n = len(victim_coords)
        if n == 0:
            return []
        if n == 1:
            return victim_ids

        # Precomputa matriz de distancias
        dist_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                dist_matrix[i][j] = math.sqrt((victim_coords[i][0] - victim_coords[j][0])**2 + (victim_coords[i][1] - victim_coords[j][1])**2)
                
        start_dist = [math.sqrt((start_pos[0] - vc[0])**2 + (start_pos[1] - vc[1])**2) for vc in victim_coords]

        def calc_distance(permutation):
            dist = start_dist[permutation[0]]
            for i in range(n - 1):
                dist += dist_matrix[permutation[i]][permutation[i+1]]
            return dist

        # Gera solucao inicial usando vizinho mais proximo (Guloso)
        current_perm = []
        unvisited = set(range(n))
        best_d = float('inf')
        curr_idx = None
        for i in range(n):
            if start_dist[i] < best_d:
                best_d = start_dist[i]
                curr_idx = i
        current_perm.append(curr_idx)
        unvisited.remove(curr_idx)
        while unvisited:
            best_d = float('inf')
            next_idx = None
            for i in unvisited:
                if dist_matrix[curr_idx][i] < best_d:
                    best_d = dist_matrix[curr_idx][i]
                    next_idx = i
            current_perm.append(next_idx)
            unvisited.remove(next_idx)
            curr_idx = next_idx

        current_dist = calc_distance(current_perm)
        best_perm = list(current_perm)
        best_dist = current_dist

        # Loop da Tempera Simulada
        T = initial_temp
        while T > min_temp:
            for _ in range(100):
                neighbor = list(current_perm)
                i, j = sorted(random.sample(range(n), 2))
                neighbor[i:j+1] = reversed(neighbor[i:j+1]) # 2-opt swap
                
                neighbor_dist = calc_distance(neighbor)
                diff = neighbor_dist - current_dist
                
                if diff < 0 or random.random() < math.exp(-diff / T):
                    current_perm = neighbor
                    current_dist = neighbor_dist
                    if current_dist < best_dist:
                        best_dist = current_dist
                        best_perm = list(current_perm)
            T *= cooling_rate

        return [victim_ids[idx] for idx in best_perm]

    def a_star(self, start, goal):
        # Algoritmo de busca A* para encontrar caminhos no grid
        if start == goal:
            return []

        queue = []
        
        def heuristic(a, b):
            dx = abs(a[0] - b[0])
            dy = abs(a[1] - b[1])
            return self.COST_LINE * (dx + dy) + (self.COST_DIAG - 2 * self.COST_LINE) * min(dx, dy)

        heapq.heappush(queue, (heuristic(start, goal), 0.0, start, []))
        visited = {start: 0.0}

        directions = [
            (0, -1, self.COST_LINE),
            (1, -1, self.COST_DIAG),
            (1, 0, self.COST_LINE),
            (1, 1, self.COST_DIAG),
            (0, 1, self.COST_LINE),
            (-1, 1, self.COST_DIAG),
            (-1, 0, self.COST_LINE),
            (-1, -1, self.COST_DIAG)
        ]

        while queue:
            f, g, curr, path = heapq.heappop(queue)

            if curr == goal:
                return path

            if g > visited.get(curr, float('inf')):
                continue

            for dx, dy, base_cost in directions:
                neighbor = (curr[0] + dx, curr[1] + dy)
                if self.map.in_map(neighbor):
                    cell_data = self.map.get(neighbor)
                    difficulty = cell_data[0]
                    if difficulty < 100:
                        step_cost = base_cost * difficulty
                        new_g = g + step_cost
                        if neighbor not in visited or new_g < visited[neighbor]:
                            visited[neighbor] = new_g
                            new_path = path + [(dx, dy)]
                            heapq.heappush(queue, (new_g + heuristic(neighbor, goal), new_g, neighbor, new_path))
                            
        return None

    def calculate_path_cost(self, path, start_pos):
        cost = 0.0
        curr_x, curr_y = start_pos
        for dx, dy in path:
            next_x = curr_x + dx
            next_y = curr_y + dy
            if dx != 0 and dy != 0:
                base = self.COST_DIAG
            else:
                base = self.COST_LINE
            cell_data = self.map.get((next_x, next_y))
            difficulty = cell_data[0] if cell_data else 1.0
            cost += base * difficulty
            curr_x, curr_y = next_x, next_y
        return cost
        
    def do_rescue(self, map, clusters):
        self.set_state(VS.ACTIVE)
        print(f"{self.NAME}: iniciando planejamento de resgate...")
        
        # Mapeia pasta de clusters ordenados
        t05_dir = os.path.dirname(self.config_folder)
        clusters_dir = os.path.join(t05_dir, "clusters")
        os.makedirs(clusters_dir, exist_ok=True)
        
        # Define os clusters atribuidos diretamente pelo mestre
        my_clusters = [c[0] for c in clusters]
            
        print(f"{self.NAME}: clusters atribuidos: {my_clusters}")
        
        self.plan = []
        self.plan_x = 0
        self.plan_y = 0
        self.plan_rtime = self.TLIM
        
        for cluster_id in my_clusters:
            # Obtem as vitimas do cluster a partir do parametro clusters em memoria
            cluster_vids = None
            for cid, vids in clusters:
                if cid == cluster_id:
                    cluster_vids = vids
                    break
                    
            if not cluster_vids:
                continue
                
            cluster_coords = []
            valid_vids = []
            for vid in cluster_vids:
                if vid in self.victims:
                    cluster_coords.append(self.victims[vid][0])
                    valid_vids.append(vid)
                    
            if not valid_vids:
                continue
                
            # Otimiza trajeto usando Tempera Simulada
            sorted_vids = self.solve_tsp_sa((self.plan_x, self.plan_y), cluster_coords, valid_vids)
            
            # Salva na pasta clusters apenas os clusters ordenados
            cluster_file = os.path.join(clusters_dir, f"cluster_{cluster_id}.txt")
            with open(cluster_file, "w") as f:
                for vid in sorted_vids:
                    f.write(f"{vid}\n")
                    
            time_out = False
            for vid in sorted_vids:
                vic_pos = self.victims[vid][0]
                
                path_to_vic = self.a_star((self.plan_x, self.plan_y), vic_pos)
                if path_to_vic is None:
                    continue
                    
                cost_to_vic = self.calculate_path_cost(path_to_vic, (self.plan_x, self.plan_y))
                path_to_base = self.a_star(vic_pos, (0, 0))
                if path_to_base is None:
                    continue
                    
                cost_to_base = self.calculate_path_cost(path_to_base, vic_pos)
                
                # Consumo energetico previsto: ir + salvar + voltar
                total_needed = cost_to_vic + self.COST_FIRST_AID + cost_to_base
                
                if self.plan_rtime >= total_needed:
                    for dx, dy in path_to_vic:
                        self.plan.append((dx, dy, False))
                    # Marca o ultimo passo para aplicar o kit de primeiro socorro
                    self.plan[-1] = (self.plan[-1][0], self.plan[-1][1], True)
                    
                    self.plan_rtime -= (cost_to_vic + self.COST_FIRST_AID)
                    self.plan_x, self.plan_y = vic_pos
                else:
                    print(f"{self.NAME}: Sem energia suficiente para a vitima {vid}. Iniciando retorno à base.")
                    time_out = True
                    break
                    
            if time_out:
                break
                
        # Planeja retorno a base (0, 0)
        if (self.plan_x, self.plan_y) != (0, 0):
            path_to_base = self.a_star((self.plan_x, self.plan_y), (0, 0))
            if path_to_base is not None:
                for dx, dy in path_to_base:
                    self.plan.append((dx, dy, False))
                    
        print(f"{self.NAME}: Plano gerado com sucesso! {len(self.plan)} acoes.")

    def merge_maps(self, exp_name, map, victims):
        # Mesclar mapas locais
        for coord, cell_data in map.map_data.items():
            if not self.map.in_map(coord):
                difficulty, victim_seq, actions_res = cell_data
                self.map.add(coord, difficulty, victim_seq, actions_res)
                
        self.victims.update(victims)
        self.explorers_remaining.discard(exp_name)
        
        if self.explorers_remaining:
            print(f"{self.NAME}: Aguardando exploradores: {self.explorers_remaining}")
            return
            
        print(f"{self.NAME}: Todos os exploradores finalizaram! Mesclagem completa.")
        self.map.draw()
        
        # Escreve map.csv contendo o mapa de exploracao unificado
        t05_dir = os.path.dirname(self.config_folder)
        map_csv_path = os.path.join(t05_dir, "map.csv")
        
        rows = []
        for (x, y), (difficulty, victim_seq, actions_res) in self.map.map_data.items():
            row = {
                'x_rel': x, 'y_rel': y, 'obst': difficulty, 'id': victim_seq,
                'idade': 0, 'fc': 0, 'fr': 0, 'pas': 0, 'spo2': 0, 'temp': 0.0,
                'pr': 0, 'sg': 0, 'fx': 0, 'queim': 0, 'gcs': 0, 'avpu': 0,
                'tri': 0, 'sobr': 0.0
            }
            if victim_seq != VS.NO_VICTIM and victim_seq in self.victims:
                coords, vs = self.victims[victim_seq]
                row.update({
                    'idade': vs[1], 'fc': vs[2], 'fr': vs[3], 'pas': vs[4], 'spo2': vs[5], 'temp': vs[6],
                    'pr': vs[7], 'sg': vs[8], 'fx': vs[9], 'queim': vs[10], 'gcs': vs[11], 'avpu': vs[12],
                    'tri': vs[13], 'sobr': vs[14]
                })
            rows.append(row)
            
        pd.DataFrame(rows).to_csv(map_csv_path, index=False)
        print(f"{self.NAME}: Arquivo map.csv exportado com sucesso em {map_csv_path}!")
        
        # Executa clustering dinâmico DBSCAN
        from sklearn.preprocessing import MinMaxScaler
        from sklearn.cluster import DBSCAN
        
        v_ids = list(self.victims.keys())
        X_cluster = []
        for vid in v_ids:
            coords, vs = self.victims[vid]
            X_cluster.append([coords[0], coords[1], vs[14]]) # x_rel, y_rel, sobr_pred (índice 14)
            
        if X_cluster:
            scaler = MinMaxScaler()
            X_scaled = scaler.fit_transform(X_cluster)
            
            db = DBSCAN(eps=0.10, min_samples=5)
            labels = db.fit_predict(X_scaled)
            
            # Agrupa clusters validos e outliers (ruidos)
            cluster_groups = {}
            outliers = []
            for i, label in enumerate(labels):
                vid = v_ids[i]
                if label != -1:
                    if label not in cluster_groups:
                        cluster_groups[label] = []
                    cluster_groups[label].append(vid)
                else:
                    outliers.append(vid)
                    
            # Associa outliers ao cluster valido mais proximo espacialmente (2D), se a distancia for aceitavel
            if cluster_groups:
                centroids = {}
                for label, vids in cluster_groups.items():
                    coords_list = [self.victims[vid][0] for vid in vids]
                    cx = np.mean([c[0] for c in coords_list])
                    cy = np.mean([c[1] for c in coords_list])
                    centroids[label] = (cx, cy)
                
                # Limite maximo de distancia em celulas de grid (ex: 20 celulas)
                MAX_CLUSTER_DIST = 20.0
                
                for vid in outliers:
                    ox, oy = self.victims[vid][0]
                    best_label = None
                    min_dist = float('inf')
                    for label, (cx, cy) in centroids.items():
                        dist = math.sqrt((cx - ox)**2 + (cy - oy)**2)
                        if dist < min_dist:
                            min_dist = dist
                            best_label = label
                    
                    if min_dist <= MAX_CLUSTER_DIST:
                        cluster_groups[best_label].append(vid)
            else:
                # Se nao houver clusters validos, nao fazemos nada (todos os outliers permanecem como ruidos descartados)
                pass
                    
            # Prioriza clusters por menor sobrevivência média (sobr_pred no índice 14)
            cluster_priorities = []
            for label, vids in cluster_groups.items():
                mean_sobr = np.mean([self.victims[vid][1][14] for vid in vids])
                cluster_priorities.append((label, mean_sobr, vids))
                
            cluster_priorities.sort(key=lambda x: x[1])
            
            # 1. Calcula centróides, soma de sobrevivência e utilidade para cada cluster
            cluster_info = []
            for label, mean_sobr, vids in cluster_priorities:
                # Calcula centroide
                coords_list = [self.victims[vid][0] for vid in vids]
                cx = np.mean([c[0] for c in coords_list])
                cy = np.mean([c[1] for c in coords_list])
                
                # Soma das probabilidades de sobrevivencia (sobr_pred no indice 14)
                sum_sobr = np.sum([self.victims[vid][1][14] for vid in vids])
                
                # Distancia ate a base (0, 0)
                dist_base = math.sqrt(cx**2 + cy**2)
                
                # Utilidade = soma_sobr / (dist_base + 1.0)
                utility = sum_sobr / (dist_base + 1.0)
                
                cluster_info.append({
                    'vids': vids,
                    'centroid': (cx, cy),
                    'sum_sobr': sum_sobr,
                    'utility': utility
                })
                
            # 2. Ordena os clusters por utilidade decrescente
            cluster_info.sort(key=lambda x: x['utility'], reverse=True)
            
            # 3. Distribuição Gulosa e Inteligente entre os socorristas
            assignments = { 'SOC_1': [], 'SOC_2': [], 'SOC_3': [] }
            last_pos = { 'SOC_1': (0, 0), 'SOC_2': (0, 0), 'SOC_3': (0, 0) }
            accumulated_workload = { 'SOC_1': 0.0, 'SOC_2': 0.0, 'SOC_3': 0.0 }
            
            t05_dir = os.path.dirname(self.config_folder)
            clusters_dir = os.path.join(t05_dir, "clusters")
            os.makedirs(clusters_dir, exist_ok=True)
            
            # Limpa a pasta clusters no inicio para tirar arquivos de execucoes anteriores
            for file in os.listdir(clusters_dir):
                if file.startswith("cluster_") and file.endswith(".txt"):
                    try:
                        os.remove(os.path.join(clusters_dir, file))
                    except OSError:
                        pass
                        
            for priority_id, info in enumerate(cluster_info, 1):
                vids = info['vids']
                cx, cy = info['centroid']
                num_victims = len(vids)
                
                # Encontra o socorrista com menor incremento estimado de carga de trabalho
                best_agent = None
                min_cost = float('inf')
                for agent in ['SOC_1', 'SOC_2', 'SOC_3']:
                    lx, ly = last_pos[agent]
                    dist_to_cluster = math.sqrt((lx - cx)**2 + (ly - cy)**2)
                    estimated_cost = accumulated_workload[agent] + dist_to_cluster + (num_victims * self.COST_FIRST_AID)
                    
                    if estimated_cost < min_cost:
                        min_cost = estimated_cost
                        best_agent = agent
                
                # Atualiza carga de trabalho acumulada e ultima posicao
                lx, ly = last_pos[best_agent]
                dist_to_cluster = math.sqrt((lx - cx)**2 + (ly - cy)**2)
                accumulated_workload[best_agent] += dist_to_cluster + (num_victims * self.COST_FIRST_AID)
                last_pos[best_agent] = (cx, cy)
                
                # Atribui o cluster
                assignments[best_agent].append((priority_id, vids))
                
            print(f"{self.NAME}: DBSCAN priorizou {len(cluster_info)} clusters clínicos.")
            for agent in ['SOC_1', 'SOC_2', 'SOC_3']:
                print(f"{self.NAME}: clusters delegados para {agent} -> {[c[0] for c in assignments[agent]]}")
        else:
            assignments = { 'SOC_1': [], 'SOC_2': [], 'SOC_3': [] }
            
        # Dispara planejamento de socorro para todos os socorristas compartilhando o mapa e as vitimas unificadas
        for i in range(3):
            self.rescuers[i].map = self.map
            self.rescuers[i].victims = self.victims
            agent_name = self.rescuers[i].NAME
            self.rescuers[i].do_rescue(self.map, assignments.get(agent_name, []))

    def deliberate(self) -> bool:
        if self.plan == []:
           print(f"{self.NAME} planeamento concluido.")
           return False

        dx, dy, there_is_vict = self.plan.pop(0)
        walked = self.walk(dx, dy)

        if walked == VS.EXECUTED:
            self.x += dx
            self.y += dy
            if there_is_vict:
                rescued = self.first_aid()
                if rescued:
                    print(f"{self.NAME} Vitima socorrida na coordenada ({self.x}, {self.y})")
                else:
                    print(f"{self.NAME} Falha - vitima nao encontrada em ({self.x}, {self.y})")
        else:
            print(f"{self.NAME} Falha de movimento - agente em ({self.x}, {self.y})")
            
        return True
