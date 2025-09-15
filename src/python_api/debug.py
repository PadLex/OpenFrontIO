import pygame
import numpy as np

W, H   = 64, 64          # logical grid (matrix) size
SCALE  = 10              # on-screen pixel size
FPS    = 60

pygame.init()
screen  = pygame.display.set_mode((W*SCALE, H*SCALE))
clock   = pygame.time.Clock()

# Example: grayscale matrix -> RGB pixels
# Keep a single array and mutate it each frame
buf = np.zeros((H, W, 3), dtype=np.uint8)

running = True
t = 0.0
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

    # --- update your matrix here (demo animation) ---
    y, x = np.mgrid[0:H, 0:W]
    val = (np.sin(0.15*x + t) + np.cos(0.12*y - t)) * 0.5 + 0.5  # 0..1
    buf[..., 0] = (val * 255).astype(np.uint8)      # R
    buf[..., 1] = (1 - val * 0.8 * (x % 2)).astype(np.uint8)     # G
    buf[..., 2] = (val * 255).astype(np.uint8)      # B
    t += 0.08
    # -----------------------------------------------

    # Create/update a surface from the array (no per-rect drawing)
    surf = pygame.surfarray.make_surface(buf.swapaxes(0,1))  # (W,H,3)
    surf = pygame.transform.scale(surf, (W*SCALE, H*SCALE))  # nearest-neighbor
    screen.blit(surf, (0, 0))
    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
