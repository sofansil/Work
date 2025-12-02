#cmd
#pip install pygame
import pygame
import random
import sys

# 초기화
pygame.init()

# 설정
CELL_SIZE = 30
COLS = 10
ROWS = 20
WIDTH = CELL_SIZE * COLS
HEIGHT = CELL_SIZE * ROWS
FPS = 60

# 색상
BLACK = (0, 0, 0)
GRAY = (40, 40, 40)
WHITE = (255, 255, 255)
COLORS = [
    (0, 255, 255),   # I
    (0, 0, 255),     # J
    (255, 165, 0),   # L
    (255, 255, 0),   # O
    (0, 255, 0),     # S
    (128, 0, 128),   # T
    (255, 0, 0),     # Z
]

# 테트리스 블록의 회전 상태 정의 (각 모양은 여러 회전 배열)
SHAPES = [
    [[".....",
      ".....",
      "..OOO",
      ".....",
      "....."],
     [".....",
      "..O..",
      "..O..",
      "..O..",
      "....."],
     [".....",
      ".....",
      "OOO..",
      ".....",
      "....."],
     [".....",
      "..O..",
      "..O..",
      "..O..",
      "....."]],  # I (길게 보이도록 중앙 정렬)

    [[".....",
      ".O...",
      ".OOO.",
      ".....",
      "....."],
     [".....",
      "..OO.",
      "..O..",
      "..O..",
      "....."],
     [".....",
      ".....",
      ".OOO.",
      "...O.",
      "....."],
     [".....",
      "..O..",
      "..O..",
      ".OO..",
      "....."]],  # J

    [[".....",
      "...O.",
      ".OOO.",
      ".....",
      "....."],
     [".....",
      "..O..",
      "..O..",
      "..OO.",
      "....."],
     [".....",
      ".....",
      ".OOO.",
      ".O...",
      "....."],
     [".....",
      ".OO..",
      "..O..",
      "..O..",
      "....."]],  # L

    [[".....",
      "..OO.",
      "..OO.",
      ".....",
      "....."]],  # O (회전 동일)

    [[".....",
      "..OO.",
      ".OO..",
      ".....",
      "....."],
     [".....",
      "..O..",
      "..OO.",
      "...O.",
      "....."]],  # S

    [[".....",
      "..O..",
      ".OOO.",
      ".....",
      "....."],
     [".....",
      "..O..",
      "..OO.",
      "..O..",
      "....."],
     [".....",
      ".....",
      ".OOO.",
      "..O..",
      "....."],
     [".....",
      "..O..",
      ".OO..",
      "..O..",
      "....."]],  # T

    [[".....",
      ".OO..",
      "..OO.",
      ".....",
      "....."],
     [".....",
      "...O.",
      "..OO.",
      "..O..",
      "....."]],  # Z
]

# 간단한 모양 인덱스 매핑
SHAPE_COLORS = COLORS  # 동일 인덱스 사용

class Piece:
    def __init__(self, x, y, shape_idx):
        self.x = x
        self.y = y
        self.idx = shape_idx
        self.rot = 0
        self.shape = SHAPES[shape_idx]

    def cells(self):
        layout = self.shape[self.rot % len(self.shape)]
        positions = []
        for i, row in enumerate(layout):
            for j, cell in enumerate(row):
                if cell == 'O':
                    positions.append((self.x + j - 2, self.y + i - 2))  # 중앙 정렬 오프셋
        return positions

    def rotate(self):
        self.rot = (self.rot + 1) % len(self.shape)

    def rotate_back(self):
        self.rot = (self.rot - 1) % len(self.shape)

class Tetris:
    def __init__(self):
        self.grid = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.score = 0
        self.level = 1
        self.lines = 0
        self.current = self.new_piece()
        self.next_piece = self.new_piece()
        self.game_over = False
        self.drop_counter = 0
        self.drop_speed = 30  # 프레임 단위 기본값

    def new_piece(self):
        idx = random.randrange(len(SHAPES))
        # 시작 위치: 중앙 상단
        return Piece(COLS // 2, 0, idx)

    def valid(self, piece):
        for x, y in piece.cells():
            if x < 0 or x >= COLS or y >= ROWS:
                return False
            if y >= 0 and self.grid[y][x] is not None:
                return False
        return True

    def lock_piece(self):
        for x, y in self.current.cells():
            if y < 0:
                self.game_over = True
                return
            self.grid[y][x] = self.current.idx
        cleared = self.clear_lines()
        self.score += cleared * 100
        self.lines += cleared
        self.level = 1 + self.lines // 10
        self.drop_speed = max(5, 30 - (self.level - 1) * 2)
        self.current = self.next_piece
        self.next_piece = self.new_piece()
        if not self.valid(self.current):
            self.game_over = True

    def clear_lines(self):
        cleared = 0
        new_grid = [row for row in self.grid if any(cell is None for cell in row)]
        cleared = ROWS - len(new_grid)
        for _ in range(cleared):
            new_grid.insert(0, [None for _ in range(COLS)])
        self.grid = new_grid
        return cleared

    def hard_drop(self):
        while True:
            self.current.y += 1
            if not self.valid(self.current):
                self.current.y -= 1
                self.lock_piece()
                break

    def step(self):
        self.drop_counter += 1
        if self.drop_counter >= self.drop_speed:
            self.drop_counter = 0
            self.current.y += 1
            if not self.valid(self.current):
                self.current.y -= 1
                self.lock_piece()

    def move(self, dx):
        self.current.x += dx
        if not self.valid(self.current):
            self.current.x -= dx

    def rotate(self):
        self.current.rotate()
        if not self.valid(self.current):
            # 간단한 벽킥 시도
            self.current.x += 1
            if not self.valid(self.current):
                self.current.x -= 2
                if not self.valid(self.current):
                    self.current.x += 1
                    self.current.rotate_back()

def draw_grid(surface):
    for y in range(ROWS):
        for x in range(COLS):
            rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(surface, GRAY, rect, 1)

def draw_block(surface, x, y, color):
    rect = pygame.Rect(x * CELL_SIZE + 1, y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2)
    pygame.draw.rect(surface, color, rect)

def draw_game(surface, game, font):
    surface.fill(BLACK)
    # 그리드와 고정 블록
    for y in range(ROWS):
        for x in range(COLS):
            if game.grid[y][x] is not None:
                color = SHAPE_COLORS[game.grid[y][x] % len(SHAPE_COLORS)]
                draw_block(surface, x, y, color)
    # 현재 조각
    for x, y in game.current.cells():
        if y >= 0:
            color = SHAPE_COLORS[game.current.idx % len(SHAPE_COLORS)]
            draw_block(surface, x, y, color)
    # 그리드 선
    draw_grid(surface)
    # UI: 점수 등
    info_surf = font.render(f"Score: {game.score}  Lines: {game.lines}  Level: {game.level}", True, WHITE)
    surface.blit(info_surf, (10, 10))
    # 다음 블록 표시
    next_x = WIDTH + 20
    next_y = 60
    small = pygame.Surface((120, 120))
    small.fill(BLACK)
    layout = game.next_piece.shape[0]
    for i, row in enumerate(layout):
        for j, ch in enumerate(row):
            if ch == 'O':
                col = SHAPE_COLORS[game.next_piece.idx % len(SHAPE_COLORS)]
                rx = next_x + j * 20
                ry = next_y + i * 20
                pygame.draw.rect(surface, col, (rx, ry, 18, 18))
    label = font.render("Next:", True, WHITE)
    surface.blit(label, (next_x, 30))

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH + 200, HEIGHT))
    pygame.display.set_caption("Tetris")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 20)
    game = Tetris()

    fall_event = pygame.USEREVENT + 1
    pygame.time.set_timer(fall_event, 1000)  # 보조 타이머 (대체 사용 가능)

    running = True
    while running:
        dt = clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if game.game_over:
                    if event.key == pygame.K_r:
                        game = Tetris()
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                    continue
                if event.key == pygame.K_LEFT:
                    game.move(-1)
                elif event.key == pygame.K_RIGHT:
                    game.move(1)
                elif event.key == pygame.K_DOWN:
                    game.current.y += 1
                    if not game.valid(game.current):
                        game.current.y -= 1
                        game.lock_piece()
                elif event.key == pygame.K_UP:
                    game.rotate()
                elif event.key == pygame.K_SPACE:
                    game.hard_drop()
                elif event.key == pygame.K_p:
                    paused = True
                    while paused:
                        for ev in pygame.event.get():
                            if ev.type == pygame.QUIT:
                                pygame.quit()
                                sys.exit()
                            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_p:
                                paused = False
                        clock.tick(15)

        if not game.game_over:
            game.step()

        draw_game(screen, game, font)
        if game.game_over:
            over_surf = font.render("Game Over - R to Restart  Esc to Quit", True, WHITE)
            screen.blit(over_surf, (20, HEIGHT // 2 - 10))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()