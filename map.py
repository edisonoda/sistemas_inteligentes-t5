from vs.constants import VS

class Map:
    def __init__(self):
        self.map_data = {}

    def in_map(self, coord):
        return coord in self.map_data

    def get(self, coord):
        return self.map_data.get(coord)

    def add(self, coord, difficulty, victim_seq, actions_res):
        self.map_data[coord] = (difficulty, victim_seq, actions_res)

    def draw(self):
        if not self.map_data:
            print("Map is empty.")
            return

        min_x = min(key[0] for key in self.map_data.keys())
        max_x = max(key[0] for key in self.map_data.keys())
        min_y = min(key[1] for key in self.map_data.keys())
        max_y = max(key[1] for key in self.map_data.keys())

        for y in range(min_y, max_y + 1):
            row = ""
            for x in range(min_x, max_x + 1):
                item = self.get((x, y))
                if item:
                    if item[1] == VS.NO_VICTIM:
                        row += f"[{item[0]:7.2f}  no] "
                    else:
                        row += f"[{item[0]:7.2f} {item[1]:3d}] "
                else:
                    row += f"[     ?     ] "
            print(row)
