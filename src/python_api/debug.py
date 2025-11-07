import pygame
import numpy as np

from interface import State, NULL_PLAYER_ID


class MapVisualizer:

    def __init__(self, state: State):
        self.width = state["width"]
        self.height = state["height"]
        self.scale = state["skip"]

        pygame.init()
        self.screen  = pygame.display.set_mode((self.width * self.scale, self.height * self.scale))
        pygame.display.set_caption("Map Visualizer")
        self.clock   = pygame.time.Clock()
        self.running = True

        players = state["players"]
        my_id = state["my_id"]
        self.colors = np.random.randint(0, 128, size=(5000, 3), dtype=np.uint8)
        self.colors[NULL_PLAYER_ID] = [0, 255, 0]  # Empty
        self.colors[my_id] = [255, 0, 0] # Me

        self.water_mask = ~np.array(state["is_land"], dtype=bool)


    def render(self, state: State):
        ownership = state["ownership"]

        if not self.running:
            return

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                self.running = False
                return

        # Example: grayscale matrix -> RGB pixels
        # Keep a single array and mutate it each frame
        buf = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        color = self.colors[ownership]
        buf[:, :, :] = color[:, :, :]

        buf[self.water_mask] = [0, 0, 255]

        y, x = np.mgrid[0:self.height, 0:self.width]

        surf = pygame.surfarray.make_surface(buf.swapaxes(0,1))  # (W,H,3)
        surf = pygame.transform.scale(surf, (self.width * self.scale, self.height * self.scale))
        self.screen.blit(surf, (0, 0))
        pygame.display.flip()


