from typing import List
import random

from interface import SynchronousAPI, State, Action, NULL_PLAYER_ID


if __name__ == "__main__":
    api = SynchronousAPI()

    def random_bot(state: State) -> List[Action]:
        actions: List[Action] = []

        # print("Received state:\n", state)

        if not state["game_started"]:
            return actions

        my_id = state["my_id"]
        is_land = state["map"]["is_land"]
        ownership = state["map"]["ownership"]
        width = state["map"]["width"]
        height = state["map"]["height"]

        # Place on a random land tile during spawn phase
        if state["is_spawn_phase"]:
            while True:
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)
                print("Trying to place at", (y, x), "land:", is_land[y][x], "owned:", ownership[y][x])
                if is_land[y][x] and ownership[y][x] == NULL_PLAYER_ID:
                    return [{"action": "spawn", "location": (y, x)}]

        return []




    api.register_agent(random_bot, headless=False)
    api.register_agent(random_bot, headless=False)

    api.play()