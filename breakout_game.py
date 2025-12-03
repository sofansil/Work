import pygame
import random
import sys

# 초기화
pygame.init()

# 화면 설정
WIDTH = 800
HEIGHT = 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("블록 깨기 게임")

# 색상
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
ORANGE = (255, 165, 0)
LIME = (50, 205, 50)
PURPLE = (128, 0, 128)

# 시계
clock = pygame.time.Clock()
FPS = 60

# 패들 클래스
class Paddle(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((300, 15))
        self.image.fill(WHITE)
        self.rect = self.image.get_rect()
        self.rect.centerx = WIDTH // 2
        self.rect.bottom = HEIGHT - 10

    def update(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] and self.rect.left > 0:
            self.rect.x -= 5
        if keys[pygame.K_RIGHT] and self.rect.right < WIDTH:
            self.rect.x += 5

# 공 클래스
class Ball(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((10, 10))
        self.image.fill(YELLOW)
        self.rect = self.image.get_rect()
        self.rect.center = (WIDTH // 2, HEIGHT // 2)
        self.vel_x = 4
        self.vel_y = -4

    def update(self):
        self.rect.x += self.vel_x
        self.rect.y += self.vel_y

        # 벽 충돌
        if self.rect.left <= 0 or self.rect.right >= WIDTH:
            self.vel_x *= -1
        if self.rect.top <= 0:
            self.vel_y *= -1
        if self.rect.bottom >= HEIGHT:
            return False
        return True

# 블록 클래스
class Block(pygame.sprite.Sprite):
    def __init__(self, x, y, color):
        super().__init__()
        self.image = pygame.Surface((75, 15))
        self.image.fill(color)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

# 아이템 클래스
class Item(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((20, 20))
        self.image.fill(PURPLE)
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        self.vel_y = 2

    def update(self):
        self.rect.y += self.vel_y
        if self.rect.bottom >= HEIGHT:
            self.kill()

# 총알 클래스
class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((5, 15))
        self.image.fill(RED)
        self.rect = self.image.get_rect()
        self.rect.centerx = x
        self.rect.bottom = y
        self.vel_y = -7

    def update(self):
        self.rect.y += self.vel_y
        if self.rect.bottom <= 0:
            self.kill()

# 게임 클래스
class Game:
    def __init__(self):
        self.paddle = Paddle()
        self.ball = Ball()
        self.all_sprites = pygame.sprite.Group()
        self.blocks = pygame.sprite.Group()
        self.items = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.all_sprites.add(self.paddle)
        self.all_sprites.add(self.ball)
        self.score = 0
        self.font = pygame.font.Font(None, 36)
        self.has_bullet = False
        self.create_blocks()

    def create_blocks(self):
        colors = [CYAN, MAGENTA, ORANGE, LIME]
        for row in range(4):
            for col in range(10):
                x = col * 80
                y = row * 20 + 40
                color = colors[row]
                block = Block(x, y, color)
                self.blocks.add(block)
                self.all_sprites.add(block)

    def run(self):
        running = True
        while running:
            clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE and self.has_bullet:
                        bullet = Bullet(self.paddle.rect.centerx, self.paddle.rect.top)
                        self.bullets.add(bullet)
                        self.all_sprites.add(bullet)
                        self.has_bullet = False

            # 업데이트
            self.all_sprites.update()
            if not self.ball.update():
                running = False

            # 패들과 공 충돌
            if pygame.sprite.spritecollide(self.ball, pygame.sprite.Group(self.paddle), False):
                self.ball.vel_y *= -1

            # 블록과 공 충돌
            hit_blocks = pygame.sprite.spritecollide(self.ball, self.blocks, True)
            if hit_blocks:
                self.ball.vel_y *= -1
                self.score += len(hit_blocks) * 10
                # 벽돌이 깨지면 아이템 생성
                for block in hit_blocks:
                    if random.random() < 0.3:  # 30% 확률로 아이템 출현
                        item = Item(block.rect.centerx, block.rect.centery)
                        self.items.add(item)
                        self.all_sprites.add(item)

            # 패들과 아이템 충돌
            hit_items = pygame.sprite.spritecollide(self.paddle, self.items, True)
            if hit_items:
                self.has_bullet = True

            # 총알과 블록 충돌
            for bullet in self.bullets:
                hit_blocks = pygame.sprite.spritecollide(bullet, self.blocks, True)
                if hit_blocks:
                    bullet.kill()
                    self.score += len(hit_blocks) * 10

            # 그리기
            screen.fill(BLACK)
            self.all_sprites.draw(screen)
            self.items.draw(screen)
            self.bullets.draw(screen)

            # 점수 표시
            score_text = self.font.render(f"Score: {self.score}", True, WHITE)
            screen.blit(score_text, (10, 10))

            # 총알 상태 표시
            bullet_status = "총알: O" if self.has_bullet else "총알: X"
            bullet_text = self.font.render(bullet_status, True, GREEN if self.has_bullet else RED)
            screen.blit(bullet_text, (WIDTH - 200, 10))

            # 게임 오버
            if len(self.blocks) == 0:
                win_text = self.font.render("YOU WIN!", True, GREEN)
                screen.blit(win_text, (WIDTH // 2 - 100, HEIGHT // 2))

            pygame.display.flip()

        pygame.quit()
        sys.exit()

# 게임 실행
if __name__ == "__main__":
    game = Game()
    game.run()