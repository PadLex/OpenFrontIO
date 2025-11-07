from typing import List
import numpy as np
import random

from interface import SynchronousAPI, State, Action, NULL_PLAYER_ID
from debug import MapVisualizer

def neighbor_ids_by_edges(A, my_id, eight=False):
    outs = []

    print("\n\n", my_id)
    print(A)

    # vertical neighbors
    up, down = A[:-1, :], A[1:, :]
    m = (up == my_id) ^ (down == my_id)
    outs.append(np.where(up[m] == my_id, down[m], up[m]))

    # horizontal neighbors
    left, right = A[:, :-1], A[:, 1:]
    m = (left == my_id) ^ (right == my_id)
    outs.append(np.where(left[m] == my_id, right[m], left[m]))

    if eight:
        # diag: up-left <-> down-right
        ul, dr = A[:-1, :-1], A[1:, 1:]
        m = (ul == my_id) ^ (dr == my_id)
        outs.append(np.where(ul[m] == my_id, dr[m], ul[m]))

        # diag: up-right <-> down-left
        ur, dl = A[:-1, 1:], A[1:, :-1]
        m = (ur == my_id) ^ (dl == my_id)
        outs.append(np.where(ur[m] == my_id, dl[m], ur[m]))

    return np.unique(np.concatenate(outs)) if outs else np.array([], dtype=A.dtype)



if __name__ == "__main__":
    api = SynchronousAPI()

    visualizer: MapVisualizer | None = None

    def random_bot(state: State) -> List[Action]:
        global visualizer
        if visualizer is None:
            visualizer = MapVisualizer(state)


        actions: List[Action] = []

        if not state["game_started"]:
            return actions

        my_id = np.array(state["my_id"])
        is_land = state["is_land"]
        ownership = np.array(state["ownership"])
        width = state["width"]
        height = state["height"]
        players = state["players"]

        if my_id == 1:
            visualizer.render(state)

        # Place on a random land tile during spawn phase
        if state["is_spawn_phase"]:
            while True:
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)
                print("Trying to place at", (y, x), "land:", is_land[y][x], "owned:", ownership[y][x])
                if is_land[y][x] and ownership[y][x] == NULL_PLAYER_ID:
                    return [{"action": "spawn", "x": x, "y": y}]

        # print(neighbor_ids_by_edges(ownership, my_id, eight=True))

        return []


    # api.register_agent(random_bot, "debug")
    # api.register_agent(random_bot, "window")
    # api.register_agent(random_bot, "window")

    api.register_agent(random_bot, "headless")
    api.register_agent(random_bot, "headless")


    api.play()