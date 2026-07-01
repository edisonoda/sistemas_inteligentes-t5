# EXPLORER AGENT
# @Author: Tacla, UTFPR
#
### It walks randomly in the environment looking for victims. When half of the
### exploration has gone, the explorer goes back to the base.

import os
import math
import random
import pandas as pd
import joblib
from vs.abstract_agent import AbstAgent
from vs.constants import VS
from map import Map

class Stack:
    def __init__(self):
        self.items = []
    def push(self, item):
        self.items.append(item)
    def pop(self):
        return self.items.pop()
    def is_empty(self):
        return len(self.items) == 0

class Explorer(AbstAgent):
    def __init__(self, env, config_file, resc):
        """ Construtor do agente random on-line
        @param env: a reference to the environment 
        @param config_file: the absolute path to the explorer's config file
        @param resc: a reference to the rescuer agent to invoke when exploration finishes
        """
        super().__init__(env, config_file)
        self.walk_stack = Stack()
        self.set_state(VS.ACTIVE)
        self.resc = resc
        self.x = 0
        self.y = 0
        self.map = Map()
        self.victims = {}

        # Registra a base no mapa e no set local de visitados
        self.map.add((self.x, self.y), 1, VS.NO_VICTIM, self.check_walls_and_lim())
        self.visited = set()
        self.visited.add((self.x, self.y))

        try:
            num = int(self.NAME.split("_")[-1])
        except ValueError:
            num = 1
            
        if num == 1:
            pivot = 0  # Começa pelo Norte (Up)
        elif num == 2:
            pivot = 3  # Começa pelo Leste (Bottom Right)
        else:
            pivot = 5  # Começa pelo Oeste (Bottom Left)
            
        self.dir_priority = [(pivot + i) % 8 for i in range(8)]

        # Carregar modelos preditivos treinados
        t05_dir = os.path.dirname(os.path.dirname(config_file))
        self.classificador = joblib.load(os.path.join(t05_dir, "mlp_model_t01.joblib"))
        self.regressor = joblib.load(os.path.join(t05_dir, "cart_model_t02.joblib"))

        # Custo do pior caso de um passo (andar na diagonal com maior dificuldade 3, ler vitais e voltar)
        self.one_more_step = self.COST_DIAG * 2 * 3 + self.COST_READ

        # Configurações para busca local em espiral/cluster
        self.spiral_mode = False
        self.spiral_center = None
        self.spiral_radius_limit = 3

    def get_backtrack_cost(self):
        # Calcula o custo exato para voltar para a base desempilhando walk_stack
        cost = 0.0
        curr_x, curr_y = self.x, self.y
        for dx, dy in reversed(self.walk_stack.items):
            nx = curr_x - dx
            ny = curr_y - dy
            if dx != 0 and dy != 0:
                base = self.COST_DIAG
            else:
                base = self.COST_LINE
            cell_data = self.map.get((nx, ny))
            difficulty = cell_data[0] if cell_data else 1.0
            cost += base * difficulty
            curr_x, curr_y = nx, ny
        return cost

    def get_next_position(self):
        """ Online DFS and local spiral search to get the next position.
        """
        obstacles = self.check_walls_and_lim()
        valid_moves = []

        # 1. Filtra movimentos válidos e não visitados localmente
        for direction in range(8):
            if obstacles[direction] == VS.CLEAR:
                dx, dy = Explorer.AC_INCR[direction]
                nx, ny = self.x + dx, self.y + dy
                if (nx, ny) not in self.visited:
                    valid_moves.append((direction, dx, dy, nx, ny))

        if not valid_moves:
            return None

        # 2. Se estiver em modo espiral, tenta priorizar vizinhos próximos ao centro
        if self.spiral_mode:
            cx, cy = self.spiral_center
            cluster_moves = []
            for direction, dx, dy, nx, ny in valid_moves:
                dist = max(abs(nx - cx), abs(ny - cy)) # Distância Chebyshev
                if dist <= self.spiral_radius_limit:
                    cluster_moves.append((direction, dx, dy, nx, ny, dist))

            if cluster_moves:
                # Ordena pelo vizinho mais próximo do centro (crescente).
                # Se empatar na distância, usa a prioridade rotacionada do agente
                cluster_moves.sort(key=lambda item: (item[5], self.dir_priority.index(item[0])))
                best_move = cluster_moves[0]
                return best_move[1], best_move[2]
            else:
                # Sem vizinhos livres dentro do raio do cluster: desativa modo espiral
                self.spiral_mode = False

        # 3. DFS linear padrão usando a ordem de prioridade rotacionada
        valid_moves.sort(key=lambda item: self.dir_priority.index(item[0]))
        return valid_moves[0][1], valid_moves[0][2]

    def explore(self):
        next_move = self.get_next_position()
        
        if next_move is not None:
            dx, dy = next_move
            nx, ny = self.x + dx, self.y + dy
            
            # Verifica se ha bateria suficiente para ir e depois voltar
            # Pior caso da acao: custo diagonal com dificuldade maxima (3)
            worst_action_cost = self.COST_DIAG * 3
            backtrack_cost = self.get_backtrack_cost()
            
            # Se a bateria restante apos a acao e leitura for suficiente para voltar de (nx, ny)
            if self.get_rtime() - (worst_action_cost + self.COST_READ + backtrack_cost + worst_action_cost) >= 0:
                # Marca como visitado localmente
                self.visited.add((nx, ny))
                
                rtime_bef = self.get_rtime()
                result = self.walk(dx, dy)
                rtime_aft = self.get_rtime()
                
                if result == VS.BUMPED:
                    self.map.add((nx, ny), VS.OBST_WALL, VS.NO_VICTIM, self.check_walls_and_lim())
                    
                if result == VS.EXECUTED:
                    self.walk_stack.push((dx, dy))
                    self.x += dx
                    self.y += dy
                    
                    seq = self.check_for_victim()
                    if seq != VS.NO_VICTIM:
                        self.spiral_mode = True
                        self.spiral_center = (self.x, self.y)
                        # Le os sinais vitais (retorna 12 elementos)
                        vs = self.read_vital_signals()
                        if vs and vs != VS.TIME_EXCEEDED:
                            # Preve tri e sobr usando os modelos carregados
                            cols = ['idade', 'fc', 'fr', 'pas', 'spo2', 'temp', 'pr', 'sg', 'fx', 'queim']
                            features = pd.DataFrame([vs[1:11]], columns=cols)
                            tri_pred = int(self.classificador.predict(features)[0])
                            sobr_pred = float(self.regressor.predict(features)[0])
                            
                            # Adiciona as prediçoes ao final da lista para completar 14 elementos
                            vs_complete = list(vs) + [tri_pred, sobr_pred]
                            self.victims[seq] = ((self.x, self.y), vs_complete)
                    
                    difficulty = (rtime_bef - rtime_aft)
                    if dx == 0 or dy == 0:
                        difficulty = difficulty / self.COST_LINE
                    else:
                        difficulty = difficulty / self.COST_DIAG
                        
                    self.map.add((self.x, self.y), difficulty, seq, self.check_walls_and_lim())
                return
                
        # Sem vizinhos unvisitados ou bateria baixa: faz backtracking
        self.come_back()

    def come_back(self):
        """ Procedure to return to the base: pops the walk_stack to follow
        the exploration path in the opposite direction """
        if self.walk_stack.is_empty():
            return
            
        dx, dy = self.walk_stack.pop()
        dx = dx * -1
        dy = dy * -1
        result = self.walk(dx, dy)
        if result == VS.BUMPED:
            print(f"{self.NAME}: quando voltava colidiu em ({self.x+dx}, {self.y+dy}) , rtime: {self.get_rtime()}")
            return
        if result == VS.EXECUTED:
            self.x += dx
            self.y += dy
        
    def deliberate(self) -> bool:
        """  The simulator calls this method at each cycle. 
        Must be implemented in every agent. The agent chooses the next action.
        """
        # Se a pilha de caminhos estiver vazia e nao houver vizinhos a explorar, terminou
        # ou se a bateria nao for suficiente para dar um passo de exploracao e voltar com folga
        # (usamos a estimativa do backtrack + worst case de passo e leitura + margem de retorno seguro)
        backtrack_cost = self.get_backtrack_cost()
        worst_step_needed = (self.COST_DIAG * 3 * 2) + self.COST_READ + 2.0
        
        if (self.get_rtime() - backtrack_cost) > worst_step_needed:
            # Tem bateria, tenta explorar
            # Verifica se o grid inteiro ja foi visitado ou se ficamos presos
            obstacles = self.check_walls_and_lim()
            has_unvisited_neighbor = False
            for direction in range(8):
                if obstacles[direction] == VS.CLEAR:
                    dx, dy = Explorer.AC_INCR[direction]
                    if (self.x + dx, self.y + dy) not in self.visited:
                        has_unvisited_neighbor = True
                        break
                        
            if has_unvisited_neighbor or not self.walk_stack.is_empty():
                self.explore()
                return True
                
        # Nao tem bateria ou ja voltou para a base e nao ha mais ramos de busca
        if self.walk_stack.is_empty():
            print(f"{self.NAME}: exploraçao terminada. Chamando merge_maps do mestre.")
            self.resc.merge_maps(self.NAME, self.map, self.victims)
            return False
            
        self.come_back()
        return True
